"""CLI agent runner — invokes an external command via a sandbox."""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

from geartrain.agents.context_builder import ContextBuilder

if TYPE_CHECKING:
    from geartrain.engine.config import AgentDefinition
    from geartrain.engine.sandbox import Sandbox


class CliAgentRunner:
    """Agent runner that delegates to a CLI subprocess.

    Builds a prompt via the shared ContextBuilder and executes the
    configured command through the sandbox interface.
    """

    def __init__(self, agent_def: "AgentDefinition", sandbox: "Sandbox") -> None:
        self.agent_def = agent_def
        self.sandbox = sandbox

    def run(self, task: str, context: dict) -> str:
        """Run the CLI agent with the given task and context.

        Builds the prompt, executes the configured command, and returns
        the plain text output.

        Raises RuntimeError on non-zero exit.
        """
        # Build prompt
        project_root = context.get("project_root", ".")
        project_name = context.get("project_name", "")
        work_folder = self.agent_def.config.work_folder

        builder = ContextBuilder(
            project_root=project_root,
            project_name=project_name,
            work_folder=work_folder,
        )

        if self.agent_def.system_prompt:
            builder.with_agent_instructions(self.agent_def.system_prompt)

        builder.with_task(task)

        # Add prior outputs from context
        for node_id, output in context.get("prior_outputs", []):
            builder.with_prior_output(node_id, output)

        # Add memory entries from context
        for scope, entries in context.get("memory_entries", []):
            builder.with_memory_entries(scope, entries)

        prompt = builder.build()

        # Execute via sandbox
        cmd = self.agent_def.config.command
        timeout = self.agent_def.config.timeout_seconds

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            full_command = f"{cmd} {prompt_file}"
            stdout, stderr, returncode = self.sandbox.execute_command(
                full_command,
                timeout=timeout,
            )

            if returncode != 0:
                raise RuntimeError(
                    f"Agent command failed (exit {returncode}): "
                    f"{stderr.strip()}"
                )

            return stdout
        finally:
            os.unlink(prompt_file)
