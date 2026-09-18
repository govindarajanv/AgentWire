#!/usr/bin/env python3
"""Fetch, filter, summarize, rotate, and render the Weekly AI World Summary with 3-line gists."""

from __future__ import annotations

import argparse
import calendar
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc

VERSION = "v1.1.0"
ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "curl/7.81.0 (compatible; AgentWire/1.1; +https://github.com/govindarajanv/AgentWire)"
CACHE_FILE = ROOT / "collected_items.json"
DEFAULT_SUMMARY_FILE = ROOT / "ai_summary.md"
KILO_GATEWAY_URL = "https://api.kilo.ai/api/gateway/chat/completions"
FREE_FALLBACK_MODELS = [
    "kilo-auto/free",
    "deepseek/deepseek-v4-flash-0731:free",
    "stepfun/step-3.7-flash:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    published_at: str  # ISO string
    source: str
    summary: str
    topic: str

    @property
    def published_datetime(self) -> datetime:
        dt = parse_time(self.published_at)
        return dt if dt is not None else datetime.fromtimestamp(0, timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text_val = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text_val)
    except ValueError:
        try:
            parsed = datetime.fromtimestamp(
                calendar.timegm(email.utils.parsedate(text_val)), timezone.utc
            )
        except (TypeError, ValueError):
            return None
    return (
        parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    ).astimezone(timezone.utc)


def fetch(url: str, custom_headers: dict[str, str] | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if custom_headers:
        headers.update(custom_headers)
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read()
    except Exception as exc:
        # Graceful fallback to curl for endpoints with TLS or user-agent quirks (e.g. arXiv)
        try:
            curl_args = ["curl", "-sL", "--max-time", "25"]
            for k, v in headers.items():
                curl_args.extend(["-H", f"{k}: {v}"])
            curl_args.append(url)
            res = subprocess.run(curl_args, capture_output=True)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
        raise exc


def matches_topic(title: str, summary: str, topic: dict[str, Any]) -> bool:
    keywords = [str(keyword).lower() for keyword in topic.get("keywords", [])]
    haystack = f"{title} {summary}".lower()
    return not keywords or any(keyword in haystack for keyword in keywords)


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def clean(value: str, limit: int = 400) -> str:
    value = re.sub(r"<[^>]+>", "", html.unescape(re.sub(r"\s+", " ", value))).strip()
    return value[: limit - 1].rstrip() + "..." if len(value) > limit else value


def extract_3_line_gist(title: str, raw_text: str, source: str, topic: str) -> tuple[str, str, str]:
    """Extracts or synthesizes a high-signal 3-line gist: (What it is, Key details, Takeaway)."""
    # Strip HN boilerplates and URLs
    cleaned = re.sub(r"Article URL:\s*\S+", "", raw_text)
    cleaned = re.sub(r"Comments URL:\s*\S+", "", cleaned)
    cleaned = re.sub(r"Points:\s*\d+", "", cleaned)
    cleaned = re.sub(r"#\s*Comments:\s*\d+", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = html.unescape(re.sub(r"\s+", " ", cleaned)).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.strip()) > 20]

    # If the text has enough rich descriptive sentences (e.g. arXiv or release notes)
    if len(sentences) >= 3:
        line1 = sentences[0]
        line2 = sentences[1]
        line3 = " ".join(sentences[2:])
    elif len(sentences) == 2:
        line1 = sentences[0]
        line2 = sentences[1]
        line3 = f"Provides valuable practical utility and implementation guidance for {topic.lower()}."
    elif len(sentences) == 1:
        line1 = sentences[0]
        line2 = f"Introduces focused improvements and architectural refinements in {topic.lower()}."
        line3 = f"Signals accelerating standard adoption and ecosystem convergence."
    else:
        # Contextual domain-aware synthesis based on headline analysis
        t_lower = title.lower()
        if "mcp" in t_lower or "model context protocol" in t_lower:
            line1 = f"Focuses on Model Context Protocol (MCP) integrations, server tooling, and agent interoperability."
            line2 = f"Standardizes how autonomous agents securely query external tools, APIs, and data sources."
            line3 = f"Demonstrates the rapid industry convergence around MCP as the unified agent tool interface."
        elif "agent" in t_lower or "autonomous" in t_lower or "harness" in t_lower:
            line1 = f"Explores autonomous agent architecture, execution safety, and unattended multi-turn workflows."
            line2 = f"Focuses on managing tool-calling loops, context windows, and operational boundaries for agents."
            line3 = f"Crucial for engineers transitioning from basic chat assistants to robust autonomous agents."
        elif "watermark" in t_lower or "provenance" in t_lower:
            line1 = f"Investigates the security, provenance, and behavioral trade-offs of LLM output watermarking."
            line2 = f"Analyzes how embedded watermarks interact with adversarial prompts and downstream agent execution."
            line3 = f"Highlights the tension between regulatory compliance demands and model security postures."
        elif "cost" in t_lower or "token" in t_lower or "pricing" in t_lower or "inflation" in t_lower:
            line1 = f"Examines LLM inference economics, token consumption patterns, and operational expenses."
            line2 = f"Evaluates context compaction, audit findings, and prompt optimizations to curb spiraling API costs."
            line3 = f"Essential for teams scaling generative AI applications under practical production budgets."
        elif "security" in t_lower or "poison" in t_lower or "vulnerab" in t_lower or "guardrail" in t_lower:
            line1 = f"Analyzes emerging threat vectors, prompt injection vulnerabilities, and code poisoning risks in AI."
            line2 = f"Investigates how self-modifying code loops and agent harnesses can be hardened and verified."
            line3 = f"Underscores the critical priority of adversarial defense, policy enforcement, and sandboxing."
        elif "bench" in t_lower or "eval" in t_lower or "metric" in t_lower:
            line1 = f"Introduces rigorous evaluation benchmarks to measure model capabilities and agent reliability."
            line2 = f"Provides standardized comparative metrics across latency, reasoning accuracy, and domain tasks."
            line3 = f"Enables reproducible assessment beyond noisy public leaderboards."
        elif "speech" in t_lower or "voice" in t_lower or "audio" in t_lower:
            line1 = f"Advances open voice synthesis and audio generation with low-latency inference."
            line2 = f"Improves natural prosody and multilingual support for real-time conversational interfaces."
            line3 = f"Expands accessible multimodal interaction channels across developer and consumer apps."
        else:
            line1 = f"{title} represents a notable development in {topic.lower()} cataloged this week."
            line2 = f"Reported and tracked via {source} as part of active developments across the AI landscape."
            line3 = f"Reflects the rapid cadence of technical experimentation and practical deployment."

    # Format cleanly to crisp 1-sentence lines
    line1 = clean(line1.rstrip(".") + ".", 220)
    line2 = clean(line2.rstrip(".") + ".", 220)
    line3 = clean(line3.rstrip(".") + ".", 220)
    return line1, line2, line3


def feed_items(
    url: str, topic: dict[str, Any], start: datetime, end: datetime
) -> list[Item]:
    try:
        root = ET.fromstring(fetch(url))
    except Exception as exc:
        print(f"warning: could not read feed {url}: {exc}", file=sys.stderr)
        return []
    result: list[Item] = []
    for entry in root.findall(".//item") + root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    ):
        title = text(entry.find("title"))
        link_node = entry.find("link")
        url_value = (
            link_node.get("href") if link_node is not None else ""
        ) or text(link_node)
        date_value = (
            text(entry.find("pubDate"))
            or text(entry.find("published"))
            or text(entry.find("updated"))
        )
        published = parse_time(date_value)
        summary = text(entry.find("description")) or text(entry.find("summary"))
        if (
            not title
            or not url_value
            or not published
            or not (start <= published < end)
            or not matches_topic(title, summary, topic)
        ):
            continue
        result.append(
            Item(
                title=clean(title, 140),
                url=url_value,
                published_at=published.isoformat(),
                source=urllib.parse.urlparse(url_value).netloc or "Web",
                summary=clean(summary, 1200),
                topic=topic["name"],
            )
        )
    return result


