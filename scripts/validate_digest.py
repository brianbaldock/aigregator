#!/usr/bin/env python3
"""Offline final-artifact checks. This does not prove claims or event equivalence."""
import copy
import argparse
import json
import os
import re
import sys

from curate import validate
from datetime import datetime, timezone
from pathlib import Path
from write_digest import (select_items, SECTION_HEADERS, SECTION_ORDER, signed,
                          render_news_item, render_research_item, render_discourse, section_stats_line,
                          dashboard_line, extract_top_mention, read_prior_sentiments, source_health_note, render_market_section)
from market_rules import filter_markets
from run_dir import run_dir_default


def links(text):
    return re.findall(r'\[[^\]\n]*\]\((https?://[^\s)]+)\)', text)


def mean_sentiment(items):
    weight = sum(item['credibility'] for item in items)
    return sum(item['sentiment'] * item['credibility'] for item in items) / weight if weight else 0


def check_row(row, item, errors, label, *, tldr=False):
    expected_urls = [s['url'] for s in item['source_urls']]
    if tldr:
        expected_urls = expected_urls[:4]
    found = links(row)
    if item.get('discovery_url') and not tldr:
        expected_urls.append(item['discovery_url'])
    if found != expected_urls:
        errors.append(f'{label}: citation identity/order differs from selected record')
    score = re.match(r'(?:- |\d+\. )(\d+)\s', row)
    if not score or int(score.group(1)) != item['score']:
        errors.append(f'{label}: rendered score differs from selected record')
    if not tldr and item['tier'] != 'research':
        badge = re.search(r'▤×(\d+)', row)
        actual = int(badge.group(1)) if badge else 1
        if actual != item['source_count']:
            errors.append(f'{label}: rendered source badge differs from citations')


LIMITATIONS = 'Checks structure, arithmetic and retained citation identity, not claim support, relevance or event equivalence.'


