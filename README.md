# AIgregator

Daily AI news digest, scored and cited. Generated each morning at 0700 Pacific by a Hermes agent.

Live site: https://brianbaldock.github.io/AIgregator/

## Architecture

```
cron (Hermes)
  -> writes digests/YYYY-MM-DD.md
  -> runs scripts/build.py (renders docs/*.html)
  -> runs scripts/publish.sh (git commit + push)
  -> GitHub Pages serves docs/
```

## Manual build

```
pip install markdown
python scripts/build.py
```

## Scoring

- 1 to 2: social signal only (X, Reddit, Bluesky)
- 3: aggregator or single-source press
- 4: tier-2 outlet (Ars Technica, The Verge, Wired, named analyst)
- 5: primary source (lab blog, Reuters, AP, FT, Bloomberg)
- 6 to 8: corroboration bonus, +1 per independent reputable source

## Commits

Commits authored by the Hermes agent are prefixed `Hermes:` even though the GitHub author is `brianbaldock`.
