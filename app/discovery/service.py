"""Live, query-driven topic discovery.

Every provider receives the persona's saved domain as a query.  This keeps the
system useful for any subject (for example climate policy, Formula 1, or Python
testing) instead of filtering everything through a fixed AI news list.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import feedparser
import httpx

from app.discovery.base import DiscoveredTopic
from app.utils.text import strip_html

logger = logging.getLogger(__name__)
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class TopicDiscoveryService:
    def _client(self, **kwargs) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=15.0, follow_redirects=True, **kwargs)

    async def discover_topics(self, query: str, max_topics: int = 12) -> list[DiscoveredTopic]:
        query = self._clean_query(query)
        if not query:
            return []

        batches = await asyncio.gather(
            self._fetch_hacker_news(query),
            self._fetch_github(query),
            self._fetch_arxiv(query),
            self._fetch_reddit(query),
            self._fetch_google_news(query),
            return_exceptions=True,
        )
        results: list[DiscoveredTopic] = []
        for batch in batches:
            if isinstance(batch, Exception):
                logger.warning("Discovery source failed for %r: %s", query, batch)
            else:
                results.extend(batch)
        return self._deduplicate(results)[:max_topics]

    async def _fetch_hacker_news(self, query: str) -> list[DiscoveredTopic]:
        async with self._client() as client:
            response = await client.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "story", "hitsPerPage": 8},
            )
            response.raise_for_status()
        topics = []
        for item in response.json().get("hits", []):
            title = item.get("title") or item.get("story_title")
            if not title:
                continue
            object_id = item.get("objectID", "")
            topics.append(DiscoveredTopic(
                title=title,
                url=item.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                summary=strip_html(item.get("story_text") or ""),
                source="Hacker News",
                discovered_at=item.get("created_at") or datetime.now(timezone.utc).isoformat(),
                signal_strength=min(1.0, (item.get("points") or 0) / 300 + 0.25),
            ))
        return topics

    async def _fetch_github(self, query: str) -> list[DiscoveredTopic]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "autonomous-topic-agent/1.0"}
        async with self._client(headers=headers) as client:
            response = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "updated", "order": "desc", "per_page": 8},
            )
            if response.status_code != 200:
                return []
        return [DiscoveredTopic(
            title=f"{repo.get('full_name', 'Repository')}: {repo.get('description') or 'Active project'}",
            url=repo.get("html_url", ""),
            summary=repo.get("description") or "",
            source="GitHub",
            discovered_at=repo.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            signal_strength=min(1.0, repo.get("stargazers_count", 0) / 2000 + 0.2),
        ) for repo in response.json().get("items", []) if repo.get("html_url")]

    async def _fetch_arxiv(self, query: str) -> list[DiscoveredTopic]:
        async with self._client() as client:
            response = await client.get(
                "https://export.arxiv.org/api/query",
                params={"search_query": f'all:"{query}"', "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 6},
            )
            response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        topics = []
        for entry in root.findall("atom:entry", ATOM_NS):
            title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").split())
            url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
            if title and url:
                topics.append(DiscoveredTopic(
                    title=title,
                    url=url,
                    summary=" ".join((entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").split())[:500],
                    source="arXiv",
                    discovered_at=entry.findtext("atom:published", default="", namespaces=ATOM_NS) or datetime.now(timezone.utc).isoformat(),
                    signal_strength=0.65,
                ))
        return topics

    async def _fetch_reddit(self, query: str) -> list[DiscoveredTopic]:
        headers = {"User-Agent": "autonomous-topic-agent/1.0"}
        async with self._client(headers=headers) as client:
            response = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "new", "limit": 8, "type": "link"},
            )
            if response.status_code != 200:
                return []
        topics = []
        for child in response.json().get("data", {}).get("children", []):
            post = child.get("data", {})
            title, permalink = post.get("title"), post.get("permalink")
            if title and permalink:
                topics.append(DiscoveredTopic(
                    title=title,
                    url=f"https://www.reddit.com{permalink}",
                    summary=strip_html((post.get("selftext") or "")[:500]),
                    source=f"Reddit r/{post.get('subreddit', 'all')}",
                    discovered_at=self._timestamp_from_unix(post.get("created_utc")),
                    signal_strength=min(1.0, post.get("score", 0) / 1000 + 0.15),
                ))
        return topics

    async def _fetch_google_news(self, query: str) -> list[DiscoveredTopic]:
        """Google News RSS gives broad, topical coverage without an API key."""
        async with self._client() as client:
            response = await client.get("https://news.google.com/rss/search", params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        return [DiscoveredTopic(
            title=entry.get("title", "Untitled"),
            url=entry.get("link", ""),
            summary=strip_html((entry.get("summary") or "")[:500]),
            source="Google News",
            discovered_at=entry.get("published") or datetime.now(timezone.utc).isoformat(),
            signal_strength=0.7,
        ) for entry in parsed.entries[:8] if entry.get("link")]

    @staticmethod
    def _clean_query(query: str) -> str:
        return re.sub(r"\s+", " ", query).strip()[:200]

    @staticmethod
    def _deduplicate(topics: list[DiscoveredTopic]) -> list[DiscoveredTopic]:
        seen, unique = set(), []
        for topic in topics:
            key = re.sub(r"\W+", "", topic.title.lower())[:160]
            if key and key not in seen:
                seen.add(key)
                unique.append(topic)
        return unique

    @staticmethod
    def _timestamp_from_unix(value: int | float | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