def arxiv_items(
    query: str, topic: dict[str, Any], start: datetime, end: datetime
) -> list[Item]:
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": 30,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    try:
        root = ET.fromstring(
            fetch(f"https://export.arxiv.org/api/query?{params}")
        )
    except Exception as exc:
        print(f"warning: could not read arXiv query {query}: {exc}", file=sys.stderr)
        return []
    result: list[Item] = []
    namespace = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f"{namespace}entry"):
        published = parse_time(text(entry.find(f"{namespace}published")))
        link = entry.find(f"{namespace}id")
        title = text(entry.find(f"{namespace}title"))
        summary = text(entry.find(f"{namespace}summary"))
        if (
            published
            and link is not None
            and (start <= published < end)
            and matches_topic(title, summary, topic)
        ):
            result.append(
                Item(
                    title=clean(title, 140),
                    url=text(link),
                    published_at=published.isoformat(),
                    source="arXiv",
                    summary=clean(summary, 1500),
                    topic=topic["name"],
                )
            )
    return result


def github_items(
    repo: str, topic: dict[str, Any], start: datetime, end: datetime
) -> list[Item]:
    try:
        payload = fetch(
            f"https://api.github.com/repos/{repo}/releases?per_page=10",
            custom_headers={"Accept": "application/vnd.github.v3+json"},
        )
        data = json.loads(payload)
    except Exception as exc:
        print(f"warning: could not read GitHub repository {repo}: {exc}", file=sys.stderr)
        return []
    result: list[Item] = []
    for release in data:
        published = parse_time(release.get("published_at") or release.get("created_at"))
        title = release.get("name") or release.get("tag_name", repo)
        summary = release.get("body") or "New repository release."
        if (
            published
            and (start <= published < end)
            and matches_topic(title, summary, topic)
        ):
            result.append(
                Item(
                    title=clean(title, 140),
                    url=release.get("html_url", f"https://github.com/{repo}"),
                    published_at=published.isoformat(),
                    source=f"GitHub/{repo}",
                    summary=clean(summary, 1500),
                    topic=topic["name"],
                )
            )
    return result


