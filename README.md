# Weekly AI World Summary

[![Live Site](https://img.shields.io/badge/site-github_pages-blue.svg)](https://govindarajanv.github.io/AgentWire/)
[![Version](https://img.shields.io/badge/version-v1.0.0-green.svg)](https://github.com/govindarajanv/AgentWire)
[![Workflow](https://github.com/govindarajanv/AgentWire/actions/workflows/digest.yml/badge.svg)](https://github.com/govindarajanv/AgentWire/actions/workflows/digest.yml)

Automated weekly summary and curated intelligence of major developments happening in the AI world, published as a GitHub Pages static site using the free [Kilo Gateway](https://kilo.ai/) inference action ([`govindarajanv/inference`](https://github.com/govindarajanv/inference)).

- **Live Site:** [https://govindarajanv.github.io/AgentWire/](https://govindarajanv.github.io/AgentWire/)
- **Schedule:** Runs every **Sunday at 09:00 AM IST** (`30 3 * * 0` UTC)
- **On-Demand:** Triggerable anytime via GitHub Actions `workflow_dispatch`
- **Inference Engine:** Powered by free tier models on Kilo Gateway via `govindarajanv/inference@v1`
- **Rolling Archive:** Maintains the latest edition plus up to 6 prior weekly editions

---

## How It Works

1. **Ingestion (`topics.yaml`):** Collects news, releases, arXiv preprints, and GitHub updates from the past 7 days across frontier AI, LLMs, and autonomous agents.
2. **AI Synthesis (`govindarajanv/inference`):** Generates an editorial Weekly AI World Summary synthesized into Executive Overview, Frontier Models, Autonomous Agents, Research Breakthroughs, and Industry Trends using free Kilo Gateway models (`kilo-auto/free` with automatic fallback chain).
3. **Resilience & Graceful Fallback:** Operates with `fail_on_error: false`. If rate limits occur or the AI gateway is throttled, the workflow gracefully completes with an automated rule-based synthesis without interrupting publishing.
4. **Publishing & Rotation:** Publishes the weekly edition to `index.md`, displays the live version badge (`v1.0.0`), and shifts previous editions into rolling archives (`archive-1.md` through `archive-6.md`).
5. **Static Deployment:** Deploys static HTML via Jekyll to GitHub Pages.

---

## Configuration

- `topics.yaml` — Source definitions for keywords, feeds, arXiv subject queries, and tracked GitHub repositories.
- `claude.md` — Single source of truth (SSOT) defining schemas, versioning conventions, and runtime contracts.
- `antigravity.md` — Agent-specific configuration inheriting from `claude.md`.
- `.github/workflows/digest.yml` — GitHub Actions workflow configuration.

---

## Local Usage

Run the full pipeline locally (uses Kilo Gateway free tier with fallback):

```bash
python scripts/digest.py
```

Prepare the prompt for AI inference only:

```bash
python scripts/digest.py --prepare-prompt --days 7
```

Render `index.md` from an existing summary file:

```bash
python scripts/digest.py --render --summary-file ai_summary.md
```

Deterministic preview for a specific date:

```bash
python scripts/digest.py --now 2026-09-20T03:30:00Z --days 7
```
