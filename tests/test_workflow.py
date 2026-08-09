import asyncio
import os
import tempfile
import unittest
from pathlib import Path

# Configure a disposable database before application modules are imported.
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_db_file.name).as_posix()}"
os.environ["IMMEDIATE_CYCLE_ON_INIT"] = "false"

from app.database.session import SessionLocal, init_db  # noqa: E402
from app.discovery.base import DiscoveredTopic  # noqa: E402
from app.services.agent_service import AgentService  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


class StaticDiscovery:
    async def discover_topics(self, query, max_topics=12):
        assert query == "AI Security"
        return [
            DiscoveredTopic(
                title="New AI security benchmark exposes prompt-injection failures",
                url="https://example.test/security-benchmark",
                summary="A reproducible benchmark for testing model security.",
                source="Test feed",
                discovered_at="2026-08-09T10:30:00Z",
                signal_strength=0.9,
            ),
            DiscoveredTopic(
                title="Unrelated celebrity gadget rumor",
                url="https://example.test/rumor",
                summary="No technical substance.",
                source="Test feed",
                discovered_at="2026-08-09T10:30:00Z",
                signal_strength=0.1,
            ),
        ]


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_publish_is_grounded_and_auditable(self):
        db = SessionLocal()
        service = AgentService()
        service.discovery = StaticDiscovery()
        agent = service.create_agent(db, "Ada", "AI Security")

        result = asyncio.run(service.run_cycle(db, agent.id))
        self.assertEqual(result["status"], "published")
        posts = service.get_feed(db, agent.id)
        self.assertEqual(len(posts), 1)
        self.assertIn("example.test/security-benchmark", posts[0].sources)

        # A second cycle sees the same topics and does not create another post.
        result = asyncio.run(service.run_cycle(db, agent.id))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(len(service.get_feed(db, agent.id)), 1)
        db.close()

    def test_init_and_feed_contract(self):
        with TestClient(app) as client:
            response = client.post("/api/agent/init", json={"persona": {"name": "Nora", "domain": "AI Governance", "cadenceMinutes": 15}})
            self.assertEqual(response.status_code, 200)
            agent_id = response.json()["agentId"]
            feed = client.get("/api/agent/feed", params={"agentId": agent_id})
            self.assertEqual(feed.status_code, 200)
            self.assertIn("posts", feed.json())


if __name__ == "__main__":
    unittest.main()
