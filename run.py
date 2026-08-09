#!/usr/bin/env python3
"""Run the autonomous AI persona API server."""

import uvicorn
import os

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=int(os.getenv("PORT", str(settings.app_port))),
        reload=False
    )
