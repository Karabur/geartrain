"""HTTP service that exposes the engine API."""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from geartrain.agents.factory import AgentFactory
from geartrain.engine.app import EngineApp
from geartrain.engine.config import AgentDefinition
from geartrain.engine.state import generate_run_id


def _build_integrations(engine_app: EngineApp) -> dict:
    """Build available integration clients from config.

    Returns ``{"github": client}`` when the github integration is configured
    and its token is present. A missing integration or credential is not an
    error here — workflows without integration nodes still run; nodes that need
    a missing client fail with a clear message at run time.
    """
    from geartrain.integrations.github import (
        GitHubError,
        github_client_from_config,
    )

    integrations: dict = {}
    if "github" in engine_app.workspace.integrations:
        try:
            integrations["github"] = github_client_from_config(
                engine_app.workspace, engine_app.engine
            )
        except GitHubError:
            pass
    return integrations


def _build_runner(engine_app: EngineApp, agent_def: AgentDefinition):
    """Create an agent runner with the context a langchain agent needs.

    The ``cli`` runner ignores the extra config; the ``langchain`` runner uses
    the workspace and engine for model resolution and the engine ``tools``
    settings for tool roots and shell limits.
    """
    tools = engine_app.engine.tools or {}
    fs = tools.get("filesystem", {})
    shell = tools.get("shell", {})
    return AgentFactory.create(
        agent_def,
        engine_app.sandbox,
        workspace=engine_app.workspace,
        engine=engine_app.engine,
        tool_root=fs.get("root", "."),
        shell_cwd=shell.get("cwd", "."),
        shell_timeout=shell.get("timeout_seconds", 60),
    )


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

        try:
            body = await request.json()
        except Exception:
            body = {}

        task = body.get("task", "")
        context = {
            "project_root": engine_app.workspace.project.repo_root,
            "project_name": engine_app.workspace.project.name,
        }

        agent_def = engine_app.agents[name]
        runner = _build_runner(engine_app, agent_def)

        try:
            output = await asyncio.to_thread(runner.run, task, context)
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

        # Detect GEARTRAIN_TOOL workflow start in agent output
        tool_result = None
        if "GEARTRAIN_TOOL workflow start" in output:
            tool_result = await _handle_workflow_start_tool(engine_app, "geartrain-dev")

        response: dict = {"output": output}
        if tool_result is not None:
            response["tool_result"] = tool_result
        return JSONResponse(response)

    async def _handle_workflow_start_tool(app: EngineApp, workflow_name: str) -> dict:
        """Handle the 'workflow start' tool invocation from the lead agent."""
        if workflow_name not in app.workflows:
            return {"error": f"Unknown workflow: {workflow_name}"}

        from geartrain.workflows.lock import WorkflowLock
        state_path = Path(app.engine.state.path)
        lock = WorkflowLock(state_path, workflow_name)

        if lock.is_locked():
            current = lock.current_run_id()
            return {"status": "already_running", "current_run": current}

        workflow_def = app.workflows[workflow_name]
        agents = {
            role: _build_runner(app, app.agents[agent_name])
            for role, agent_name in workflow_def.agents.items()
            if agent_name in app.agents
        }
        run_id = generate_run_id(workflow_name, state_path=state_path)
        work_dir = Path(app.workspace.project.repo_root) / "work"
        log_file = Path(".geartrain") / "logs" / f"{workflow_name}.md"

        from geartrain.workflows.geartrain_dev import run_geartrain_dev
        try:
            result = await asyncio.to_thread(
                run_geartrain_dev,
                workflow_def,
                agents,
                app.state_backend,
                state_path,
                work_dir,
                run_id,
                log_file,
                None,
                _build_integrations(app),
            )
            return result
        except Exception as exc:
            return {"error": str(exc)}

    async def workflow_start(request):
        name = request.path_params["name"]
        if name not in engine_app.workflows:
            return JSONResponse(
                {"error": f"Unknown workflow: {name}"}, status_code=404
            )

        workflow_def = engine_app.workflows[name]
        state_path = Path(engine_app.engine.state.path)
        agents = {
            role: _build_runner(engine_app, engine_app.agents[agent_name])
            for role, agent_name in workflow_def.agents.items()
            if agent_name in engine_app.agents
        }

        from geartrain.workflows.lock import WorkflowLock
        lock = WorkflowLock(state_path, name)
        if lock.is_locked():
            current = lock.current_run_id()
            try:
                state = engine_app.state_backend.read_workflow_state(name)
            except FileNotFoundError:
                state = {"workflow_name": name, "status": "running", "current_run": current}
            return JSONResponse({"status": "already_running", "current_run": current, "workflow_state": state})

        run_id = generate_run_id(name, state_path=state_path)

        from geartrain.workflows.geartrain_dev import run_geartrain_dev
        work_dir = Path(engine_app.workspace.project.repo_root) / "work"
        log_file = Path(".geartrain") / "logs" / f"{name}.md"

        try:
            result = await asyncio.to_thread(
                run_geartrain_dev,
                workflow_def,
                agents,
                engine_app.state_backend,
                state_path,
                work_dir,
                run_id,
                log_file,
                None,
                _build_integrations(engine_app),
            )
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

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