def validate_artifact(items, curation, markets, markdown, edition, *, now=None, prior_sentiments=None, source_manifest=None, market_issues=None):
    """Compare a rendered artifact with its actual selected input records."""
    cleaned, warnings, errors = validate(copy.deepcopy(curation), items)
    result = {'errors': errors, 'warnings': warnings, 'counts': {'candidates': len(items) if isinstance(items, list) else 0},
              'limitations': LIMITATIONS}
    if errors:
        return result
    sections = select_items(items, cleaned)
    news = [item for section in SECTION_ORDER for item in sections.get(section, []) if item['tier'] == 'news']
    domains = {source for item in news for source in item['source_domains']}
    cross = sum(item['source_count'] > 1 for item in news)
    match = re.search(r'^> \*\*📊 TODAY:\*\* (\d+) stories · (\d+) sources .*?🔥 (\d+) cross-source', markdown, re.M)
    if not match or tuple(map(int, match.groups())) != (len(news), len(domains), cross):
        errors.append('dashboard story/source/cross-source counts differ from selected records')
    result['counts'].update(news=len(news), sources=len(domains), cross_source=cross)
    if not markdown.startswith(f'# {edition} :: AI DAILY DIGEST\n'):
        errors.append('edition heading does not match requested date')
    if re.search(r'\b(?:None|NaN|Inf(?:inity)?)\s*(?:%|pp)\b', markdown, re.I):
        errors.append('non-numeric placeholder in rendered artifact')
    today = next((line for line in markdown.splitlines() if line.startswith('> **📊 TODAY:')), '')
    if f'{signed(mean_sentiment(news))} sentiment' not in today:
        errors.append('dashboard sentiment differs from selected records')

    expected_headers = ['## ⚡ TL;DR'] + [SECTION_HEADERS[s] for s in SECTION_ORDER] + ['## 📈 Prediction Markets', '## 💬 Discourse']
    headers = re.findall(r'^## .*$', markdown, re.M)
    if headers != expected_headers:
        errors.append('section headings missing, repeated, out of order, or unexpected')
    blocks, header = {}, None
    for line in markdown.splitlines():
        if line.startswith('## '):
            header = line
            blocks.setdefault(header, [])
        elif header:
            blocks[header].append(line)
    rendered = 0
    for section in SECTION_ORDER:
        content = blocks.get(SECTION_HEADERS[section], [])
        rows = [line for line in content if line.startswith('- ')]
        expected = sections.get(section, [])
        formatter = render_research_item if section == 'research' else render_news_item
        expected_lines = [section_stats_line(expected)] + [formatter(item, cleaned['items'][item['url']]) for item in expected]
        if [line for line in content if line.strip()] != expected_lines:
            errors.append(f'{section}: text/rows differ from the validated curation and final selection')
        rendered += len(rows)
        if len(rows) != len(expected):
            errors.append(f'{section}: body row count differs from final selection')
        stats = [line for line in content if line.startswith('_')]
        if expected:
            count = re.search(r'^_(\d+) items? ·', stats[0]) if stats else None
            if not count or int(count.group(1)) != len(rows):
                errors.append(f'{section}: section count differs from rows')
            if not stats or f'{signed(mean_sentiment(expected))} sentiment_' not in stats[0]:
                errors.append(f'{section}: section sentiment differs from selected records')
        elif stats != ['_(quiet today)_']:
            errors.append(f'{section}: empty section must be explicitly quiet')
        for row, item in zip(rows, expected):
            check_row(row, item, errors, section)

    tldr_rows = [line for line in blocks.get('## ⚡ TL;DR', []) if line.strip()]
    tldr = cleaned['tldr_order']
    by_url = {item['url']: item for item in items}
    body_urls = {item['url'] for pool in sections.values() for item in pool}
    if len(tldr_rows) != len(tldr):
        errors.append('TLDR row count differs from chosen URLs')
    for rank, (row, url) in enumerate(zip(tldr_rows, tldr), 1):
        if not row.startswith(f'{rank}. ') or url not in body_urls:
            errors.append('TLDR order or body inclusion is inconsistent')
        check_row(row, by_url[url], errors, 'TLDR', tldr=True)
        expected_tldr = f"{rank}. {render_news_item(by_url[url], cleaned['items'][url], in_tldr=True)}"
        if row != expected_tldr:
            errors.append('TLDR text differs from validated curation')

    clock = now or datetime.now(timezone.utc)
    if edition != clock.date().isoformat():
        clock = datetime.fromisoformat(edition).replace(tzinfo=timezone.utc)
    accepted_markets, omissions = filter_markets(markets, clock)
    if market_issues is not None:
        omissions = list(market_issues) + omissions
    themes = [theme for section in SECTION_ORDER for item in sections.get(section, [])
              for theme in cleaned['items'][item['url']]['themes']]
    top_mover = max(accepted_markets, key=lambda m: abs(m['change_24h_pp']), default=None)
    expected_intro = [f'# {edition} :: AI DAILY DIGEST', f"_{cleaned['subtitle']}_"]
    expected_intro.extend(dashboard_line(news, themes, extract_top_mention(news, cleaned['items']),
                                        cross, prior_sentiments or [], mean_sentiment(news),
                                        has_polymarket=bool(accepted_markets), top_mover=top_mover,
                                        n_markets=len(accepted_markets)))
    coverage_note = source_health_note(source_manifest)
    if coverage_note:
        expected_intro.append(coverage_note)
    actual_intro = [line for line in markdown.split('## ⚡ TL;DR', 1)[0].splitlines() if line.strip()]
    if actual_intro != expected_intro:
        errors.append('dashboard/intro text differs from validated inputs (including themes, mentions and supplied history)')
    result['counts']['history_days'] = len(prior_sentiments or [])
    market_block = blocks.get('## 📈 Prediction Markets', [])
    if [line for line in market_block if line.strip()] != render_market_section(accepted_markets, bool(omissions)):
        errors.append('market section text differs from validated market inputs')
    market_rows = [line for line in market_block if line.startswith('- ')]
    if len(market_rows) != len(accepted_markets):
        errors.append('market rows differ from valid current market selection')
    if accepted_markets:
        counts = [line for line in market_block if re.match(r'^_\d+ markets', line)]
        if counts != [f'_{len(market_rows)} markets · AI/policy_']:
            errors.append('market section count differs from displayed markets')
        pulse = next((line for line in markdown.splitlines() if line.startswith('> **📈 MARKET PULSE:')), '')
        if f'{len(market_rows)} AI markets tracked' not in pulse:
            errors.append('dashboard market count differs from displayed markets')
    if omissions and not any('omitted' in line for line in market_block):
        errors.append('omitted optional markets are not disclosed')
    for row, market in zip(market_rows, accepted_markets):
        if f"**{market['question']}**" not in row or links(row) != [market['url']]:
            errors.append('market question/citation differs from valid input')
        if f"{market['yes_pct']:g}% Yes" not in row:
            errors.append('market probability differs from explicit percentage input')
        delta = market['change_24h_pp']
        arrow = '▲' if delta > 0 else '▼' if delta < 0 else '→'
        if f'({arrow}{abs(delta)}pp 24h' not in row:
            errors.append('market movement differs from input')
        vol = market['volume_usd']
        volume = f'${vol/1_000_000:.1f}M' if vol >= 1_000_000 else f'${vol/1_000:.0f}K' if vol >= 1_000 else f'${vol:.0f}'
        if f'{volume} vol)' not in row:
            errors.append('market volume differs from input')

    social = sections.get('discourse', [])
    expected_social = render_discourse(social, cleaned['items']).strip() if social else '_(quiet today)_'
    if '\n'.join(blocks.get('## 💬 Discourse', [])).strip() != expected_social:
        errors.append('Discourse text differs from validated curation')
    social_rows = [line for line in blocks.get('## 💬 Discourse', []) if line.startswith('- ')]
    expected_social_urls = {item['url'] for item in social}
    social_urls = [url for row in social_rows for url in links(row)]
    if len(social_urls) != len(social) or set(social_urls) != expected_social_urls:
        errors.append('Discourse rows differ from selected social records')
    result['counts'].update(body_rows=rendered, social=len(social_rows), markets=len(market_rows), tldr=len(tldr_rows),
                            selected=len(body_urls), explicit_exclusions=len(cleaned.get('exclusions', {})),
                            unselected_overlays=len(cleaned['items']) - len(body_urls))
    result['warnings'].extend(omissions)
    return result


