from pydantic import BaseModel, Field


class PersonaInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=200, description="Any topic to research and write about")
    cadenceMinutes: int | None = Field(default=None, ge=5, le=10080, description="Minutes between autonomous searches")


class InitAgentRequest(BaseModel):
    persona: PersonaInput


class InitAgentResponse(BaseModel):
    agentId: str


class PostResponse(BaseModel):
    id: str
    agentId: str
    text: str
    rationale: str
    sources: list[dict]
    createdAt: str


class FeedResponse(BaseModel):
    posts: list[PostResponse]
