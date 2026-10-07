"""Offline provenance, input-lineage, and built-output checks for publication."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import gather
from project_discovery import PROJECT_SUB, _repo_identity

EXPECTED_SOURCES = {"rss", "arxiv", "reddit", "bsky", "hn", "kagi", "polymarket", "opensource"}


def _report():
    return {"errors": [], "warnings": [], "counts": {}, "limitations": [
        "URL lineage establishes retained input identity, not semantic support, relevance, or event equivalence."
    ]}


def _read_json(path: Path):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def _timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing collected_at")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _safe_output(run_dir: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or os.path.isabs(relative):
        return None
    candidate = run_dir / relative
    try:
        candidate.relative_to(run_dir)
    except ValueError:
        return None
    if candidate.is_symlink() or (relative.startswith('kagi/') and (run_dir / 'kagi').is_symlink()) or not candidate.is_file():
        return None
    if relative in gather.OUTPUT_FILE.values() or (
        relative.startswith("kagi/") and relative.endswith(".json") and "/" not in relative[5:]
    ):
        return candidate
    return None


def _legacy_replay(root, manifest):
    report = _report()
    report['provenance_verified'] = False
    report['warnings'].append('Historical replay: original generation/timestamps/hashes are unverified; not eligible for publication.')
    consumed, successful = set(), 0
    for name, entry in manifest.items():
        if not isinstance(entry, dict) or entry.get('status') not in {'OK', 'EMPTY', 'FAIL', 'TIMEOUT', 'GLOBAL_DEADLINE'}:
            report['errors'].append(f'{name}: invalid legacy source status')
            continue
        candidates = list((root / 'kagi').glob('*.json')) if name == 'kagi' else [root / gather.OUTPUT_FILE[name]]
        present = [path for path in candidates if path.exists() or path.is_symlink()]
        if entry['status'] not in {'OK', 'EMPTY'}:
            if present:
                report['errors'].append(f'{name}: failed legacy source has leftover consumable output')
            report['warnings'].append(f'{name}: source unavailable ({entry["status"]})')
            continue
        count, paths = gather._validate(name, str(root))
        if count is None:
            report['errors'].append(f'{name}: invalid legacy schema ({paths})')
            continue
        for relative in paths:
            path = _safe_output(root, relative)
            if path is None:
                report['errors'].append(f'{name}: unsafe legacy input path')
            else:
                consumed.add(path)
        successful += count > 0
        if not count:
            report['warnings'].append(f'{name}: source completed empty')
    if not consumed or not successful:
        report['errors'].append('historical replay has no usable collected source records')
    report['counts'].update(consumed_outputs=len(consumed), successful_sources=successful)
    return report, consumed


def check_provenance(run_dir: str | Path, edition: str, *, now=None, historical_replay=False):
    """Validate gather's immutable manifest and only return verified consumed paths."""
    report = _report()
    root = Path(run_dir)
    lock_path = root / ".gather.lock"
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            report["errors"].append("gather lock is held; refusing concurrent validation")
            return report, set()
    except OSError as exc:
        report["errors"].append(f"cannot inspect gather lock: {exc}")
        return report, set()
    try:
        try:
            manifest = _read_json(root / "gather_manifest.json")
        except ValueError as exc:
            report["errors"].append(str(exc))
            return report, set()
        if not isinstance(manifest, dict) or set(manifest) != EXPECTED_SOURCES:
            report["errors"].append("manifest must contain exactly all expected source names")
            return report, set()
        legacy = all(isinstance(entry, dict) and not {'generation_id', 'collected_at', 'outputs'} & entry.keys()
                     for entry in manifest.values())
        if historical_replay and legacy:
            return _legacy_replay(root, manifest)
        clock = now or datetime.now(timezone.utc)
        clock = clock.replace(tzinfo=timezone.utc) if clock.tzinfo is None else clock.astimezone(timezone.utc)
        generations, times, consumed, successful = set(), [], set(), 0
        for name, entry in manifest.items():
            if not isinstance(entry, dict):
                report["errors"].append(f"{name}: malformed manifest entry")
                continue
            status = entry.get("status")
            if status == "IN_PROGRESS":
                report["errors"].append(f"{name}: collection remains IN_PROGRESS")
                continue
            if status not in {"OK", "EMPTY", "FAIL", "TIMEOUT", "GLOBAL_DEADLINE"}:
                report["errors"].append(f"{name}: invalid status {status!r}")
                continue
            try:
                stamp = _timestamp(entry.get("collected_at"))
                times.append(stamp)
                if stamp.date().isoformat() != edition:
                    report["errors"].append(f"{name}: collection date does not match edition")
                if stamp > clock:
                    report["errors"].append(f"{name}: collection timestamp is in the future")
            except ValueError as exc:
                report["errors"].append(f"{name}: {exc}")
            generation = entry.get("generation_id")
            if not isinstance(generation, str) or not generation:
                report["errors"].append(f"{name}: missing generation_id")
            else:
                generations.add(generation)
            outputs = entry.get("outputs")
            if not isinstance(outputs, list):
                report["errors"].append(f"{name}: outputs must be a list")
                continue
            if status in {"FAIL", "TIMEOUT", "GLOBAL_DEADLINE"}:
                leftovers = list((root / 'kagi').glob('*.json')) if name == 'kagi' else [root / gather.OUTPUT_FILE[name]]
                if outputs or any(path.exists() or path.is_symlink() for path in leftovers):
                    report["errors"].append(f"{name}: failed source has leftover consumable output")
                report["warnings"].append(f"{name}: source unavailable ({status})")
                continue
            rc, count = entry.get("rc"), entry.get("count")
            if type(rc) is not int or rc != 0 or type(count) is not int or count < 0:
                report["errors"].append(f"{name}: successful status requires rc=0 and nonnegative count")
                continue
            if (status == "OK") != (count > 0):
                report["errors"].append(f"{name}: status/count mismatch")
                continue
            checked = []
            for output in outputs:
                path = _safe_output(root, output.get("path") if isinstance(output, dict) else None)
                digest = output.get("sha256") if isinstance(output, dict) else None
                if path is None:
                    report["errors"].append(f"{name}: unsafe or unknown output path")
                    continue
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    report["errors"].append(f"{name}: missing or invalid output hash")
                    continue
                elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    report["errors"].append(f"{name}: output hash mismatch for {path.name}")
                    continue
                checked.append(path)
            count_actual, paths_or_reason = gather._validate(name, str(root))
            if count_actual is None or count_actual != count:
                report["errors"].append(f"{name}: output schema/count invalid ({paths_or_reason})")
                continue
            expected_paths = {str(p) for p in paths_or_reason}
            listed_paths = {str(p.relative_to(root)) for p in checked}
            if expected_paths != listed_paths:
                report["errors"].append(f"{name}: manifest outputs do not match validated consumed paths")
                continue
            consumed.update(checked)
            successful += status == "OK"
            if status == "EMPTY":
                report["warnings"].append(f"{name}: source completed empty")
        if len(generations) != 1:
            report["errors"].append("manifest entries must share one nonempty generation_id")
        if times and not historical_replay and clock - max(times) > timedelta(hours=24):
            report["errors"].append("current edition provenance is older than 24 hours")
        if not consumed:
            report["errors"].append("no validated source outputs were consumed")
        if not successful:
            report["errors"].append("at least one genuine successful source is required")
        report["counts"].update(consumed_outputs=len(consumed), successful_sources=successful)
        report['provenance_verified'] = not report['errors']
        return report, consumed
    finally:
        os.close(fd)


