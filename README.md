# AI Agents & LLM Digest

Automated daily digest of AI, LLM, and agent news built with a rolling archive pipeline.

- **Live site:** https://govindarajanv.github.io/AgentWire/
- **Schedule:** Runs daily via GitHub Actions
- **Archive:** Keeps the latest digest plus up to 6 rolling archives

## How it works

1. `topics.yaml` defines keywords, feeds, arXiv queries, and GitHub repos to track.
2. `scripts/digest.py` fetches new items within the time window since the last run.
3. Results are deduplicated, rendered, and published to `index.md`.
4. Older pages shift into `archive-1.md` through `archive-6.md`, with `archive-6.md` dropped.

## Configuration

- `claude.md` — single source of truth for schemas, style, and runtime rules.
- `antigravity.md` — agent-specific override that inherits from `claude.md`.

## Usage

The digest is generated automatically by the GitHub Actions workflow.

To run locally:

```bash
python scripts/digest.py
```

To preview with a fixed timestamp:

```bash
python scripts/digest.py --now 2026-09-08T13:00:00Z
```