def _load_json(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} ({path}): {exc}") from exc


def _merge_reports(*reports):
    merged = {"errors": [], "warnings": [], "counts": {}, "limitations": []}
    for report in reports:
        merged["errors"].extend(report.get("errors", []))
        merged["warnings"].extend(report.get("warnings", []))
        merged["counts"].update(report.get("counts", {}))
        limits = report.get('limitations', [])
        merged['limitations'].extend([limits] if isinstance(limits, str) else limits)
        if 'provenance_verified' in report:
            merged['provenance_verified'] = report['provenance_verified']
    return merged


def main():
    parser = argparse.ArgumentParser(description="Offline final publication validation.")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--run-dir", default=run_dir_default())
    parser.add_argument("--digest")
    parser.add_argument("--docs")
    parser.add_argument("--report")
    parser.add_argument("--historical-replay", action="store_true")
    args = parser.parse_args()
    from publication_checks import check_docs, check_lineage, check_provenance

    digest = args.digest or os.path.join(os.path.dirname(os.path.dirname(__file__)), "digests", f"{args.date}.md")
    reports = []
    try:
        items = _load_json(os.path.join(args.run_dir, "digest_items.json"), "digest items")
        curation = _load_json(os.path.join(args.run_dir, "curation.json"), "curation")
        markets_path = os.path.join(args.run_dir, "polymarket.json")
        market_issues = None
        if os.path.exists(markets_path):
            markets = _load_json(markets_path, "markets")
        else:
            markets = []
            market_issues = ['market data unavailable']
            reports.append({"errors": [], "warnings": ["polymarket input unavailable; omission disclosure is required"],
                            "counts": {}, "limitations": []})
        if not isinstance(items, list) or not isinstance(curation, dict) or not isinstance(markets, list):
            raise ValueError("digest inputs have invalid JSON schema")
        with open(digest, encoding="utf-8") as fh:
            markdown = fh.read()
        provenance, consumed = check_provenance(args.run_dir, args.date, historical_replay=args.historical_replay)
        source_manifest = _load_json(os.path.join(args.run_dir, 'gather_manifest.json'), 'source manifest')
        artifact = validate_artifact(items, curation, markets, markdown, args.date,
                                     prior_sentiments=read_prior_sentiments(
                                         Path(__file__).resolve().parents[1] / 'digests', args.date),
                                     source_manifest=source_manifest, market_issues=market_issues)
        reports.extend((provenance, artifact))
        if not artifact['errors'] and not provenance['errors']:
            reports.append(check_lineage(args.run_dir, items, args.date, consumed=consumed))
        if args.docs:
            reports.append(check_docs(args.docs, digest, args.date))
    except (OSError, ValueError) as exc:
        reports.append({"errors": [str(exc)], "warnings": [], "counts": {}, "limitations": []})
    report = _merge_reports(*reports)
    if args.report:
        temporary = f"{args.report}.tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, args.report)
    print(f"examined: {report['counts']}")
    for limitation in dict.fromkeys(report["limitations"]):
        print(f"limitation: {limitation}")
    for warning in report['warnings']:
        print(f'WARNING: {warning}', file=sys.stderr)
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
