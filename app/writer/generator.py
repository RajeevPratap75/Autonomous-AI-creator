from app.utils.text import strip_html
import logging
from app.discovery.base import DiscoveredTopic
from app.models.agent import Agent
from app.persona.manager import PersonaManager
from app.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.persona = PersonaManager()

    async def generate_post(
        self,
        agent: Agent,
        topic: DiscoveredTopic,
        editorial_reason: str,
        rejected: list[dict],
        memory_context: dict,
    ) -> dict:
        llm_post = await self._generate_with_llm(agent, topic, editorial_reason, rejected, memory_context)
        if llm_post:
            return llm_post
        return self._generate_fallback(agent, topic, editorial_reason, rejected)

    async def _generate_with_llm(
        self,
        agent: Agent,
        topic: DiscoveredTopic,
        editorial_reason: str,
        rejected: list[dict],
        memory_context: dict,
    ) -> dict | None:
        if not self.llm.enabled:
            return None

        system_prompt = (
            f"{self.persona.persona_context(agent)}\n"
            "Write one thoughtful post in Markdown about the selected topic. Maintain a consistent voice. "
            "Return JSON with keys: text, rationale, sources. "
            "Rationale must explain why selected, why relevant now, and why over alternatives. "
            "sources must be an array of objects with title, url, source."
        )
        user_prompt = json.dumps(
            {
                "selected_topic": {
                    "title": topic.title,
                    "url": topic.url,
                    "summary": topic.summary,
                    "source": topic.source,
                },
                "editorial_reason": editorial_reason,
                "rejected_topics": rejected,
                "memory_context": memory_context,
            },
            indent=2,
        )

        try:
            result = await self.llm.complete_json(system_prompt, user_prompt)
            text = result.get("text", "").strip()
            rationale = result.get("rationale", "").strip()
            if not text or not rationale:
                return None
            # Never expose model-supplied source URLs: the writer may only cite the
            # item the discovery layer actually fetched.
            sources = [{"title": topic.title, "url": topic.url, "source": topic.source}]
            return {"text": text, "rationale": rationale, "sources": sources}
        except Exception as exc:
            logger.warning("LLM content generation failed: %s", exc)
            return None

    def _generate_fallback(
        self,
        agent: Agent,
        topic: DiscoveredTopic,
        editorial_reason: str,
        rejected: list[dict],
    ) -> dict:
        alt_titles = ", ".join(item.get("title", "unknown") for item in rejected[:3]) or "none"
        summary = strip_html(topic.summary)
        text = (
            f"## {topic.title}\n\n"
            f"**As {agent.name}, I am tracking {agent.domain} closely.** "
            f"{summary or 'This story surfaced across live technology sources and merits a careful read rather than reactive hype.'}\n\n"
            f"The useful question is not just what happened, but what changes next for people following {agent.domain}. "
            f"I would separate the source-backed facts from the headline, watch for second-order effects, "
            f"and revisit the story as stronger evidence emerges.\n\n"
            f"Source trail: [{topic.source}]({topic.url})."
        )
        rationale = (
            f"Selected because {editorial_reason}. "
            f"It is relevant now given fresh activity from {topic.source}. "
            f"Chosen instead of alternatives such as {alt_titles} due to stronger fit with {agent.domain} "
            f"and clearer technical substance."
        )
        sources = [{"title": topic.title, "url": topic.url, "source": topic.source}]
        return {"text": text, "rationale": rationale, "sources": sources}