def _urls(value):
    found = set()
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                for key in ("url", "link", "canonical_url"):
                    if isinstance(row.get(key), str):
                        found.add(row[key])
    return found


def check_lineage(run_dir: str | Path, items, edition: str, *, consumed=None):
    report = _report()
    root = Path(run_dir)
    inputs, project_pairs = set(), {}
    for name, filename in gather.OUTPUT_FILE.items():
        path = root / filename
        if consumed is not None and path not in consumed:
            continue
        if path.exists() and name != "opensource":
            try:
                rows = _read_json(path)
                inputs.update(_urls(rows))
                if name == 'reddit' and isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict) or row.get('subreddit') != PROJECT_SUB:
                            continue
                        for url in row.get('project_urls', []):
                            if isinstance(url, str) and _repo_identity(url):
                                inputs.add(url)
                                project_pairs.setdefault(url, set()).add(row.get('url'))
            except ValueError as exc:
                report["errors"].append(str(exc))
        elif name == "opensource" and path.exists():
            payload = _read_json(path)
            if isinstance(payload, dict):
                for bucket in payload.values():
                    inputs.update(_urls(bucket))
    kagi = root / "kagi"
    if kagi.is_dir():
        for path in kagi.glob("*.json"):
            if consumed is not None and path not in consumed:
                continue
            payload = _read_json(path)
            if isinstance(payload, dict):
                inputs.update(_urls(((payload.get("data") or {}).get("search"))))
    # This checks retained identity, not age. Collection/edition dates are checked
    # separately; re-running a 24h loader at edition midnight would lose valid posts.
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and (item.get('tier') == 'projects' or item.get('discovery_url')):
            if item.get('discovery_url') not in project_pairs.get(item.get('url'), set()):
                report['errors'].append('project/discussion pair is absent from collected discovery input')
        for source in item.get("source_urls", []) if isinstance(item, dict) else []:
            url = source.get("url") if isinstance(source, dict) else None
            if not isinstance(url, str) or url not in inputs:
                report["errors"].append(f"candidate citation is absent from collected inputs: {url!r}")
    report["counts"]["collected_urls"] = len(inputs)
    return report


