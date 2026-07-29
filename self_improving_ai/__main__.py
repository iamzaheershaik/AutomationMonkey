"""
Main entry point for the Self-Improving AI System.

Usage:
    python -m self_improving_ai              # Start API server
    python -m self_improving_ai --loop       # Run improvement loop
    python -m self_improving_ai --init-db    # Initialize database
"""

import argparse
import sys

import uvicorn

from config.settings import settings


def main():
    parser = argparse.ArgumentParser(description="Self-Improving AI System")
    parser.add_argument("--host", default=settings.API_HOST)
    parser.add_argument("--port", type=int, default=settings.API_PORT)
    parser.add_argument("--workers", type=int, default=settings.API_WORKERS)
    parser.add_argument("--reload", action="store_true", default=settings.API_RELOAD)
    parser.add_argument("--loop", action="store_true", help="Run the continuous improvement loop")
    parser.add_argument("--init-db", action="store_true", help="Initialize database tables")
    args = parser.parse_args()

    if args.init_db:
        from core.database import init_db
        from config.settings import ensure_directories
        ensure_directories()
        init_db()
        print("Database initialized successfully.")
        return

    if args.loop:
        from self_improving_ai.orchestrator import ImprovementLoop
        loop = ImprovementLoop()
        loop.run()
    else:
        uvicorn.run(
            "api:app",
            host=args.host,
            port=args.port,
            workers=args.workers if not args.reload else 1,
            reload=args.reload,
            log_level=settings.LOG_LEVEL.lower(),
        )


if __name__ == "__main__":
    main()
