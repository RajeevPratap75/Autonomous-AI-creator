# AI Usage Log

This document records how AI tools were used to build the Autonomous AI Technology Persona hackathon project.

## Tools Used

- **Cursor Agent (Claude)** — primary coding assistant for architecture, implementation, and documentation
- **OpenAI API (`gpt-4o-mini`)** — runtime LLM for editorial decisions and post generation inside the deployed agent

## Prompts & Workflow

### 1. Project bootstrap

**Prompt:** Implement the full PRD for an autonomous AI technology persona with FastAPI, SQLite, APScheduler, live discovery, editorial judgment, memory, and feed APIs.

**Outcome:** Generated project structure, models, services, scheduler, API routes, README, and deployment files.

### 2. Editorial engine design

**Prompt (implicit via PRD):** Not every topic should be published; reject weak topics using freshness, relevance, persona fit, duplication, and technical quality.

**Outcome:** Heuristic scoring plus optional LLM JSON evaluation returning `publish` or `reject` with reasons.

### 3. Memory system

**Prompt (implicit via PRD):** Remember published posts, rejected topics, themes, and prevent duplicate/repetitive content.

**Outcome:** SQLite-backed memory records with title similarity checks and recent-context injection into editorial/writer prompts.

### 4. Content generation

**Prompt template used at runtime:**

```
You are {persona}. Write one thoughtful AI/technology post.
Return JSON with text, rationale, and sources.
Rationale must explain why selected, why relevant now, and why over alternatives.
```

**Outcome:** Structured post generation with transparent reasoning and source attribution.

### 5. Discovery sources

**Prompt (implicit via PRD):** Use live sources — RSS, Hacker News, GitHub, Reddit, arXiv.

**Outcome:** Async httpx/feedparser integrations with deduplication and tech-relevance filtering.

## Human Decisions

- Chose OpenAI as default LLM provider with heuristic/template fallback for resilience
- Default scheduler interval: 30 minutes (configurable)
- SQLite for simplicity and easy hackathon deployment
- Single-post-per-cycle design to prioritize quality over volume

## Verification

All AI-generated code was reviewed and organized into modular services matching the PRD folder structure. Runtime AI usage is isolated to editorial and writing prompts inside the deployed agent.
