"""CLI entrypoint for GearTrain.

Usage:
    geartrain <global-command>
    geartrain <module> <command> [args]
"""

import argparse
import http.client
import json
import os
import signal
import sys
import threading
from pathlib import Path

from geartrain.engine.app import EngineApp
from geartrain.engine.loader import load_engine
from geartrain.engine.observability import (
    render_summary,
    render_timeline,
    summarize_run,
)
from geartrain.engine.service import create_app as create_http_app
from geartrain.engine.state import FileStateBackend
from geartrain.engine.validator import format_diagnostics, validate_all


def _find_config_files() -> tuple[Path, Path | None]:
    """Find workspace and engine config files relative to CWD."""
    cwd = Path.cwd()
    ws_path = cwd / ".geartrain" / "workspace.yaml"
    engine_path = cwd / ".geartrain" / "engines" / "local.engine.yaml"

    if not ws_path.exists():
        return ws_path, None
    if not engine_path.exists():
        return ws_path, None
    return ws_path, engine_path


# --- Engine lifecycle -------------------------------------------------------


def _run_engine_start() -> None:
    """Start the engine: validate config, launch app and HTTP server."""
    ws_path, engine_path = _find_config_files()

    if engine_path is None or not engine_path.exists():
        print("Engine config not found. Run 'geartrain init' first.")
        sys.exit(1)

    diags = validate_all(ws_path, engine_path)
    print(format_diagnostics(diags))

    if any(d.sev == "error" for d in diags):
        sys.exit(1)

    app = EngineApp(workspace_path=ws_path, engine_path=engine_path)
    app.load_registries()
    app.start()

    host = app.engine.host
    port = app.engine.port

    import uvicorn

    config = uvicorn.Config(
        create_http_app(app),
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    def _run():
        server.run()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    print(f"Engine started on {host}:{port}")

    def _shutdown(signum, frame):
        server.should_exit = True
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        t.join()
    except KeyboardInterrupt:
        server.should_exit = True
        app.stop()
        sys.exit(0)


def _run_engine_status() -> None:
    """Query the engine API for status, or report not running."""
    engine_path = Path.cwd() / ".geartrain" / "engines" / "local.engine.yaml"

    try:
        engine = load_engine(str(engine_path))
        host = engine.host
        port = engine.port
    except FileNotFoundError:
        host = "127.0.0.1"
        port = 8420

    try:
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = resp.json()
        conn.close()

        print(f"Engine: running")
        print(f"  Workspace: {data.get('workspace', '?')}")
        print(f"  Engine: {data.get('engine', '?')}")
        agents = data.get("agents", [])
        workflows = data.get("workflows", [])
        print(f"  Agents: {', '.join(agents) if agents else 'none'}")
        print(f"  Workflows: {', '.join(workflows) if workflows else 'none'}")
    except (ConnectionRefusedError, OSError):
        print("Engine is not running")
        # Check persisted state file for last known state
        try:
            state_path = Path.cwd() / ".geartrain" / "state"
            backend = FileStateBackend(state_path)
            state = backend.read_engine_state()
            print(f"  Last state: {state.get('status', 'unknown')}")
        except (FileNotFoundError, ValueError):
            pass


def _run_agent(name: str, prompt: str) -> None:
    """Send a one-shot prompt to a named agent via the engine API and print the output."""
    engine_path = Path.cwd() / ".geartrain" / "engines" / "local.engine.yaml"
    try:
        engine = load_engine(str(engine_path))
        host = engine.host
        port = engine.port
    except FileNotFoundError:
        host = "127.0.0.1"
        port = 8420

    body = json.dumps({"task": prompt}).encode()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=600)
        conn.request(
            "POST",
            f"/agents/{name}/run",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        data = json.loads(raw)

        if resp.status == 404:
            print(f"Error: {data.get('error', f'Unknown agent: {name}')}")
            sys.exit(1)
        elif resp.status != 200:
            print(f"Error: {data.get('error', 'Agent run failed')}")
            sys.exit(1)

        print(data.get("output", ""), end="")
    except (ConnectionRefusedError, OSError):
        print("Engine is not running. Start it with 'geartrain engine start'.")
        sys.exit(1)


def _run_engine_stop() -> None:
    """Send stop signal to the running engine."""
    engine_path = Path.cwd() / ".geartrain" / "engines" / "local.engine.yaml"

    try:
        engine = load_engine(str(engine_path))
        host = engine.host
        port = engine.port
    except FileNotFoundError:
        host = "127.0.0.1"
        port = 8420

    try:
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/engine/stop")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        print("Engine stopped")
    except (ConnectionRefusedError, OSError):
        print("Engine is not running")


def _run_workflow_start(workflow_name: str = "geartrain-dev") -> None:
    """Send a start request to the running engine and print the result."""
    engine_path = Path.cwd() / ".geartrain" / "engines" / "local.engine.yaml"
    try:
        engine = load_engine(str(engine_path))
        host = engine.host
        port = engine.port
    except FileNotFoundError:
        host = "127.0.0.1"
        port = 8420

    try:
        conn = http.client.HTTPConnection(host, port, timeout=600)
        conn.request("POST", f"/workflows/{workflow_name}/start")
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        data = json.loads(raw)

        if resp.status == 404:
            print(f"Error: {data.get('error', f'Unknown workflow: {workflow_name}')}")
            sys.exit(1)
        elif resp.status not in (200, 201):
            print(f"Error: {data.get('error', 'Workflow start failed')}")
            sys.exit(1)

        status = data.get("status", "")
        if status == "already_running":
            print(f"Workflow is already running (run_id={data.get('current_run')})")
        elif status == "no_tasks":
            print(data.get("message", "No tasks found."))
        else:
            print(f"Workflow run completed: {data.get('run_id', '?')} — {status}")
    except (ConnectionRefusedError, OSError):
        print("Engine is not running. Start it with 'geartrain engine start'.")
        sys.exit(1)


# --- Run observability ------------------------------------------------------


def _state_backend() -> FileStateBackend:
    """Build a state backend pointed at the local engine state directory."""
    engine_path = Path.cwd() / ".geartrain" / "engines" / "local.engine.yaml"
    try:
        engine = load_engine(str(engine_path))
        state_path = Path(engine.state.path)
    except FileNotFoundError:
        state_path = Path.cwd() / ".geartrain" / "state"
    return FileStateBackend(state_path)


def _run_run_list() -> None:
    """List recorded runs, newest first."""
    backend = _state_backend()
    runs = backend.list_runs()
    if not runs:
        print("No runs found.")
        return
    for run in runs:
        print(
            f"{run.get('run_id', '?')}  "
            f"[{run.get('status', '?')}]  "
            f"{run.get('workflow', '?')}  "
            f"{run.get('started_at', '')}"
        )


def _run_run_summary(run_id: str) -> None:
    """Print a compact summary of one run."""
    backend = _state_backend()
    try:
        summary = summarize_run(backend, run_id)
    except (FileNotFoundError, ValueError):
        print(f"Unknown run: {run_id}")
        sys.exit(1)
    events_log = str(backend.state_path / "runs" / run_id / "events.jsonl")
    print(render_summary(summary, events_log=events_log))


def _run_run_events(run_id: str) -> None:
    """Print the ordered event timeline for one run."""
    backend = _state_backend()
    try:
        backend.read_run_state(run_id)
    except (FileNotFoundError, ValueError):
        print(f"Unknown run: {run_id}")
        sys.exit(1)
    print(render_timeline(backend.read_events(run_id)))


# --- Parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "geartrain",
        description="Local AI engineering agent orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- engine --
    engine = subparsers.add_parser("engine", help="Engine lifecycle management")
    engine_sub = engine.add_subparsers(dest="engine_action")

    engine_sub.add_parser("start", help="Start the local engine")
    engine_sub.add_parser("stop", help="Stop the running engine")
    engine_sub.add_parser("status", help="Show engine status")

    # -- validate --
    val = subparsers.add_parser("validate", help="Validate workspace configuration")
    val.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["workspace", "engine", "agent", "workflow", "memory", "all"],
        help="What to validate (default: all)",
    )

    # -- agent --
    agent = subparsers.add_parser("agent", help="Run an agent directly")
    agent.add_argument("agent_name", help="Name of the agent to run")
    agent.add_argument("prompt", help="Prompt to send to the agent")

    # -- workflow --
    workflow = subparsers.add_parser("workflow", help="Workflow management")
    workflow_sub = workflow.add_subparsers(dest="workflow_action")
    workflow_sub.add_parser("start", help="Start a workflow run")

    # -- run --
    run = subparsers.add_parser("run", help="Inspect workflow runs")
    run_sub = run.add_subparsers(dest="run_action")
    run_sub.add_parser("list", help="List recorded runs")
    run_summary = run_sub.add_parser("summary", help="Show a run summary")
    run_summary.add_argument("run_id", help="Run id to summarize")
    run_events = run_sub.add_parser("events", help="Show a run's event timeline")
    run_events.add_argument("run_id", help="Run id to inspect")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "engine":
        if not args.engine_action:
            parser.parse_args(["engine", "-h"])
        elif args.engine_action == "start":
            _run_engine_start()
        elif args.engine_action == "status":
            _run_engine_status()
        elif args.engine_action == "stop":
            _run_engine_stop()

    elif args.command == "validate":
        ws_path, engine_path = _find_config_files()
        diags = validate_all(ws_path, engine_path)
        print(format_diagnostics(diags))
        has_errors = any(d.sev == "error" for d in diags)
        sys.exit(1 if has_errors else 0)

    elif args.command == "agent":
        _run_agent(args.agent_name, args.prompt)

    elif args.command == "workflow":
        if not args.workflow_action:
            parser.parse_args(["workflow", "-h"])
        elif args.workflow_action == "start":
            _run_workflow_start()

    elif args.command == "run":
        if not args.run_action:
            parser.parse_args(["run", "-h"])
        elif args.run_action == "list":
            _run_run_list()
        elif args.run_action == "summary":
            _run_run_summary(args.run_id)
        elif args.run_action == "events":
            _run_run_events(args.run_id)


if __name__ == "__main__":
    main()
