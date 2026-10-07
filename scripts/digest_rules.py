"""Mechanical candidate contracts, not semantic fact-checking."""
from urllib.parse import urlsplit
from market_rules import finite_number
from scoring_policy import score_item

SOCIAL_DOMAINS = {'reddit.com', 'old.reddit.com', 'bsky.app', 'news.ycombinator.com',
                  'x.com', 'twitter.com', 'mastodon.social', 'threads.net'}
TIERS = {'news', 'social', 'research', 'opensource', 'projects'}


def public_url(value):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not (parsed.username or parsed.password)
    except ValueError:
        return False


def domain(value):
    return (urlsplit(value).hostname or '').lower().removeprefix('www.')


def item_errors(items):
    errors = []
    if not isinstance(items, list) or not items:
        return ['candidate input must be a nonempty list']
    seen = set()
    for index, item in enumerate(items, 1):
        tag = f'candidate {index}'
        if not isinstance(item, dict):
            errors.append(f'{tag}: not an object')
            continue
        url = item.get('url')
        if not public_url(url):
            errors.append(f'{tag}: invalid public URL')
            continue
        if url in seen:
            errors.append(f'{tag}: duplicate URL')
        seen.add(url)
        for field in ('title', 'source', 'domain'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f'{tag}: missing {field}')
        if item.get('tier') not in TIERS:
            errors.append(f'{tag}: unknown tier')
        if item.get('domain') != domain(url):
            errors.append(f'{tag}: canonical domain differs from URL')
        bad_number = False
        for field, lo, hi in (('credibility', 1, 5), ('sentiment', -3, 3), ('score', 0, float('inf')),
                              ('source_count', 1, float('inf'))):
            value = item.get(field)
            if not finite_number(value) or not lo <= value <= hi:
                errors.append(f'{tag}: invalid numeric {field}')
                bad_number = True
        if type(item.get('source_count')) is not int or type(item.get('credibility')) is not int:
            errors.append(f'{tag}: credibility/source_count must be integers')
            bad_number = True
        flags = item.get('flags')
        if not isinstance(flags, list) or any(not isinstance(f, str) for f in flags):
            errors.append(f'{tag}: flags must be a list of names')
            continue
        citations = item.get('source_urls')
        if not isinstance(citations, list) or not citations:
            errors.append(f'{tag}: missing citation lineage')
            continue
        cited = []
        for citation in citations:
            if not isinstance(citation, dict) or not public_url(citation.get('url')):
                errors.append(f'{tag}: invalid citation')
                continue
            host = domain(citation['url'])
            cited.append(host)
            if citation.get('domain') != host:
                errors.append(f'{tag}: citation domain differs from URL')
            if item.get('tier') == 'news' and host in SOCIAL_DOMAINS:
                errors.append(f'{tag}: social reaction is not independent news corroboration')
        if len(set(cited)) != len(citations) or set(cited) != set(item.get('source_domains', [])):
            errors.append(f'{tag}: citation/domain membership differs')
        if not bad_number:
            if item['source_count'] != len(set(cited)):
                errors.append(f'{tag}: source_count does not match citations')
            if ('cross_source' in flags) != (item['source_count'] > 1):
                errors.append(f'{tag}: cross_source flag contradicts source_count')
            if item['score'] != score_item(item):
                errors.append(f'{tag}: score contradicts ranking policy')
        if url not in [c.get('url') for c in citations if isinstance(c, dict)]:
            errors.append(f'{tag}: canonical URL missing from citation lineage')
    return errors
