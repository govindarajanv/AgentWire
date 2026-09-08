#!/usr/bin/env python3
"""Fetch, filter, rotate, and render the rolling AI digest."""

from __future__ import annotations

import argparse
import calendar
import email.utils
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "ai-digest/1.0 (+GitHub Actions)"


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    published_at: datetime
    source: str
    summary: str
    topic: str


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromtimestamp(calendar.timegm(email.utils.parsedate(text)), timezone.utc)
        except (TypeError, ValueError):
            return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def matches_topic(title: str, summary: str, topic: dict[str, Any]) -> bool:
    keywords = [str(keyword).lower() for keyword in topic.get("keywords", [])]
    haystack = f"{title} {summary}".lower()
    return not keywords or any(keyword in haystack for keyword in keywords)


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def feed_items(url: str, topic: dict[str, Any], start: datetime, end: datetime) -> list[Item]:
    try:
        root = ET.fromstring(fetch(url))
    except Exception as exc:
        print(f"warning: could not read feed {url}: {exc}", file=sys.stderr)
        return []
    result: list[Item] = []
    for entry in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = text(entry.find("title"))
        link_node = entry.find("link")
        url_value = (link_node.get("href") if link_node is not None else "") or text(link_node)
        date_value = text(entry.find("pubDate")) or text(entry.find("published")) or text(entry.find("updated"))
        published = parse_time(date_value)
        summary = text(entry.find("description"))
        if not title or not url_value or not published or not (start <= published < end) or not matches_topic(title, summary, topic):
            continue
        result.append(Item(title, url_value, published, urllib.parse.urlparse(url_value).netloc, summary, topic["name"]))
    return result


def arxiv_items(query: str, topic: dict[str, Any], start: datetime, end: datetime) -> list[Item]:
    params = urllib.parse.urlencode({"search_query": query, "start": 0, "max_results": 25, "sortBy": "submittedDate", "sortOrder": "descending"})
    try:
        root = ET.fromstring(fetch(f"https://export.arxiv.org/api/query?{params}"))
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
        if published and link is not None and start <= published < end and matches_topic(title, summary, topic):
            result.append(Item(title, text(link), published, "arXiv", summary, topic["name"]))
    return result


def github_items(repo: str, topic: dict[str, Any], start: datetime, end: datetime) -> list[Item]:
    try:
        data = json.loads(fetch(f"https://api.github.com/repos/{repo}/releases?per_page=10"))
    except Exception as exc:
        print(f"warning: could not read GitHub repository {repo}: {exc}", file=sys.stderr)
        return []
    result: list[Item] = []
    for release in data:
        published = parse_time(release.get("published_at") or release.get("created_at"))
        title = release.get("name") or release.get("tag_name", repo)
        summary = release.get("body") or "New repository release."
        if published and start <= published < end and matches_topic(title, summary, topic):
            result.append(Item(title, release["html_url"], published, f"GitHub/{repo}", summary, topic["name"]))
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
    match = re.search(r"^run_time:\s*(.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)
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


def clean(value: str, limit: int = 240) -> str:
    value = re.sub(r"<[^>]+>", "", html.unescape(re.sub(r"\s+", " ", value))).strip()
    return value[: limit - 1].rstrip() + "..." if len(value) > limit else value


def render(items: list[Item], topics: list[dict[str, Any]], start: datetime, run_time: datetime, engine: str, root: Path) -> str:
    lines = ["---", "title: Daily AI Agents & LLM Digest", f"run_time: {run_time.isoformat().replace('+00:00', 'Z')}", f"engine_used: {engine}", "---", ""]
    for topic in topics:
        topic_items = [item for item in items if item.topic == topic["name"]]
        lines.extend([f"## {topic['name']}", ""])
        if not topic_items:
            lines.append("- No matching updates in this window.")
        for item in topic_items:
            lines.append(f"- [{clean(item.title, 140)}]({item.url}) - {item.source}, {item.published_at.strftime('%Y-%m-%d %H:%M UTC')}. {clean(item.summary)}")
        lines.append("")
    lines.extend(["## Archive", ""])
    for number in range(1, 7):
        archive = root / f"archive-{number}.md"
        if archive.exists():
            label = "Archive 1 (Previous Run)" if number == 1 else f"Archive {number}"
            lines.append(f"- [{label}](archive-{number}.md)")
    return "\n".join(lines).rstrip() + "\n"


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
    for item in sorted(items, key=lambda candidate: candidate.published_at, reverse=True):
        parsed = urllib.parse.urlsplit(item.url)
        canonical_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        title_key = re.sub(r"\W+", " ", item.title.lower()).strip()
        if canonical_url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(canonical_url)
        seen_titles.add(title_key)
        unique.append(item)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--now", help="UTC ISO timestamp, useful for deterministic tests")
    args = parser.parse_args()
    root = args.root.resolve()
    active = root / "index.md"
    if not active.exists() and (root / "README.md").exists():
        active = root / "README.md"
    start = previous_run(active)
    end = parse_time(args.now) or datetime.now(timezone.utc)
    if end <= start:
        end = start + __import__("datetime").timedelta(minutes=1)
    topics = load_topics(root / "topics.yaml")
    items = collect(topics, start, end)
    rotate(root, active.name)
    active.write_text(render(items, topics, start, end, os.environ.get("DIGEST_ENGINE", "Python digest"), root), encoding="utf-8")
    print(f"published {len(items)} items for {start.isoformat()} to {end.isoformat()}")


if __name__ == "__main__":
    main()
