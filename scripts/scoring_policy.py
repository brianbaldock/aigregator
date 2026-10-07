"""Shared ranking arithmetic. Scores rank coverage; they are not truth probabilities."""
BASE_WEIGHT = 2
CORROBORATION_BONUS = 3
WIRE_SEARCH_BONUS = 1
UNDATED_PENALTY = 3
WIRE_DOMAINS = frozenset({'reuters.com', 'apnews.com', 'bloomberg.com', 'wsj.com'})


def score_item(item):
    score = item['credibility'] * BASE_WEIGHT + max(0, item['source_count'] - 1) * CORROBORATION_BONUS
    if item.get('via_kagi') and item['domain'] in WIRE_DOMAINS:
        score += WIRE_SEARCH_BONUS
    if 'undated' in item.get('flags', []):
        score = max(0, score - UNDATED_PENALTY)
    return score
