# Weekly AI World Summary SSOT

This file is the single source of truth for the Weekly AI World Summary pipeline.

## Schedule & Runtime Contract

- **Schedule:** Runs every Sunday morning at 09:00 AM IST (03:30 AM UTC) via GitHub Actions, and on-demand via `workflow_dispatch`.
- **Time Window:** Ingests developments from the past 7 days (`--days 7`).
- **Data Ingestion:** Reads topics, keywords, feeds, arXiv queries, and GitHub repositories from `topics.yaml`.
- **Deduplication:** Deduplicates items by canonical URL, then normalized title.
- **AI Inference:** Synthesizes weekly developments using the free Kilo Gateway GitHub Action (`govindarajanv/inference@v1`).
- **Graceful Degradation:** Strictly operates within the free tier (`fail_on_error: false`). Falls back to structured rule-based synthesis if inference is rate limited or unavailable.
- **Archive Rotation:** Maintains rolling weekly archives (`archive-1.md` through `archive-6.md`).
- **Static Hosting:** Builds and deploys static site to GitHub Pages.

## Versioning

- Follows Semantic Versioning: `v[major].[minor].[patch]`, initialized at `v1.0.0`.
- The live version badge is always displayed directly below the main page title so it is visible to users.

## Item Schema

Each item contains:
- `title`: Sanitized headline (up to 140 characters).
- `url`: Canonical link to the source or release.
- `published_at`: ISO 8601 publication timestamp.
- `source`: Domain or source label (e.g., `arXiv`, `GitHub/repo`, domain name).
- `summary`: Concisely formatted description.
- `topic`: Target category from `topics.yaml`.

## Page Schema

Generated pages follow this layout:
1. **Front Matter:** YAML containing `title`, `version`, `run_time`, and `engine_used`.
2. **Title & Version Header:** `# Weekly AI World Summary` followed immediately by the live version badge and week date range.
3. **AI Weekly Synthesis:** `## AI Weekly Synthesis` with editorial sections:
   - `### 1. Executive Overview`
   - `### 2. Frontier Models & LLM Innovations`
   - `### 3. Autonomous Agents & Ecosystem`
   - `### 4. Research Breakthroughs & Novel Approaches`
   - `### 5. Industry Impact & Key Trends`
4. **Weekly Developments by Topic:** `## Weekly Developments by Topic` with linked markdown bullets.
5. **Archive:** `## Archive` with links to past 6 weeks of summaries.

## Agent Inheritance

Agent-specific files reference this file and contain only overrides. They must not duplicate these schemas or rules.