def load_topics(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"{path} must contain a non-empty topics list")
    return topics


def previous_run(path: Path) -> datetime:
    if not path.exists():
        return datetime.fromtimestamp(0, timezone.utc)
    match = re.search(
        r"^run_time:\s*(.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE
    )
    return parse_time(match.group(1)) if match else datetime.fromtimestamp(0, timezone.utc)


def rotate(root: Path, active_name: str = "index.md") -> None:
    expired = root / "archive-6.md"
    if expired.exists():
        expired.unlink()
    for number in range(5, 0, -1):
        source = root / f"archive-{number}.md"
        if source.exists():
            source.rename(root / f"archive-{number + 1}.md")
    active = root / active_name
    if active.exists():
        active.rename(root / "archive-1.md")


def collect(topics: list[dict[str, Any]], start: datetime, end: datetime) -> list[Item]:
    items: list[Item] = []
    for topic in topics:
        for url in topic.get("feeds", []):
            items.extend(feed_items(url, topic, start, end))
        for query in topic.get("arxiv_queries", []):
            items.extend(arxiv_items(query, topic, start, end))
        for repo in topic.get("github_repos", []):
            items.extend(github_items(repo, topic, start, end))
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Item] = []
    for item in sorted(items, key=lambda candidate: candidate.published_datetime, reverse=True):
        parsed = urllib.parse.urlsplit(item.url)
        canonical_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        title_key = re.sub(r"\W+", " ", item.title.lower()).strip()
        if canonical_url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(canonical_url)
        seen_titles.add(title_key)
        unique.append(item)
    return unique


def save_items_cache(items: list[Item], path: Path) -> None:
    path.write_text(json.dumps([asdict(item) for item in items], indent=2), encoding="utf-8")


def load_items_cache(path: Path) -> list[Item] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Item(**entry) for entry in raw]
    except Exception as exc:
        print(f"warning: could not load cache {path}: {exc}", file=sys.stderr)
        return None


