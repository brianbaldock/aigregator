"""Offline checks for normalized prediction markets, shared by intake and render.

Percent fields are percentages, not inferred probabilities. These mechanical
checks do not determine whether a market question is a credible prediction.
"""
from datetime import datetime, timedelta, timezone
import math
import re
from urllib.parse import urlsplit

_MONTH_NAMES = ('january|february|march|april|may|june|july|august|'
                'september|october|november|december')
_QUESTION_DEADLINE = re.compile(
    rf'\b(?:by|before|on|at (?:the )?end of)\s+({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?[, ]+((?:19|20)\d{{2}})\b', re.I)
_QUESTION_MONTH_END = re.compile(
    rf'\b(?:by|before|at (?:the )?end of)\s+({_MONTH_NAMES})\s+((?:19|20)\d{{2}})\b', re.I)


def has_embedded_markup(text: str) -> bool:
    # Input prose never supplies HTML or its own inline/reference citation links.
    return bool(re.search(r'<(?:/?[A-Za-z]|!--)|\]\s*[\[(]|\[[^\]]+\]:\s*\S', text))


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _api_deadline_has_passed(value, now):
    if value is None or value == '':
        return False
    if not isinstance(value, str):
        return True
    raw = value.strip()
    try:
        if 'T' in raw:
            parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc) <= now
        return datetime.strptime(raw, '%Y-%m-%d').date() < now.date()
    except ValueError:
        return True  # present but malformed dates cannot certify freshness


def _question_deadline_has_passed(question, now):
    if not isinstance(question, str):
        return False
    match = _QUESTION_DEADLINE.search(question)
    if match:
        try:
            deadline = datetime.strptime(
                f'{match.group(1)} {match.group(2)} {match.group(3)}', '%B %d %Y').date()
            return deadline < now.date()
        except ValueError:
            return False
    match = _QUESTION_MONTH_END.search(question)
    if match:
        try:
            month_start = datetime.strptime(f'{match.group(1)} 1 {match.group(2)}', '%B %d %Y').date()
            next_month = (month_start.replace(year=month_start.year + 1, month=1)
                          if month_start.month == 12 else month_start.replace(month=month_start.month + 1))
            return next_month - timedelta(days=1) < now.date()
        except ValueError:
            return False
    return False


def market_is_current(market, event, now=None):
    now = now or datetime.now(timezone.utc)
    for record in (market, event):
        if not isinstance(record, dict):
            return False
        if any(key in record and type(record[key]) is not bool
               for key in ('closed', 'active', 'acceptingOrders')):
            return False
        if record.get('closed') is True or record.get('active') is False:
            return False
        if record.get('acceptingOrders') is False:
            return False
        for key in ('endDate', 'endDateIso', 'umaEndDate'):
            if _api_deadline_has_passed(record.get(key), now):
                return False
    return not _question_deadline_has_passed(market.get('question') or event.get('title'), now)


def market_issue(market, now=None):
    """Return an omission reason, or None for a mechanically valid record."""
    if not isinstance(market, dict):
        return 'record is not an object'
    for key in ('question', 'url'):
        value = market.get(key)
        if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
            return f'invalid {key}'
    if has_embedded_markup(market['question']):
        return 'invalid question (embedded markup)'
    try:
        url = urlsplit(market['url'])
        if (url.scheme != 'https' or url.hostname not in ('polymarket.com', 'www.polymarket.com')
                or url.username or url.password or url.port or not url.path.startswith('/event/')
                or url.path == '/event/'):
            return 'not a public Polymarket event URL'
    except ValueError:
        return 'invalid market URL'
    for key, lo, hi in (('yes_pct', 0, 100), ('change_24h_pp', -100, 100), ('volume_usd', 0, math.inf)):
        value = market.get(key)
        if not finite_number(value) or not lo <= value <= hi:
            return f'invalid {key} (explicit numeric units required)'
    if 'market_id' in market and (type(market['market_id']) not in (str, int) or market['market_id'] == ''):
        return 'invalid market identity'
    if not market_is_current(market, market.get('event', {}), now):
        return 'closed, inactive, or expired market'
    return None


def filter_markets(data, now=None, limit=5):
    """Select valid optional records once, returning visible omission reasons."""
    if not isinstance(data, list):
        return [], ['market input is not a list']
    kept, issues, seen = [], [], set()
    for index, market in enumerate(data):
        issue = market_issue(market, now)
        if issue:
            issues.append(f'market {index + 1}: {issue}')
            continue
        identity = market.get('market_id') or (market['url'], market['question'])
        if identity in seen:
            issues.append(f'market {index + 1}: duplicate')
            continue
        seen.add(identity)
        kept.append(market)
    return kept[:limit], issues
