"""Tests for the CLI agent runner (GT-P2-03)."""

import pytest

from geartrain.agents.cli_runner import CliAgentRunner
from geartrain.engine.config import AgentDefinition, CliAgentConfig
from geartrain.engine.sandbox import NoopSandbox


def _make_agent(
    command: str = "echo fake-codex",
    timeout: int = 30,
    work_folder: str = "work",
    system_prompt: str = "You are a coder.",
) -> AgentDefinition:
    """Create a minimal AgentDefinition for testing."""
    return AgentDefinition(
        schema_version=1,
        name="test-agent",
        config=CliAgentConfig(
            type="cli",
            command=command,
            timeout_seconds=timeout,
            work_folder=work_folder,
            sandbox="workspace-write",
            credential="test.cred",
        ),
        system_prompt=system_prompt,
    )


class TestCliAgentRunner:
    def test_run_returns_stdout_on_success(self):
        """cat echoes the file content (our prompt)."""
        agent = _make_agent(command="cat")
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        result = runner.run(
            "Hello world",
            {"project_root": "/tmp", "project_name": "test"},
        )

        assert "Hello world" in result
        assert "Project Context" in result

    def test_run_with_context_sections(self):
        """Prior outputs and memory entries appear in the prompt."""
        agent = _make_agent(command="cat")
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        context = {
            "project_root": "/app",
            "project_name": "MyApp",
            "prior_outputs": [("intake", "Approved")],
            "memory_entries": [("workspace", ["Remember this"])],
        }

        result = runner.run("Do the task", context)

        assert "Do the task" in result
        assert "Approved" in result
        assert "Remember this" in result
        assert "MyApp" in result

    def test_run_raises_on_nonzero_exit(self):
        """Non-zero exit raises RuntimeError with exit code."""
        agent = _make_agent(command="false")
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        with pytest.raises(RuntimeError) as exc:
            runner.run(
                "fail",
                {"project_root": "/tmp", "project_name": "x"},
            )

        assert "exit 1" in str(exc.value)

    def test_run_uses_work_folder(self):
        """Work folder from config appears in the prompt."""
        agent = _make_agent(command="cat", work_folder="my-work")
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        result = runner.run(
            "task",
            {"project_root": "/tmp", "project_name": "x"},
        )

        assert "my-work" in result

    def test_run_uses_system_prompt(self):
        """System prompt from agent config appears in the prompt."""
        agent = _make_agent(
            command="cat",
            system_prompt="Custom instructions.",
        )
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        result = runner.run(
            "task",
            {"project_root": "/tmp", "project_name": "x"},
        )

        assert "Custom instructions" in result

    def test_run_empty_context(self):
        """Empty context dict still produces valid output."""
        agent = _make_agent(command="cat")
        sandbox = NoopSandbox()
        runner = CliAgentRunner(agent, sandbox)

        result = runner.run("simple task", {})

        assert "simple task" in result
