# Weekly AI World Summary SSOT

This file is the single source of truth for the Weekly AI World Summary pipeline.

## Schedule & Runtime Contract

- **Schedule:** Runs every Sunday morning at 09:00 AM IST (03:30 AM UTC) via GitHub Actions, and on-demand via `workflow_dispatch`.
- **Time Window:** Ingests developments from the past 7 days (`--days 7`).
- **Data Ingestion:** Reads topics, keywords, feeds, arXiv queries, and GitHub repositories from `topics.yaml`.
- **Deduplication:** Deduplicates items by canonical URL, then normalized title.
- **AI Inference:** Synthesizes weekly developments using the free Kilo Gateway GitHub Action (`govindarajanv/inference@v1`).
- **Graceful Degradation:** Strictly operates within the free tier (`fail_on_error: false`). Falls back to structured rule-based synthesis if inference is rate limited or unavailable.
- **3-Line Gists:** Formats every development into a crisp 3-line structured gist:
  1. `What it is`: Core proposition, release, or problem tackled.
  2. `Key details`: Mechanism, methodology, or performance benchmarks.
  3. `Takeaway`: Industry impact, developer utility, or ecosystem relevance.
- **Archive Rotation:** Maintains rolling weekly archives (`archive-1.md` through `archive-6.md`).
- **Static Hosting:** Builds and deploys responsive static site via Jekyll to GitHub Pages using `_layouts/default.html` and `_config.yml`.

## Versioning

- Follows Semantic Versioning: `v[major].[minor].[patch]`.
- Current release: `v1.1.0` (redesigned professional magazine layout, responsive CSS, and 3-line skimmable gists).
- The live version badge is always displayed directly below the main page title so it is visible to users.

## Item Schema

Each item contains:
- `title`: Sanitized headline (up to 140 characters).
- `url`: Canonical link to the source or release.
- `published_at`: ISO 8601 publication timestamp.
- `source`: Domain or source label (e.g., `arXiv`, `GitHub/repo`, domain name).
- `summary`: Concisely formatted description.
- `topic`: Target category from `topics.yaml`.
- `gist`: 3-tuple `(what_it_is, key_details, takeaway)`.

## Page Schema

Generated pages follow this layout:
1. **Front Matter:** YAML containing `layout: default`, `title`, `version`, `run_time`, and `engine_used`.
2. **Hero Header:** Main title, live version badge (`v1.1.0`), week date range, and edition metadata.
3. **AI Weekly Synthesis:** Highlight section powered by Kilo Gateway:
   - `### 1. Executive Overview`
   - `### 2. Frontier Models & LLM Innovations`
   - `### 3. Autonomous Agents & Ecosystem`
   - `### 4. Research Breakthroughs & Novel Approaches`
   - `### 5. Industry Impact & Key Trends`
4. **Weekly Developments by Topic:** Categorized cards featuring source pills, date badges, and structured 3-line gist boxes.
5. **Archive:** Grid of prior editions linking to historical weekly archives.

## Agent Inheritance

Agent-specific files reference this file and contain only overrides. They must not duplicate these schemas or rules.