def build_prompt(
    items: list[Item], topics: list[dict[str, Any]], start: datetime, end: datetime
) -> str:
    start_str = start.strftime("%B %d, %Y")
    end_str = end.strftime("%B %d, %Y")

    lines = [
        f"You are an expert AI analyst and journalist writing the 'Weekly AI World Summary' for the week of {start_str} to {end_str}.",
        "",
        "Below is the curated collection of raw news, releases, papers, and discussions from the past 7 days across the AI ecosystem:",
        "",
    ]

    for topic in topics:
        topic_items = [item for item in items if item.topic == topic["name"]]
        lines.append(f"### Category: {topic['name']}")
        for item in topic_items[:20]:
            lines.append(
                f"- Title: {item.title} | Source: {item.source} | Summary: {item.summary[:200]}"
            )
        lines.append("")

    lines.extend(
        [
            "Please synthesize these developments into an editorial Weekly AI World Summary in GitHub-flavored Markdown.",
            "Your output will be read by engineers, researchers, and technical leaders who want crisp gists to skim through.",
            "Your summary MUST include the following clear sections with Markdown headings:",
            "",
            "### 1. Executive Overview",
            "A 2-paragraph synthesis highlighting the primary themes, turning points, and major stories of this week.",
            "",
            "### 2. Frontier Models & LLM Innovations",
            "Key model releases, capability advancements, open-weights releases, and performance breakthroughs. For each key story, include a 3-line takeaway (What it is / Key details / Why it matters).",
            "",
            "### 3. Autonomous Agents & Ecosystem",
            "Developments in agent architectures, tool use (e.g. Model Context Protocol / MCP), frameworks, and developer tooling. Highlight key agent milestones with 3-line gists.",
            "",
            "### 4. Research Breakthroughs & Novel Approaches",
            "Noteworthy research findings, architectures, and theoretical insights from papers submitted this week.",
            "",
            "### 5. Industry Impact & Key Trends",
            "What developers, practitioners, and leaders are prioritizing; regulatory or market movements; and what to watch next week.",
            "",
            "Rules:",
            "- Do not simply echo raw bullet lists. Provide editorial analysis, connections between developments, and clear insights.",
            "- Write in a professional, engaging, and objective tone.",
            "- Do not include a top-level page title (e.g. do not write '# Weekly AI World Summary'); start directly with section headings.",
        ]
    )

    return "\n".join(lines).strip()


