# Digest SSOT

This file is the single source of truth for the digest pipeline.

## Runtime contract

- Read topics from `topics.yaml`.
- Use the previous page `run_time` as the inclusive window start.
- Use the current UTC execution time as the exclusive window end.
- Never include an item outside that window.
- Deduplicate by canonical URL, then normalized title.
- Render one section per configured topic.

## Item schema

Each item has `title`, `url`, `published_at`, `source`, and `summary`.

## Page schema

Every generated page uses YAML front matter with `title`, `run_time`, and `engine_used`, followed by topic sections and a generated archive footer.

## Style

Use concise Markdown bullets. A bullet contains a linked title, source, publication time, and one-sentence summary. Keep archive links at the bottom under `## Archive`.

## Agent inheritance

Agent-specific files must reference this file and may only contain overrides. They must not copy these schemas, skills, or style rules.
