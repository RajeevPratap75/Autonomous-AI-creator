import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key)
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if self.enabled else None
        self.model = settings.openai_model

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.client:
            raise RuntimeError("OpenAI API key is not configured")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
