#!/usr/bin/env python3
"""Validate a weekly handoff and import its local review-only SimplePost packet."""
import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


MAX_HANDOFF_BYTES = 16 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_COPY_BYTES = 4096
MAX_PDF_BYTES = 20 * 1024 * 1024
VAULT_GIT_TIMEOUT = 60
VAULT_INDEX_NAME = "AIGregator Weekly.md"
DEFAULT_VAULT_REL = "Projects/LinkedIn Posts/AIgregator Weekly"
# A plain branch ref, never an option: the ref is spliced into `git show <ref>:<path>`.
VAULT_REF = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._/-]*")
WEEK = re.compile(r"^[0-9]{4}-W[0-9]{2}$")
PLATFORMS = ("linkedin", "bluesky", "x")


class HandoffError(Exception):
    pass


def fail(message):
    print("simplepost weekly handoff: %s" % message, file=sys.stderr)
    return 1


def regular_file(path, label):
    try:
        if not path.is_file() or path.is_symlink():
            raise HandoffError("%s must be a regular file" % label)
    except OSError as error:
        raise HandoffError("cannot inspect %s" % label) from error


def load_handoff(path, now):
    regular_file(path, "handoff")
    if path.stat().st_size > MAX_HANDOFF_BYTES:
        raise HandoffError("handoff exceeds byte limit")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HandoffError("handoff is malformed JSON") from error
    required = {"status", "slug", "url", "written_at", "detail"}
    if not isinstance(data, dict) or set(data) != required or not all(isinstance(data[key], str) for key in required):
        raise HandoffError("handoff has invalid fields")
    if data["status"] == "FAIL":
        raise HandoffError("weekly build failed: %s" % data["detail"])
    if data["status"] not in ("OK", "SKIP"):
        raise HandoffError("handoff has invalid status")
    if not WEEK.fullmatch(data["slug"]):
        raise HandoffError("handoff has invalid weekly slug")
    try:
        year, week = data["slug"].split("-W")
        datetime.fromisocalendar(int(year), int(week), 1)
    except ValueError as error:
        raise HandoffError("handoff weekly slug is not real") from error
    expected_url = "https://aigregator.news/weekly/%s.html" % data["slug"]
    if data["url"] != expected_url:
        raise HandoffError("handoff URL does not match weekly slug")
    try:
        written = datetime.fromisoformat(data["written_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise HandoffError("handoff has invalid written_at") from error
    if written.tzinfo is None:
        raise HandoffError("handoff written_at must include timezone")
    age = now - written.astimezone(timezone.utc)
    if age < timedelta(0):
        raise HandoffError("handoff is from the future")
    if age > timedelta(hours=12):
        raise HandoffError("handoff is stale")
    return data


def artifact_paths(work, slug):
    return {
        platform: work / ("%s-%s.txt" % (slug, platform))
        for platform in PLATFORMS
    } | {"pdf": work / ("%s-carousel.pdf" % slug)}


def vault_git(vault_dir, *args, timeout=VAULT_GIT_TIMEOUT):
    command = ["git", "-C", str(vault_dir), *args]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    process = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise HandoffError("vault git %s timed out after %ss" % (args[0], timeout))
    if process.returncode:
        raise HandoffError("vault git %s failed: %s" % (args[0], stderr.decode("utf-8", "replace").strip()))
    return stdout


def verify_vault_bundle(vault_dir, vault_rel, vault_ref, slug, url, paths):
    """Prove the edition bundle is on the vault REMOTE, byte-exact, and return its commit.

    The social worker is an LLM: prose cannot make a half-finished vault sync exit
    nonzero, and a staged-but-unpushed bundle is invisible to every other device.
    So read the remote-tracking ref after a fresh fetch, never the local worktree.
    """
    if not VAULT_REF.fullmatch(vault_ref):
        raise HandoffError("vault ref is not a plain branch ref")
    if not vault_dir.is_dir():
        raise HandoffError("vault directory is unavailable")
    vault_git(vault_dir, "fetch", "--quiet", "origin")
    base = vault_rel.strip("/")

    def blob(name):
        try:
            return vault_git(vault_dir, "show", "%s:%s/%s" % (vault_ref, base, name))
        except HandoffError as error:
            raise HandoffError("%s is missing from the vault: %s" % (name, error)) from error

    reviewed_pdf = read_bounded(paths["pdf"], MAX_PDF_BYTES, "pdf artifact")
    if hashlib.sha256(blob("%s-carousel.pdf" % slug)).digest() != hashlib.sha256(reviewed_pdf).digest():
        raise HandoffError("vault carousel PDF differs from the reviewed artifact")
    if blob("%s-linkedin.md" % slug) != read_bounded(paths["linkedin"], MAX_COPY_BYTES, "linkedin artifact"):
        raise HandoffError("vault LinkedIn copy differs from the reviewed artifact")
    edition = blob("%s.md" % slug).decode("utf-8", "replace")
    if ("\nedition: %s\n" % slug) not in edition or url not in edition:
        raise HandoffError("vault edition note lacks its edition slug or published URL")
    index = blob(VAULT_INDEX_NAME).decode("utf-8", "replace")
    if index.count("[[%s/%s|%s]]" % (base, slug, slug)) != 1:
        raise HandoffError("vault weekly index must link %s exactly once" % slug)
    return vault_git(vault_dir, "rev-parse", "--short", vault_ref).decode("utf-8").strip()


def verify_vault(args, handoff, paths, imported=False):
    if args.vault_dir is None:
        return {}
    try:
        commit = verify_vault_bundle(
            args.vault_dir, args.vault_rel, args.vault_ref, handoff["slug"], handoff["url"], paths
        )
    except HandoffError as error:
        lead = "review cards were imported, but " if imported else ""
        raise HandoffError("%sthe vault bundle is not verified on %s: %s" % (lead, args.vault_ref, error)) from error
    return {"vault": commit}


def read_bounded(path, limit, label):
    regular_file(path, label)
    try:
        if path.stat().st_size > limit:
            raise HandoffError("%s exceeds byte limit" % label)
        raw = path.read_bytes()
    except OSError as error:
        raise HandoffError("cannot read %s" % label) from error
    if len(raw) > limit:
        raise HandoffError("%s exceeds byte limit" % label)
    return raw


def artifacts_complete(paths):
    try:
        for name, path in paths.items():
            limit = MAX_PDF_BYTES if name == "pdf" else MAX_COPY_BYTES
            if not read_bounded(path, limit, name + " artifact"):
                return False
    except HandoffError:
        return False
    return True


def validate_locked_artifacts(paths, handoff):
    expected_linkedin = "Latest AI Weekly Roundup just dropped → %s\n" % handoff["url"]
    try:
        copies = {
            platform: read_bounded(paths[platform], MAX_COPY_BYTES, platform + " artifact").decode("utf-8")
            for platform in PLATFORMS
        }
        linkedin = copies["linkedin"]
    except UnicodeDecodeError as error:
        raise HandoffError("cannot read prepared copy") from error
    if linkedin != expected_linkedin:
        raise HandoffError("LinkedIn copy does not match the locked one-line format")
    if any("\u2013" in copy or "\u2014" in copy for copy in copies.values()):
        raise HandoffError("prepared copy contains an en or em dash")


def run_bounded(command, cwd, env, timeout, label):
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True, start_new_session=True)
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise HandoffError("%s timed out after %ss" % (label, timeout))
    if returncode:
        raise HandoffError("%s exited %d" % (label, returncode))


def run_bounded_capture(command, cwd, timeout, label):
    process = subprocess.Popen(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        raise HandoffError("%s timed out after %ss" % (label, timeout))
    if process.returncode:
        raise HandoffError("%s failed: %s" % (label, stderr.strip()))
    return stdout


def run_worker(args, handoff, source):
    env = os.environ.copy()
    env.update({
        "AIG_WEEKLY_WORK_DIR": str(args.work_dir.resolve()),
        "AIG_WEEKLY_SLUG": handoff["slug"],
        "AIG_WEEKLY_URL": handoff["url"],
        "AIG_WEEKLY_SOURCE": str(source),
    })
    command = [args.worker, *args.worker_arg]
    run_bounded(command, args.repo_root, env, args.worker_timeout, "worker")


def run_producer(args, handoff, paths):
    packet_id = "aigregator-%s-v1" % handoff["slug"]
    command = [
        args.python, "-m", "simplepost.producer",
        "--packet-id", packet_id, "--x", str(paths["x"]),
        "--bluesky", str(paths["bluesky"]), "--linkedin", str(paths["linkedin"]),
        "--pdf", str(paths["pdf"]), "--pdf-title", "AI Weekly Roundup | %s" % handoff["slug"],
        "--weekly-slug", handoff["slug"], "--output", str(args.output),
        "--root", str(args.review_root),
    ]
    stdout = run_bounded_capture(command, args.producer_cwd, args.producer_timeout, "producer")
    try:
        return json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise HandoffError("producer returned malformed result") from error


def readback(review_root, packet_id, paths, slug):
    db = review_root / "state.sqlite3"
    regular_file(db, "review database")
    try:
        expected = {
            platform: read_bounded(paths[platform], MAX_COPY_BYTES, platform + " artifact").decode("utf-8")
            for platform in PLATFORMS
        }
    except UnicodeDecodeError as error:
        raise HandoffError("cannot read prepared copy") from error
    pdf = read_bounded(paths["pdf"], MAX_PDF_BYTES, "pdf artifact")
    digest = hashlib.sha256(pdf).hexdigest()
    try:
        with sqlite3.connect("file:%s?mode=ro" % db.resolve().as_posix(), uri=True) as connection:
            cards = connection.execute(
                """SELECT platform, state, content, document_path, document_filename, document_title, document_sha256
                   FROM cards WHERE packet_id=? ORDER BY platform""", (packet_id,)
            ).fetchall()
            jobs = connection.execute("SELECT COUNT(*) FROM jobs WHERE packet_id=?", (packet_id,)).fetchone()[0]
    except sqlite3.Error as error:
        raise HandoffError("cannot read review database") from error
    if len(cards) != len(PLATFORMS) or any(row[0] not in expected or row[1] != "review" or row[2] != expected[row[0]] for row in cards):
        raise HandoffError("review readback is not exactly three unapproved cards")
    linked_in = next(row for row in cards if row[0] == "linkedin")
    if linked_in[4:] != ("%s-carousel.pdf" % slug, "AI Weekly Roundup | %s" % slug, digest):
        raise HandoffError("review readback PDF does not match locked artifact")
    try:
        stored_digest = hashlib.sha256(read_bounded(Path(linked_in[3]), MAX_PDF_BYTES, "stored PDF asset")).hexdigest()
    except TypeError as error:
        raise HandoffError("review readback has no stored PDF asset") from error
    if stored_digest != digest:
        raise HandoffError("review readback stored PDF bytes do not match locked artifact")
    if any(row[4] is not None for row in cards if row[0] != "linkedin"):
        raise HandoffError("review readback attached PDF to the wrong platform")
    if jobs:
        raise HandoffError("review readback found scheduled jobs")
    return len(cards), jobs


def existing_packet(review_root, packet_id, weekly_url):
    db = review_root / "state.sqlite3"
    if not db.exists():
        return None
    regular_file(db, "review database")
    try:
        with sqlite3.connect("file:%s?mode=ro" % db.resolve().as_posix(), uri=True) as connection:
            rows = connection.execute(
                "SELECT packet_id, state FROM cards WHERE instr(content, ?) > 0", (weekly_url,)
            ).fetchall()
            jobs = connection.execute("SELECT COUNT(*) FROM jobs WHERE packet_id=?", (packet_id,)).fetchone()[0]
    except sqlite3.Error as error:
        raise HandoffError("cannot read review database") from error
    if not rows:
        return None
    ids = {row[0] for row in rows}
    if ids != {packet_id}:
        raise HandoffError("weekly edition is already represented by %s" % sorted(ids)[0])
    if len(rows) != len(PLATFORMS) or any(row[1] != "review" for row in rows) or jobs:
        raise HandoffError("existing edition requires manual reconciliation")
    return {"id": packet_id, "imported": False, "cards": len(rows), "jobs": jobs}


def prepare_workspace(workspace, slug):
    try:
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(workspace, 0o700)
    except OSError as error:
        raise HandoffError("cannot create private workspace") from error
    if not workspace.is_dir() or workspace.is_symlink():
        raise HandoffError("workspace must be a directory")
    return workspace / ("%s.json" % slug)


def write_manifest(workspace, slug, source, paths):
    manifest = workspace / ("%s.manifest.json" % slug)
    payload = {
        "slug": slug,
        "source_sha256": hashlib.sha256(read_bounded(source, MAX_SOURCE_BYTES, "weekly source")).hexdigest(),
        "artifacts": {
            name: hashlib.sha256(read_bounded(path, MAX_PDF_BYTES if name == "pdf" else MAX_COPY_BYTES, name + " artifact")).hexdigest()
            for name, path in paths.items()
        },
    }
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        if manifest.exists():
            if manifest.read_text(encoding="utf-8") != rendered:
                raise HandoffError("existing completion manifest conflicts with prepared artifacts")
            return
        with manifest.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    except OSError as error:
        raise HandoffError("cannot record completion manifest") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--review-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--producer-cwd", required=True, type=Path)
    parser.add_argument("--python", required=True)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--worker-arg", action="append", default=[])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker-timeout", type=int, default=1800)
    parser.add_argument("--producer-timeout", type=int, default=60)
    parser.add_argument("--vault-dir", type=Path, help="enable the vault-remote gate for this Obsidian vault")
    parser.add_argument("--vault-rel", default=DEFAULT_VAULT_REL)
    parser.add_argument("--vault-ref", default="origin/main")
    args = parser.parse_args(argv)
    try:
        args.repo_root = args.repo_root.resolve()
        args.producer_cwd = args.producer_cwd.resolve()
        if not args.repo_root.is_dir() or not args.producer_cwd.is_dir() or not args.source_dir.is_dir():
            raise HandoffError("configured working directory is unavailable")
        if not args.work_dir.is_dir():
            raise HandoffError("work directory is unavailable")
        if not 0 < args.worker_timeout <= 1800 or not 0 < args.producer_timeout <= 60:
            raise HandoffError("configured timeout is outside allowed bounds")
        handoff = load_handoff(args.handoff, datetime.now(timezone.utc))
        source = args.source_dir / (handoff["slug"] + ".md")
        read_bounded(source, MAX_SOURCE_BYTES, "weekly source")
        packet_id = "aigregator-%s-v1" % handoff["slug"]
        paths = artifact_paths(args.work_dir, handoff["slug"])
        existing = existing_packet(args.review_root, packet_id, handoff["url"])
        if existing:
            # A replay is also the cheap way to re-verify: the vault gate still runs.
            existing.update(verify_vault(args, handoff, paths))
            print(json.dumps(existing, sort_keys=True))
            return 0
        # Artifacts alone cannot attest vault preflight/sync or source freshness.
        # Run the bounded worker unless the review store already proves this edition.
        run_worker(args, handoff, source)
        if not artifacts_complete(paths):
            missing = next(name for name, path in paths.items() if not path.is_file() or path.stat().st_size == 0)
            raise HandoffError("missing required artifact: %s" % missing)
        validate_locked_artifacts(paths, handoff)
        args.output = prepare_workspace(args.workspace, handoff["slug"])
        write_manifest(args.workspace, handoff["slug"], source, paths)
        result = run_producer(args, handoff, paths)
        cards, jobs = readback(args.review_root, result["id"], paths, handoff["slug"])
        report = {"id": result["id"], "imported": result["imported"], "cards": cards, "jobs": jobs}
        report.update(verify_vault(args, handoff, paths, imported=True))
    except HandoffError as error:
        return fail(str(error))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
