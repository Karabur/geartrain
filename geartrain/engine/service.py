"""HTTP service that exposes the engine API."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from geartrain.engine.app import EngineApp


def create_app(engine_app: EngineApp) -> Starlette:
    """Create the HTTP service Starlette app with all engine routes."""

    async def health(request):
        return JSONResponse({"status": "ok"})

    async def status(request):
        return JSONResponse(engine_app.get_status())

    async def agent_run(request):
        name = request.path_params["name"]
        if name not in engine_app.agents:
            return JSONResponse(
                {"error": f"Unknown agent: {name}"}, status_code=404
            )
        return JSONResponse(
            {"error": "Agent execution not yet implemented"}, status_code=501
        )

    async def workflow_start(request):
        name = request.path_params["name"]
        if name not in engine_app.workflows:
            return JSONResponse(
                {"error": f"Unknown workflow: {name}"}, status_code=404
            )
        return JSONResponse(
            {"error": "Workflow execution not yet implemented"}, status_code=501
        )

    async def workflow_status(request):
        name = request.path_params["name"]
        if name not in engine_app.workflows:
            return JSONResponse(
                {"error": f"Unknown workflow: {name}"}, status_code=404
            )
        try:
            state = engine_app.state_backend.read_workflow_state(name)
        except FileNotFoundError:
            state = {
                "workflow_name": name,
                "status": "idle",
                "current_run": None,
            }
        return JSONResponse(state)

    async def engine_stop(request):
        engine_app.stop()
        return JSONResponse({"status": "stopped"})

    routes = [
        Route("/health", health),
        Route("/status", status),
        Route("/agents/{name}/run", agent_run, methods=["POST"]),
        Route("/workflows/{name}/start", workflow_start, methods=["POST"]),
        Route("/workflows/{name}/status", workflow_status),
        Route("/engine/stop", engine_stop, methods=["POST"]),
    ]
    return Starlette(routes=routes)


def run_server(engine_app: EngineApp) -> None:
    """Start the uvicorn server using engine config host and port."""
    import uvicorn

    app = create_app(engine_app)
    uvicorn.run(
        app,
        host=engine_app.engine.host,
        port=engine_app.engine.port,
        log_level="info",
    )
