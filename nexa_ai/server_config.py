from __future__ import annotations

from typing import Any


def build_uvicorn_config(app: Any, host: str, port: int):
    """Build a quiet local API server without Uvicorn's dictConfig formatter lookup.

    PyInstaller's frozen Windows bundle can fail to resolve Uvicorn's default
    uvicorn.logging.DefaultFormatter through dictConfig. NexaAI owns its
    startup/runtime log, so disable Uvicorn's optional logging configuration.
    """
    import uvicorn

    return uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="error",
        access_log=False,
        log_config=None,
    )
