"""HTTP service that exposes the engine API."""

from __future__ import annotations

import asyncio
import json
import re

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse

from geartrain.agents.factory import AgentFactory
from geartrain.engine.app import EngineApp
from geartrain.engine.config import AgentDefinition
from geartrain.engine.observability import attempts_for_run, summarize_run
from geartrain.memory.store import MemoryScope, MemorySystem
from geartrain.workflows.start import start_workflow


def _parse_workflow_start_tool(output: str) -> str | None:
    """Extract the workflow name from a ``GEARTRAIN_TOOL workflow start`` line.

    Returns the name after the marker, or ``None`` when none is given.
    """
    m = re.search(r"GEARTRAIN_TOOL workflow start\s+(\S+)", output)
    return m.group(1) if m else None

# Streaming poll cadence and ceiling. Small enough that a live event appended
# during a stream is delivered promptly; bounded so a stream never hangs.
_STREAM_POLL_SECONDS = 0.1
_STREAM_MAX_SECONDS = 30.0
_TERMINAL_STATUSES = {"completed", "failed"}


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

        # Detect GEARTRAIN_TOOL workflow start in agent output. The workflow
        # name is parsed from the tool invocation; the engine names none.
        tool_result = None
        if "GEARTRAIN_TOOL workflow start" in output:
            workflow_name = _parse_workflow_start_tool(output)
            if workflow_name:
                tool_result = await _start_workflow_async(engine_app, workflow_name)

        response: dict = {"output": output}
        if tool_result is not None:
            response["tool_result"] = tool_result
        return JSONResponse(response)

    async def _start_workflow_async(
        app: EngineApp, name: str, task: str = ""
    ) -> dict:
        """Run the generic start path off the event loop."""
        return await asyncio.to_thread(
            start_workflow,
            app,
            name,
            task,
            build_runner=lambda agent_def: _build_runner(app, agent_def),
            integrations=_build_integrations(app),
        )

    async def workflow_start(request):
        name = request.path_params["name"]
        if name not in engine_app.workflows:
            return JSONResponse(
                {"error": f"Unknown workflow: {name}"}, status_code=404
            )

        try:
            body = await request.json()
        except Exception:
            body = {}
        task = body.get("task", "") if isinstance(body, dict) else ""

        try:
            result = await _start_workflow_async(engine_app, name, task)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

        if result.get("status") == "already_running":
            current = result.get("current_run")
            try:
                state = engine_app.state_backend.read_workflow_state(name)
            except FileNotFoundError:
                state = {
                    "workflow_name": name,
                    "status": "running",
                    "current_run": current,
                }
            return JSONResponse(
                {
                    "status": "already_running",
                    "current_run": current,
                    "workflow_state": state,
                }
            )
        if "error" in result:
            return JSONResponse(result, status_code=500)
        return JSONResponse(result)

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

    # -- Run query API (Phase 7 observability) -------------------------------

    backend = engine_app.state_backend

    def _run_exists(run_id: str) -> bool:
        try:
            backend.read_run_state(run_id)
            return True
        except (FileNotFoundError, ValueError):
            return False

    async def list_runs(request):
        return JSONResponse({"runs": backend.list_runs()})

    async def get_run(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)
        return JSONResponse(backend.read_run_state(run_id))

    async def get_run_events(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)
        return JSONResponse({"run_id": run_id, "events": backend.read_events(run_id)})

    async def get_run_nodes(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)
        return JSONResponse(
            {"run_id": run_id, "nodes": backend.list_node_outputs(run_id)}
        )

    async def get_run_attempts(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)
        return JSONResponse(
            {"run_id": run_id, "attempts": attempts_for_run(backend, run_id)}
        )

    async def get_run_summary(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)
        return JSONResponse(summarize_run(backend, run_id))

    async def stream_run_events(request):
        run_id = request.path_params["id"]
        if not _run_exists(run_id):
            return JSONResponse({"error": f"Unknown run: {run_id}"}, status_code=404)

        async def gen():
            seen = 0
            waited = 0.0
            while True:
                events = backend.read_events(run_id)
                for ev in events[seen:]:
                    payload = json.dumps(ev)
                    yield f"event: {ev.get('type', 'event')}\ndata: {payload}\n\n"
                seen = len(events)

                try:
                    state = backend.read_run_state(run_id)
                except (FileNotFoundError, ValueError):
                    state = {}
                if state.get("status") in _TERMINAL_STATUSES:
                    yield f"event: end\ndata: {json.dumps({'run_id': run_id})}\n\n"
                    return
                if waited >= _STREAM_MAX_SECONDS:
                    return
                await asyncio.sleep(_STREAM_POLL_SECONDS)
                waited += _STREAM_POLL_SECONDS

        return StreamingResponse(gen(), media_type="text/event-stream")

    async def list_workflows(request):
        return JSONResponse({"workflows": sorted(engine_app.workflows.keys())})

    async def get_workflow(request):
        name = request.path_params["id"]
        if name not in engine_app.workflows:
            return JSONResponse(
                {"error": f"Unknown workflow: {name}"}, status_code=404
            )
        wf = engine_app.workflows[name]
        try:
            state = backend.read_workflow_state(name)
        except FileNotFoundError:
            state = {"workflow_name": name, "status": "idle", "current_run": None}
        return JSONResponse(
            {
                "name": name,
                "description": wf.description,
                "agents": wf.agents,
                "state": state,
            }
        )

    async def list_checkpoints(request):
        status_filter = request.query_params.get("status")
        return JSONResponse(
            {"checkpoints": backend.list_checkpoints(status=status_filter)}
        )

    async def respond_checkpoint(request):
        checkpoint_id = request.path_params["cid"]
        try:
            body = await request.json()
        except Exception:
            body = {}
        response = str(body.get("response", ""))

        match = next(
            (cp for cp in backend.list_checkpoints() if cp.get("checkpoint_id") == checkpoint_id),
            None,
        )
        if match is None:
            return JSONResponse(
                {"error": f"Unknown checkpoint: {checkpoint_id}"}, status_code=404
            )

        run_id = match["run_id"]
        updated = backend.respond_checkpoint(run_id, checkpoint_id, response)
        # Wake the paused run thread, if the run is live in this process.
        resumed = engine_app.checkpoint_coordinator.resolve(run_id, response)
        return JSONResponse({"checkpoint": updated, "resumed": resumed})

    async def list_memory(request):
        store = engine_app.memory_store
        scopes = {
            MemoryScope.WORKSPACE: "",
            MemoryScope.WORKFLOW: "",
            MemoryScope.AGENT_LEVEL: "",
        }
        overview = []
        for system in (MemorySystem.MEMORY, MemorySystem.KNOWLEDGE):
            for scope in scopes:
                entries = store.list_entries(system=system, scope=scope)
                if entries:
                    overview.append(
                        {
                            "system": system.value,
                            "scope": scope.value,
                            "count": len(entries),
                        }
                    )
        return JSONResponse({"memory": overview})

    async def get_memory_scope(request):
        scope_name = request.path_params["scope"]
        try:
            scope = MemoryScope(scope_name)
        except ValueError:
            return JSONResponse(
                {"error": f"Unknown scope: {scope_name}"}, status_code=404
            )
        system_name = request.query_params.get("system", MemorySystem.MEMORY.value)
        try:
            system = MemorySystem(system_name)
        except ValueError:
            return JSONResponse(
                {"error": f"Unknown system: {system_name}"}, status_code=404
            )
        entries = engine_app.memory_store.list_entries(system=system, scope=scope)
        return JSONResponse(
            {
                "scope": scope.value,
                "system": system.value,
                "entries": [r.to_metadata() for r in entries],
            }
        )

    routes = [
        Route("/health", health),
        Route("/status", status),
        Route("/agents/{name}/run", agent_run, methods=["POST"]),
        Route("/workflows/{name}/start", workflow_start, methods=["POST"]),
        Route("/workflows/{name}/status", workflow_status),
        Route("/engine/stop", engine_stop, methods=["POST"]),
        # Run query + observability API
        Route("/api/runs", list_runs),
        Route("/api/runs/{id}", get_run),
        Route("/api/runs/{id}/events", get_run_events),
        Route("/api/runs/{id}/events/stream", stream_run_events),
        Route("/api/runs/{id}/nodes", get_run_nodes),
        Route("/api/runs/{id}/attempts", get_run_attempts),
        Route("/api/runs/{id}/summary", get_run_summary),
        Route("/api/workflows", list_workflows),
        Route("/api/workflows/{id}", get_workflow),
        Route("/api/checkpoints", list_checkpoints),
        Route("/api/checkpoints/{cid}/respond", respond_checkpoint, methods=["POST"]),
        Route("/api/memory", list_memory),
        Route("/api/memory/{scope}", get_memory_scope),
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
