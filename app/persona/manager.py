import json

from app.config import settings
from app.models.agent import Agent


class PersonaManager:
    DEFAULT_VOICE = (
        "Evidence-based, professional, critical thinker, technical, and concise. "
        "Prefer concrete analysis over hype. Acknowledge uncertainty when appropriate."
    )

    def build_voice(self, name: str, domain: str) -> str:
        return (
            f"You are {name}, an independent technology writer specializing in {domain}. "
            f"Your voice is {self.DEFAULT_VOICE} "
            f"Stay focused on the saved topic, {domain}, and do not drift into unrelated subjects."
        )

    def build_profile(self, name: str, domain: str) -> dict:
        """Create a deterministic, persistent editorial identity without requiring an LLM."""
        domain_terms = [term.lower() for term in domain.replace("/", " ").split() if len(term) > 2]
        focus = " ".join(domain_terms[:2]) or "technology"
        interests = [
            f"recent developments in {focus}",
            f"the practical impact of {focus}",
            f"evidence and credible sources about {focus}",
            f"different viewpoints and second-order effects in {focus}",
        ]
        opinions = [
            "Claims need reproducible evidence, not launch-day enthusiasm.",
            "New capability should be evaluated together with its misuse and governance costs.",
            "Useful technology is measured by durable real-world outcomes, not demos alone.",
        ]
        descriptors = ["skeptical", "technical-but-accessible", "evidence-led", "constructively contrarian"]
        return {
            "voice": self.build_voice(name, domain),
            "voice_profile": descriptors,
            "interests": interests,
            "opinions": opinions,
            "cadence_minutes": settings.scheduler_interval_minutes,
        }

    def persona_context(self, agent: Agent) -> str:
        interests = json.loads(agent.interests or "[]")
        opinions = json.loads(agent.opinions or "[]")
        voice_profile = json.loads(agent.voice_profile or "[]")
        return (
            f"Persona Name: {agent.name}\n"
            f"Domain Focus: {agent.domain}\n"
            f"Editorial Voice: {agent.voice}\n"
            f"Voice descriptors: {', '.join(voice_profile)}\n"
            f"Core interests: {'; '.join(interests)}\n"
            f"Standing opinions: {'; '.join(opinions)}"
        )
