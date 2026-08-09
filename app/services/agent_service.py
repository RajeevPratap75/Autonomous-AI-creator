import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.discovery.service import TopicDiscoveryService
from app.editorial.engine import EditorialEngine
from app.memory.engine import MemoryEngine
from app.models.agent import Agent
from app.models.judgment import Judgment
from app.models.post import Post
from app.models.topic import Topic
from app.persona.manager import PersonaManager
from app.writer.generator import ContentGenerator

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self) -> None:
        self.discovery = TopicDiscoveryService()
        self.editorial = EditorialEngine()
        self.memory = MemoryEngine()
        self.writer = ContentGenerator()
        self.persona = PersonaManager()

    def create_agent(self, db: Session, name: str, domain: str, cadence_minutes: int | None = None) -> Agent:
        existing = db.query(Agent).filter(Agent.name == name, Agent.domain == domain).first()
        if existing:
            if cadence_minutes and existing.cadence_minutes != cadence_minutes:
                existing.cadence_minutes = cadence_minutes
                db.commit()
                db.refresh(existing)
            return existing
        profile = self.persona.build_profile(name, domain)
        agent = Agent(
            name=name,
            domain=domain,
            voice=profile["voice"],
            voice_profile=json.dumps(profile["voice_profile"]),
            interests=json.dumps(profile["interests"]),
            opinions=json.dumps(profile["opinions"]),
            cadence_minutes=cadence_minutes or profile["cadence_minutes"],
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent

    async def run_cycle(self, db: Session, agent_id: str) -> dict:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        logger.info("Starting autonomous cycle for agent %s (%s)", agent.name, agent_id)
        topics = await self.discovery.discover_topics(query=agent.domain)
        memory_context = self.memory.get_recent_context(db, agent_id)

        stored_topics: list[Topic] = []
        for discovered in topics:
            is_dup, dup_reason = self.memory.is_duplicate(db, agent_id, discovered.title)
            topic = Topic(
                agent_id=agent_id,
                title=discovered.title,
                url=discovered.url,
                summary=discovered.summary,
                source=discovered.source,
                signal_strength=discovered.signal_strength,
                dedupe_hash=self.memory.dedupe_hash(discovered.title, discovered.url),
                status="duplicate" if is_dup else "discovered",
                rejection_reason=dup_reason if is_dup else None,
                discovered_at=self._parse_timestamp(discovered.discovered_at),
            )
            db.add(topic)
            stored_topics.append(topic)
        db.commit()

        candidate_topics = [
            discovered
            for discovered, topic in zip(topics, stored_topics)
            if topic.status == "discovered"
        ]

        decision = await self.editorial.evaluate(agent, candidate_topics, memory_context)
        evaluation_by_title = {item["topic"].title: item for item in decision.evaluations}

        # Persist a decision for every candidate, including items that lost to the winner.
        for topic in stored_topics:
            if topic.status == "duplicate":
                continue
            evaluation = evaluation_by_title.get(topic.title, {})
            is_selected = decision.action == "publish" and decision.selected and topic.title == decision.selected.title
            rejection = next((item for item in decision.rejected if item.get("title") == topic.title), None)
            reason = decision.reason if is_selected else (rejection or {}).get("reason", "Not selected this cycle")
            db.add(Judgment(
                agent_id=agent_id,
                topic_id=topic.id,
                score=float(evaluation.get("score", decision.score)),
                decision="accept" if is_selected else "reject",
                reason=reason,
                criteria=json.dumps(evaluation.get("criteria", {})),
            ))

        if decision.action != "publish" or not decision.selected:
            for topic in stored_topics:
                if topic.status == "discovered":
                    topic.status = "rejected"
                    topic.score = decision.score
                    topic.rejection_reason = decision.reason
                    self.memory.remember_rejection(db, agent_id, topic.title)
            db.commit()
            logger.info("Cycle rejected all topics for agent %s: %s", agent_id, decision.reason)
            return {"status": "rejected", "reason": decision.reason}

        selected_topic = decision.selected
        for topic in stored_topics:
            if topic.title == selected_topic.title:
                topic.status = "published"
                topic.score = decision.score
            elif topic.status == "discovered":
                topic.status = "rejected"
                rejected_match = next((r for r in decision.rejected if r.get("title") == topic.title), None)
                topic.rejection_reason = rejected_match.get("reason") if rejected_match else "Not selected"
                topic.score = decision.score
                self.memory.remember_rejection(db, agent_id, topic.title)

        generated = await self.writer.generate_post(
            agent=agent,
            topic=selected_topic,
            editorial_reason=decision.reason,
            rejected=decision.rejected,
            memory_context=memory_context,
        )

        post = Post(
            agent_id=agent_id,
            topic_id=next(topic.id for topic in stored_topics if topic.title == selected_topic.title),
            text=generated["text"],
            rationale=generated["rationale"],
            sources=json.dumps(generated["sources"]),
        )
        db.add(post)
        self.memory.remember_publication(db, agent_id, selected_topic.title, theme=agent.domain)
        db.commit()
        db.refresh(post)

        logger.info("Published post %s for agent %s", post.id, agent_id)
        return {"status": "published", "postId": post.id}

    def get_feed(self, db: Session, agent_id: str) -> list[Post]:
        return (
            db.query(Post)
            .filter(Post.agent_id == agent_id)
            .order_by(Post.created_at.desc())
            .all()
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)