def sanitize_ai_summary(text_val: str) -> str:
    """Strips any reasoning pre-amble and ensures clean Markdown section structure."""
    if not text_val:
        return ""
    match = re.search(r"(###?\s+(?:1\.?\s*)?Executive Overview.*)", text_val, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match_general = re.search(r"(^###?\s+.+)", text_val, re.MULTILINE | re.DOTALL)
    if match_general:
        return match_general.group(1).strip()
    return text_val.strip()


def query_kilo_gateway(
    prompt: str,
    system_prompt: str = "You are an expert AI analyst and journalist.",
    model: str = "kilo-auto/free",
) -> str | None:
    """Invokes Kilo Gateway free tier directly for local runs or fallback."""
    models_to_try = [model] + [m for m in FREE_FALLBACK_MODELS if m != model]
    for candidate in models_to_try:
        try:
            body = json.dumps(
                {
                    "model": candidate,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.6,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                KILO_GATEWAY_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content = msg.get("content") or msg.get("reasoning")
                if content and len(content.strip()) > 50:
                    cleaned = sanitize_ai_summary(content)
                    print(f"info: successfully generated summary using Kilo free model '{candidate}'")
                    return cleaned
        except Exception as exc:
            print(f"warning: candidate model '{candidate}' failed: {exc}", file=sys.stderr)
            continue
    return None


def generate_fallback_summary(
    items: list[Item], topics: list[dict[str, Any]], start: datetime, end: datetime
) -> str:
    start_str = start.strftime("%B %d, %Y")
    end_str = end.strftime("%B %d, %Y")

    lines = [
        "> [!NOTE]",
        f"> **Notice:** Kilo Gateway AI inference was throttled or operating in offline fallback mode for this run. Below is an automated editorial synthesis of the {len(items)} curated developments recorded between {start_str} and {end_str}.",
        "",
        "### 1. Executive Overview",
        f"During the week of {start_str} to {end_str}, the AI landscape saw continuous acceleration across frontier foundation models, agentic workflows, and multi-agent systems. A total of {len(items)} notable updates were cataloged from global feeds, developer releases, and arXiv submissions.",
        "",
        "### 2. Frontier Models & LLM Innovations",
        "Key updates this week focused on optimizing inference efficiency, expanding context reasoning, and releasing refined open-weight models for edge and enterprise deployments.",
        "",
        "### 3. Autonomous Agents & Ecosystem",
        "Agentic tooling continues its rapid evolution around protocol standardization (including the Model Context Protocol / MCP) and autonomous agent frameworks designed for deterministic tool execution.",
        "",
        "### 4. Research Breakthroughs & Novel Approaches",
        "Recent research highlights innovations in multi-agent coordination, alignment evaluation, and enhanced retrieval systems that improve model verification and factual reliability.",
        "",
        "### 5. Industry Impact & Key Trends",
        "Industry focus remains anchored on lowering latency, reducing API invocation overhead, and expanding resilient agentic architectures across developer environments.",
    ]
    return "\n".join(lines)


def get_source_slug(source: str) -> str:
    s = source.lower()
    if "arxiv" in s:
        return "arxiv"
    if "github" in s:
        return "github"
    if "ycombinator" in s or "hn" in s:
        return "hn"
    return "general"


def render(
    items: list[Item],
    topics: list[dict[str, Any]],
    start: datetime,
    end: datetime,
    engine: str,
    root: Path,
    ai_summary: str,
) -> str:
    start_str = start.strftime("%B %d, %Y")
    end_str = end.strftime("%B %d, %Y")
    run_time_iso = end.isoformat().replace("+00:00", "Z")

    lines = [
        "---",
        "layout: default",
        "title: Weekly AI World Summary",
        f"version: {VERSION}",
        f"run_time: {run_time_iso}",
        f"engine_used: {engine}",
        "---",
        "",
        '<header class="hero-header">',
        '  <div class="hero-title-row">',
        '    <h1 class="hero-title">Weekly AI World Summary</h1>',
        f'    <span class="version-pill">{VERSION}</span>',
        "  </div>",
        '  <div class="hero-meta">',
        '    <div class="hero-meta-item">',
        "      <span>🗓️</span>",
        f"      <strong>Week of {start_str} &ndash; {end_str}</strong>",
        "    </div>",
        '    <span class="hero-meta-divider">&bull;</span>',
        '    <div class="hero-meta-item">',
        '      <span class="schedule-chip">Published Sundays 09:00 AM IST</span>',
        "    </div>",
        '    <span class="hero-meta-divider">&bull;</span>',
        '    <div class="hero-meta-item">',
        f"      <span>Engine: {engine}</span>",
        "    </div>",
        "  </div>",
        "</header>",
        "",
        '<section id="synthesis" class="synthesis-section">',
        '  <div class="synthesis-header">',
        '    <div class="synthesis-title">',
        "      <span>🧠</span>",
        "      <span>AI Weekly Synthesis</span>",
        "    </div>",
        '    <span class="synthesis-badge">Kilo Gateway Free Tier</span>',
        "  </div>",
        "",
        ai_summary.strip(),
        "</section>",
        "",
        '<section id="developments">',
        '  <h2 class="section-title"><span>⚡</span> Weekly Developments &amp; 3-Line Gists</h2>',
        "",
    ]

    for topic in topics:
        topic_items = [item for item in items if item.topic == topic["name"]]
        topic_anchor = re.sub(r"[^a-z0-9]+", "-", topic["name"].lower()).strip("-")
        lines.append(f'<div id="{topic_anchor}">')
        lines.append(f'  <h3 class="topic-group-title"><span>📌</span> {topic["name"]} ({len(topic_items)} updates)</h3>')
        lines.append('  <div class="dev-card-grid">')

        if not topic_items:
            lines.append('    <p style="color: var(--color-text-muted);">No matching updates recorded in this window.</p>')

        for item in topic_items:
            pub_dt = item.published_datetime
            date_display = pub_dt.strftime("%b %d, %Y • %H:%M UTC") if pub_dt else "Recent"
            source_slug = get_source_slug(item.source)
            l1, l2, l3 = extract_3_line_gist(item.title, item.summary, item.source, topic["name"])

            card_html = f"""    <div class="item-card">
      <div class="item-header">
        <div class="item-title"><a href="{item.url}" target="_blank" rel="noopener">{html.escape(item.title)} ↗</a></div>
      </div>
      <div class="item-meta">
        <span class="badge-source source-{source_slug}">{html.escape(item.source)}</span>
        <span class="item-date">{date_display}</span>
      </div>
      <div class="gist-box">
        <div class="gist-line"><span class="gist-label gist-label-what">What it is</span> <span>{html.escape(l1)}</span></div>
        <div class="gist-line"><span class="gist-label gist-label-details">Key details</span> <span>{html.escape(l2)}</span></div>
        <div class="gist-line"><span class="gist-label gist-label-impact">Takeaway</span> <span>{html.escape(l3)}</span></div>
      </div>
    </div>"""
            lines.append(card_html)

        lines.append("  </div>")
        lines.append("</div>")
        lines.append("")

    lines.append("</section>")
    lines.append("")
    lines.append('<section id="archive">')
    lines.append('  <h2 class="section-title"><span>📚</span> Prior Editions Archive</h2>')
    lines.append('  <div class="archive-grid">')

    for number in range(1, 7):
        archive = root / f"archive-{number}.md"
        if archive.exists():
            label = "Archive 1 (Previous Week)" if number == 1 else f"Archive {number} (Week {number} Prior)"
            archive_card = f"""    <a href="archive-{number}.html" class="archive-card">
      <span class="archive-title">{label}</span>
      <span class="archive-desc">Historical digest edition &bull; Archive #{number}</span>
    </a>"""
            lines.append(archive_card)

    lines.append("  </div>")
    lines.append("</section>")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weekly AI World Summary generator using Kilo Gateway inference."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back for developments (default: 7)",
    )
    parser.add_argument(
        "--now", help="UTC ISO timestamp, useful for deterministic testing or scheduled runs"
    )
    parser.add_argument(
        "--prepare-prompt",
        action="store_true",
        help="Collect items, generate prompt for Kilo Gateway, save to prompt.txt and $GITHUB_OUTPUT",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render index.md using the AI summary from --summary-file or direct fallback",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=DEFAULT_SUMMARY_FILE,
        help="Path to AI summary file generated by Kilo Gateway action",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    topics = load_topics(root / "topics.yaml")
    end = parse_time(args.now) or datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    active = root / "index.md"
    if not active.exists() and (root / "README.md").exists():
        active = root / "README.md"

    if args.prepare_prompt:
        print(f"Collecting developments from {start.isoformat()} to {end.isoformat()} (last {args.days} days)...")
        items = collect(topics, start, end)
        print(f"Collected {len(items)} unique developments across {len(topics)} topics.")
        save_items_cache(items, root / "collected_items.json")

        prompt_text = build_prompt(items, topics, start, end)
        prompt_file = root / "prompt.txt"
        prompt_file.write_text(prompt_text, encoding="utf-8")
        print(f"Wrote prompt ({len(prompt_text)} chars) to {prompt_file}")

        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            delim = "KILO_PROMPT_EOF_984729"
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"prompt<<{delim}\n")
                f.write(prompt_text + "\n")
                f.write(f"{delim}\n")
            print("Exported prompt to $GITHUB_OUTPUT")
        return

    if args.render:
        items = load_items_cache(root / "collected_items.json")
        if items is None:
            print("Cache not found, collecting fresh items...")
            items = collect(topics, start, end)

        ai_summary = ""
        summary_path = args.summary_file.resolve()
        if summary_path.exists():
            raw_summary = summary_path.read_text(encoding="utf-8").strip()
            ai_summary = sanitize_ai_summary(raw_summary)

        engine = os.environ.get("DIGEST_ENGINE", "Kilo Gateway (govindarajanv/inference)")
        ai_success = os.environ.get("AI_SUCCESS", "true").lower() == "true"
        ai_model_used = os.environ.get("AI_MODEL_USED", "")

        if not ai_summary or not ai_success:
            print("warning: AI summary file empty or unsuccessful, using structured fallback summary")
            ai_summary = generate_fallback_summary(items, topics, start, end)
            engine = "Rule-based synthesis (Kilo Gateway fallback)"
        elif ai_model_used:
            engine = f"Kilo Gateway ({ai_model_used})"

        rotate(root, active.name)
        active.write_text(
            render(items, topics, start, end, engine, root, ai_summary), encoding="utf-8"
        )
        print(f"Published Weekly AI World Summary with {len(items)} items for {start.isoformat()} to {end.isoformat()}")
        return

    # Default: Run full pipeline locally
    print(f"Running full weekly summary pipeline locally for {start.isoformat()} to {end.isoformat()}...")
    items = collect(topics, start, end)
    print(f"Collected {len(items)} unique developments.")

    ai_summary = ""
    summary_path = args.summary_file.resolve()
    if summary_path.exists():
        ai_summary = sanitize_ai_summary(summary_path.read_text(encoding="utf-8").strip())

    if not ai_summary:
        print("Invoking free Kilo Gateway directly...")
        prompt_text = build_prompt(items, topics, start, end)
        ai_summary = query_kilo_gateway(prompt_text) or ""

    if not ai_summary:
        print("Generating structured fallback summary...")
        ai_summary = generate_fallback_summary(items, topics, start, end)
        engine = "Rule-based synthesis (local fallback)"
    else:
        engine = "Kilo Gateway free tier (direct)"

    rotate(root, active.name)
    active.write_text(
        render(items, topics, start, end, engine, root, ai_summary), encoding="utf-8"
    )
    print(f"Published Weekly AI World Summary to {active.name}")


if __name__ == "__main__":
    main()
