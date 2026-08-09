import json
import re
import hashlib
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.post import Post
from app.models.topic import Topic


class MemoryEngine:
    SIMILARITY_THRESHOLD = 0.72

    def get_recent_context(self, db: Session, agent_id: str, limit: int = 8) -> dict:
        posts = (
            db.query(Post)
            .filter(Post.agent_id == agent_id)
            .order_by(Post.created_at.desc())
            .limit(limit)
            .all()
        )
        rejected = (
            db.query(Topic)
            .filter(Topic.agent_id == agent_id, Topic.status == "rejected")
            .order_by(Topic.discovered_at.desc())
            .limit(limit)
            .all()
        )
        memories = (
            db.query(Memory)
            .filter(Memory.agent_id == agent_id)
            .order_by(Memory.created_at.desc())
            .limit(limit * 2)
            .all()
        )

        return {
            "published_titles": [self._extract_title(post.text) for post in posts],
            "recent_themes": [memory.topic for memory in memories if memory.kind == "theme"],
            "rejected_topics": [topic.title for topic in rejected],
            "frequent_expressions": self._extract_expressions(posts),
        }

    def is_duplicate(self, db: Session, agent_id: str, title: str) -> tuple[bool, str]:
        normalized = self._normalize(title)
        if db.query(Topic).filter(Topic.agent_id == agent_id, Topic.dedupe_hash == self.dedupe_hash(title, "")).first():
            return True, "This topic was already discovered"
        for memory in db.query(Memory).filter(Memory.agent_id == agent_id).all():
            if self._similarity(normalized, self._normalize(memory.topic)) >= self.SIMILARITY_THRESHOLD:
                return True, f"Similar to previously stored topic: {memory.topic}"
        return False, ""

    def dedupe_hash(self, title: str, url: str = "") -> str:
        normalized = self._normalize(title)
        # Title is intentionally the primary identity: different syndication URLs should not create a new post.
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def remember_publication(self, db: Session, agent_id: str, title: str, theme: str | None = None) -> None:
        db.add(Memory(agent_id=agent_id, topic=title, kind="published"))
        if theme:
            db.add(Memory(agent_id=agent_id, topic=theme, kind="theme"))

    def remember_rejection(self, db: Session, agent_id: str, title: str) -> None:
        db.add(Memory(agent_id=agent_id, topic=title, kind="rejected"))

    def _extract_title(self, text: str) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else "Untitled"
        return first_line[:200]

    def _extract_expressions(self, posts: list[Post]) -> list[str]:
        phrases: dict[str, int] = {}
        for post in posts:
            for match in re.findall(r"\b[A-Z][a-z]+(?: [a-z]+){1,3}\b", post.text):
                if len(match) < 12:
                    continue
                phrases[match] = phrases.get(match, 0) + 1
        ranked = sorted(phrases.items(), key=lambda item: item[1], reverse=True)
        return [phrase for phrase, count in ranked[:5] if count > 1]

    def _normalize(self, text: str) -> str:
        return re.sub(r"\W+", " ", text.lower()).strip()

    def _similarity(self, left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()

    def serialize_context(self, context: dict) -> str:
        return json.dumps(context, indent=2)
