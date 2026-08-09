import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.models.agent import Agent
from app.database.session import SessionLocal
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)


class AutonomousScheduler:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self.agent_service = AgentService()
        self._started = False
        self._agent_jobs: set[str] = set()

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.start()
        self._started = True
        logger.info("Autonomous scheduler started")

    def shutdown(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False

    def register_agent(self, agent_id: str, cadence_minutes: int | None = None) -> None:
        self.start()
        interval_minutes = cadence_minutes or settings.scheduler_interval_minutes
        # Keep a little natural variation while never letting jitter overwhelm a
        # short interval selected in the UI.
        jitter_seconds = min(settings.scheduler_jitter_seconds, max(0, interval_minutes * 6))
        self.scheduler.add_job(
            self._run_job,
            trigger=IntervalTrigger(
                minutes=interval_minutes,
                jitter=jitter_seconds,
            ),
            id=f"agent-cycle-{agent_id}",
            args=[agent_id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._agent_jobs.add(agent_id)
        logger.info(
            "Registered autonomous job for agent %s every %s minutes",
            agent_id,
            interval_minutes,
        )

    async def run_once(self, agent_id: str) -> None:
        await self._run_job(agent_id)

    async def _run_job(self, agent_id: str) -> None:
        db = SessionLocal()
        try:
            await self.agent_service.run_cycle(db, agent_id)
        except Exception as exc:
            logger.exception("Autonomous cycle failed for agent %s: %s", agent_id, exc)
        finally:
            db.close()

    def restore_agents(self, agents: list[Agent]) -> None:
        for agent in agents:
            self.register_agent(agent.id, agent.cadence_minutes)


scheduler = AutonomousScheduler()
