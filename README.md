# Autonomous AI Technology Persona

An autonomous AI writer that discovers live AI & technology topics, applies editorial judgment, remembers prior work, and publishes posts over time — after a single initialization call.

## Features

- **One-time initialization** via `POST /api/agent/init`
- **Autonomous scheduler** that wakes, discovers, evaluates, writes, and sleeps
- **Live topic discovery** from Hacker News, GitHub, arXiv, Reddit, and RSS feeds
- **Editorial engine** that intentionally rejects weak or duplicate topics
- **Persona management** for consistent voice and domain focus
- **Memory engine** to avoid repetition and maintain continuity
- **Transparent publishing** with rationale and sources on every post
- **Persistent feed** via `GET /api/agent/feed`

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Set `OPENAI_API_KEY` in `.env` for highest-quality editorial decisions and writing. The system still runs without it using heuristic editorial scoring and template-based fallback writing. The focus/domain field accepts any topic; each cycle uses that saved text to search live Hacker News, GitHub, arXiv, Reddit, and Google News sources.

Run the server:

```bash
python run.py
```

Open the feed viewer at `http://localhost:8001/` and the API docs at `http://localhost:8001/docs`.

## API Usage

### Initialize agent (once)

```bash
curl -X POST http://localhost:8001/api/agent/init \
  -H "Content-Type: application/json" \
  -d "{\"persona\":{\"name\":\"Ada\",\"domain\":\"AI Security\",\"cadenceMinutes\":180}}"
```

Response:

```json
{"agentId":"abc-123"}
```

### Read feed

```bash
curl "http://localhost:8001/api/agent/feed?agentId=abc-123"
```

## Architecture

```
Client -> FastAPI -> Agent Controller
                         |
           +-------------+-------------+
           |                           |
    Background Scheduler          Feed API
           |
    Topic Discovery -> Editorial Engine -> Memory Engine -> Content Generator -> SQLite
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Enables LLM editorial + writing |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for generation |
| `SCHEDULER_INTERVAL_MINUTES` | `180` | Minutes between autonomous cycles |
| `DATABASE_URL` | `sqlite:///./data/agent.db` | Persistent storage |

The default publishing cadence is 180 minutes (with up to 15 minutes of jitter). You can supply `cadenceMinutes` (minimum 5) when initializing an agent; it is persisted with that agent and used by the autonomous scheduler after restarts. Every published post, source, and editorial rationale is stored in SQLite and remains available through the feed endpoint. Set `SCHEDULER_JITTER_SECONDS=0` locally to run a compressed demo. The first cycle is queued immediately after initialization.

### Audit trail

Use `GET /api/agent/audit?agentId=abc-123` to inspect every accepted and rejected topic. Each judgment includes the weighted relevance, novelty, source signal, and persona-opinion scores. The audit log demonstrates that the agent filters topics instead of publishing every discovery result.

## Deployment

### Render / Railway

1. Push this repository to GitHub
2. Create a web service using `python run.py`
3. Set `OPENAI_API_KEY` and optionally `SCHEDULER_INTERVAL_MINUTES`
4. Use a persistent disk/volume for `./data` if available

A `Dockerfile` is included for container deployment.

## Hackathon Submission Checklist

- [x] Public Git repository
- [x] Working API with init + feed endpoints
- [x] Autonomous scheduler
- [x] Live topic discovery
- [x] Editorial rejection
- [x] Persona + memory
- [x] Rationale + sources on posts
- [x] `PROMPTS.md` AI usage log

## License

MIT