def _digest_article(html):
    articles = []
    for match in re.finditer(r'<article\b([^>]*)>.*?</article>', html, re.I | re.S):
        attribute = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', match.group(1), re.I | re.S)
        if attribute and 'digest' in attribute.group(2).split():
            articles.append(match.group(0))
    if len(articles) != 1:
        raise ValueError('expected exactly one digest article')
    return articles[0]


def check_docs(docs: str | Path, digest: str | Path, edition: str):
    report = _report()
    docs, digest = Path(docs), Path(digest)
    try:
        from build import render_digest_md
        fragment = render_digest_md(digest.read_text(encoding="utf-8"))
    except Exception as exc:
        report["errors"].append(f"cannot render digest for built-output verification: {exc}")
        return report
    required = [docs / "digests" / f"{edition}.html", docs / "index.html", docs / "feed.xml",
                docs / "atom.xml", docs / "archive.json"]
    text = {}
    for path in required:
        if not path.is_file():
            report["errors"].append(f"missing built surface: {path.name}")
        else:
            text[path.name] = path.read_text(encoding="utf-8")
    if report["errors"]:
        return report
    from build import SITE_URL
    expected_url = f'{SITE_URL}/digests/{edition}.html'
    try:
        daily = _digest_article(text[f'{edition}.html'])
        home = _digest_article(text['index.html'])
        if not daily.removesuffix('</article>').rstrip().endswith(fragment.strip()) or daily != home:
            report['errors'].append('daily/homepage content differs from the validated digest')
        rss = ET.fromstring(text['feed.xml']).findall('./channel/item')
        atom_ns = '{http://www.w3.org/2005/Atom}'
        atom = ET.fromstring(text['atom.xml']).findall(atom_ns + 'entry')
        if not rss or rss[0].findtext('link') != expected_url or rss[0].findtext('guid') != expected_url:
            report['errors'].append('RSS latest entry identity differs from requested edition')
        elif rss[0].findtext('{http://purl.org/rss/1.0/modules/content/}encoded', '').strip() != daily.strip():
            report['errors'].append('RSS latest payload differs from the validated daily article')
        if not atom or atom[0].findtext(atom_ns + 'id') != expected_url:
            report['errors'].append('Atom latest entry identity differs from requested edition')
        else:
            link = atom[0].find(atom_ns + 'link')
            if link is None or link.get('href') != expected_url or atom[0].findtext(atom_ns + 'content', '').strip() != daily.strip():
                report['errors'].append('Atom latest payload/link differs from the validated daily article')
    except (ValueError, ET.ParseError) as exc:
        report['errors'].append(f'invalid built article/feed: {exc}')
    try:
        archive = json.loads(text["archive.json"])
        entries = archive.get("digests", archive) if isinstance(archive, dict) else archive
        if (not isinstance(entries, list) or not entries or not isinstance(entries[0], dict)
                or entries[0].get('slug') != edition
                or sum(isinstance(e, dict) and e.get('slug') == edition for e in entries) != 1):
            report["errors"].append("archive latest entry does not contain the exact unique requested slug")
    except json.JSONDecodeError:
        report["errors"].append("archive.json is malformed")
    report['counts']['built_surfaces'] = len(text)
    return report
