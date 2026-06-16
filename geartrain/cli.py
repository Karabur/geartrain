"""CLI entrypoint for GearTrain.

Usage:
    geartrain <global-command>
    geartrain <module> <command> [args]
"""

import argparse
import os
import sys
from pathlib import Path

from geartrain.engine.validator import (
    format_diagnostics,
    validate_all,
    validate_engine,
    validate_workflow,
    validate_workspace,
)


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


def _run_validate() -> int:
    """Run validation and return exit code."""
    ws_path, engine_path = _find_config_files()

    diags = validate_all(ws_path, engine_path)
    print(format_diagnostics(diags))

    has_errors = any(d.sev == "error" for d in diags)
    return 1 if has_errors else 0


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

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "engine":
        if not args.engine_action:
            engine_parser = parser.parse_args(["engine", "-h"])
        print(f"Engine: {args.engine_action}")

    elif args.command == "validate":
        rc = _run_validate()
        sys.exit(rc)

    elif args.command == "agent":
        print(f"Agent: running '{args.agent_name}' with prompt: {args.prompt}")

    elif args.command == "workflow":
        if not args.workflow_action:
            parser.parse_args(["workflow", "-h"])
        print(f"Workflow: {args.workflow_action}")


if __name__ == "__main__":
    main()
