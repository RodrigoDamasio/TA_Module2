"""Composition root. Railway starts it with `uvicorn app.main:app`."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import problems, routes
from app.config import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Code Analyzer",
        description="LLM agent that reviews code and returns structured feedback.",
    )

    # Order matters: Starlette makes the LAST added middleware the outermost.
    # The error middleware is added first so CORS wraps it and 500s keep CORS headers.
    app.add_middleware(problems.UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Retry-After"],
    )

    problems.register_problem_handlers(app)
    app.include_router(problems.router)
    app.include_router(routes.router)
    return app


app = create_app()
