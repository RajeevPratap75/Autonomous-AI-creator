import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as agent_router
from app.database.session import SessionLocal, init_db
from app.models.agent import Agent
from app.scheduler.jobs import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        agents = db.query(Agent).all()
        if agents:
            scheduler.restore_agents(agents)
            logger.info("Restored %s autonomous agent job(s)", len(agents))
    finally:
        db.close()

    yield
    scheduler.shutdown()


app = FastAPI(
    title="Autonomous AI Technology Persona",
    description="An autonomous AI writer that discovers, evaluates, and publishes technology content.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(agent_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def feed_viewer() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
