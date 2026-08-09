import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import FeedResponse, InitAgentRequest, InitAgentResponse, PostResponse
from app.config import settings
from app.database.session import get_db
from app.models.agent import Agent
from app.models.judgment import Judgment
from app.models.topic import Topic
from app.scheduler.jobs import scheduler
from app.services.agent_service import AgentService
from app.utils.text import to_utc_iso

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_service = AgentService()


@router.post("/init", response_model=InitAgentResponse)
async def initialize_agent(payload: InitAgentRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> InitAgentResponse:
    agent = agent_service.create_agent(
        db=db,
        name=payload.persona.name,
        domain=payload.persona.domain,
        cadence_minutes=payload.persona.cadenceMinutes,
    )
    scheduler.register_agent(agent.id, agent.cadence_minutes)
    if settings.immediate_cycle_on_init:
        background_tasks.add_task(scheduler.run_once, agent.id)
    return InitAgentResponse(agentId=agent.id)


@router.get("/feed", response_model=FeedResponse)
def get_feed(agentId: str = Query(..., alias="agentId"), db: Session = Depends(get_db)) -> FeedResponse:
    agent = db.query(Agent).filter(Agent.id == agentId).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    posts = agent_service.get_feed(db, agentId)
    response_posts: list[PostResponse] = []
    for post in posts:
        try:
            sources = json.loads(post.sources)
        except json.JSONDecodeError:
            sources = []

        response_posts.append(
            PostResponse(
                id=post.id,
                agentId=post.agent_id,
                text=post.text,
                rationale=post.rationale,
                sources=sources,
                createdAt=to_utc_iso(post.created_at),
            )
        )

    return FeedResponse(posts=response_posts)


@router.get("/audit")
def get_audit(agentId: str = Query(..., alias="agentId"), db: Session = Depends(get_db)) -> dict:
    """Demo-facing visibility into accepted and rejected editorial decisions."""
    if not db.query(Agent).filter(Agent.id == agentId).first():
        raise HTTPException(status_code=404, detail="Agent not found")
    rows = (
        db.query(Judgment, Topic)
        .join(Topic, Judgment.topic_id == Topic.id)
        .filter(Judgment.agent_id == agentId)
        .order_by(Judgment.evaluated_at.desc())
        .all()
    )
    return {"judgments": [
        {
            "topic": topic.title,
            "url": topic.url,
            "source": topic.source,
            "score": judgment.score,
            "decision": judgment.decision,
            "reason": judgment.reason,
            "criteria": json.loads(judgment.criteria),
            "evaluatedAt": to_utc_iso(judgment.evaluated_at),
        }
        for judgment, topic in rows
    ]}
