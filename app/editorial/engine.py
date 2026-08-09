import json
import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.discovery.base import DiscoveredTopic
from app.models.agent import Agent
from app.utils.llm import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class EditorialDecision:
    action: str
    selected: DiscoveredTopic | None
    score: float
    reason: str
    rejected: list[dict]
    evaluations: list[dict]


class EditorialEngine:
    KEYWORDS = {
        "ai security": 0.25,
        "security": 0.18,
        "vulnerability": 0.2,
        "attack": 0.15,
        "privacy": 0.12,
        "alignment": 0.12,
        "agent": 0.1,
        "llm": 0.1,
        "model": 0.08,
        "benchmark": 0.08,
        "open source": 0.07,
        "regulation": 0.07,
    }

    def __init__(self) -> None:
        self.llm = LLMClient()

    async def evaluate(
        self,
        agent: Agent,
        topics: list[DiscoveredTopic],
        memory_context: dict,
    ) -> EditorialDecision:
        if not topics:
            return EditorialDecision("reject", None, 0.0, "No topics discovered", [], [])

        scored = [self._score_topic(agent, topic, memory_context) for topic in topics]
        scored.sort(key=lambda item: item["score"], reverse=True)

        llm_decision = await self._llm_evaluate(agent, scored[:6], memory_context)
        if llm_decision:
            return llm_decision

        best = scored[0]
        if best["score"] < settings.min_publish_score:
            return EditorialDecision(
                action="reject",
                selected=None,
                score=best["score"],
                reason=f"No topic met publish threshold ({settings.min_publish_score}). Best: {best['reason']}",
                rejected=[{"title": item["topic"].title, "score": item["score"], "reason": item["reason"]} for item in scored],
                evaluations=scored,
            )

        rejected = [
            {"title": item["topic"].title, "score": item["score"], "reason": item["reason"]}
            for item in scored
            if item["topic"].title != best["topic"].title
        ]
        return EditorialDecision(
            action="publish",
            selected=best["topic"],
            score=best["score"],
            reason=best["reason"],
            rejected=rejected,
            evaluations=scored,
        )

    def _score_topic(self, agent: Agent, topic: DiscoveredTopic, memory_context: dict) -> dict:
        text = f"{topic.title} {topic.summary}".lower()
        domain_words = [word for word in re.findall(r"[a-z0-9]+", agent.domain.lower()) if len(word) > 2]
        interests = " ".join(json.loads(agent.interests or "[]")).lower()
        opinions = " ".join(json.loads(agent.opinions or "[]")).lower()
        relevance = 0.10
        novelty = 1.0
        opinion_fit = 0.0
        reasons: list[str] = []

        normalized_domain = " ".join(domain_words)
        exact_topic_match = normalized_domain and normalized_domain in re.sub(r"[^a-z0-9]+", " ", text)
        matching_domain_words = [word for word in domain_words if word in text]
        if exact_topic_match:
            relevance = 0.9
            reasons.append("directly matches the saved topic query")
        if matching_domain_words:
            relevance += min(0.55, 0.28 * len(matching_domain_words))
            reasons.append("matches persona domain")

        for keyword, weight in self.KEYWORDS.items():
            if keyword in text:
                relevance += weight * 0.45
                reasons.append(f"relevant keyword: {keyword}")

        if any(term in text for term in re.findall(r"[a-z]{4,}", interests)):
            relevance += 0.1
            reasons.append("matches a core interest")

        if any(keyword in text for keyword in ["today", "new", "launch", "release", "breakthrough"]):
            reasons.append("timely signal")

        opinion_terms = ["evidence", "benchmark", "security", "safety", "privacy", "open source", "governance"]
        if any(term in text and term in opinions for term in opinion_terms):
            opinion_fit = 1.0
            reasons.append("creates a clear persona-opinion angle")

        for published in memory_context.get("published_titles", []):
            if published.lower() in topic.title.lower() or topic.title.lower() in published.lower():
                novelty = 0.15
                reasons.append("likely duplicate of prior publication")

        for rejected in memory_context.get("rejected_topics", []):
            if rejected.lower() == topic.title.lower():
                novelty = 0.0
                reasons.append("previously rejected")

        relevance = min(relevance, 1.0)
        signal = max(0.0, min(topic.signal_strength, 1.0))
        score = (relevance * 0.40) + (novelty * 0.30) + (signal * 0.20) + (opinion_fit * 0.10)
        criteria = {
            "relevance": round(relevance, 3),
            "novelty": round(novelty, 3),
            "signal_strength": round(signal, 3),
            "opinion_fit": round(opinion_fit, 3),
        }
        if not reasons:
            reasons.append("general AI/technology relevance")
        return {"topic": topic, "score": round(score, 3), "reason": "; ".join(reasons), "criteria": criteria}

    async def _llm_evaluate(
        self,
        agent: Agent,
        scored_topics: list[dict],
        memory_context: dict,
    ) -> EditorialDecision | None:
        if not self.llm.enabled:
            return None

        payload = {
            "persona": {"name": agent.name, "domain": agent.domain, "voice": agent.voice},
            "memory": memory_context,
            "candidates": [
                {
                    "title": item["topic"].title,
                    "url": item["topic"].url,
                    "summary": item["topic"].summary,
                    "source": item["topic"].source,
                    "heuristic_score": item["score"],
                    "heuristic_reason": item["reason"],
                }
                for item in scored_topics
            ],
        }

        system_prompt = (
            "You are an editorial desk for an autonomous AI technology writer. "
            "Choose at most one topic to publish or reject all. "
            "Reject duplicates, weak hype, or off-domain topics. "
            "Respond with JSON: "
            '{"action":"publish|reject","selected_title":string|null,"score":number,"reason":string,'
            '"rejected":[{"title":string,"reason":string}]}'
        )

        try:
            result = await self.llm.complete_json(system_prompt, json.dumps(payload))
        except Exception as exc:
            logger.warning("LLM editorial evaluation failed: %s", exc)
            return None

        action = result.get("action", "reject")
        selected_title = result.get("selected_title")
        selected = next((item["topic"] for item in scored_topics if item["topic"].title == selected_title), None)

        if action == "publish" and selected:
            return EditorialDecision(
                action="publish",
                selected=selected,
                score=float(result.get("score", 0.0)),
                reason=result.get("reason", "Selected by editorial model"),
                rejected=result.get("rejected", []),
                evaluations=scored_topics,
            )

        return EditorialDecision(
            action="reject",
            selected=None,
            score=float(result.get("score", 0.0)),
            reason=result.get("reason", "No suitable topic selected"),
            rejected=result.get("rejected", []),
            evaluations=scored_topics,
        )
