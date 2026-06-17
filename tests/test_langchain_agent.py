"""End-to-end langchain agent tests with a stub LLM (GT-P4-06).

Proves a langchain coder reads, edits, and runs tests through tools, and that
the same workflow node runs a coder under either agent ``type`` unchanged. No
real LLM calls — the model is a scripted stub.
"""

from langchain_core.messages import AIMessage

from geartrain.agents.cli_runner import CliAgentRunner
from geartrain.agents.langchain_runner import LangchainAgentRunner
from geartrain.engine.config import (
    AgentDefinition,
    CliAgentConfig,
    LangchainAgentConfig,
)
from geartrain.engine.sandbox import NoopSandbox
from geartrain.workflows.nodes import AgentNodeRunner
from tests.stub_chat_model import StubChatModel, tool_call_message


def _coder(tools) -> AgentDefinition:
    return AgentDefinition(
        schema_version=1,
        name="coder",
        config=LangchainAgentConfig(type="langchain", tools=tools),
        system_prompt="You implement changes.",
    )


def test_coder_reads_edits_and_runs_tests(tmp_path):
    """The agent reads a file, writes a change, runs a command, then finishes."""
    target = tmp_path / "calc.py"
    target.write_text("def add(a, b):\n    return a - b\n")  # bug: subtracts

    # Script the model: read -> write fix -> run tests -> final answer.
    stub = StubChatModel(
        responses=[
            tool_call_message("file_read", {"path": "calc.py"}, "c1"),
            tool_call_message(
                "file_write",
                {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"},
                "c2",
            ),
            tool_call_message("shell_exec", {"command": "echo tests pass"}, "c3"),
            AIMessage(content="Fixed the bug in add()."),
        ]
    )

    runner = LangchainAgentRunner(
        _coder(["file_read", "file_write", "shell_exec"]),
        NoopSandbox(),
        llm=stub,
        tool_root=str(tmp_path),
        shell_cwd=str(tmp_path),
    )

    output = runner.run("Fix the add function", {"project_name": "Calc"})

    assert output == "Fixed the bug in add()."
    assert target.read_text() == "def add(a, b):\n    return a + b\n"

    names = [e.name for e in runner.recorder.events]
    assert names == ["file_read", "file_write", "shell_exec"]
    assert all(e.status == "ok" for e in runner.recorder.events)


def test_same_workflow_node_runs_either_agent_type(tmp_path):
    """One AgentNodeRunner runs a cli coder and a langchain coder unchanged."""
    node_def = {"agent": "coder", "transitions": {"default": "next"}}
    context = {"task": "summarize", "project_name": "X"}

    # CLI coder: `cat` echoes the assembled prompt back.
    cli_coder = CliAgentRunner(
        AgentDefinition(
            schema_version=1,
            name="coder",
            config=CliAgentConfig(
                type="cli", command="cat", credential="c.default"
            ),
            system_prompt="cli coder",
        ),
        NoopSandbox(),
    )
    cli_result = AgentNodeRunner({"coder": cli_coder}).run(node_def, context)
    assert cli_result.status == "ok"
    assert cli_result.next_node == "next"
    assert "summarize" in cli_result.output

    # LangChain coder: stub returns a final answer; same node, same call.
    lc_coder = LangchainAgentRunner(
        _coder([]),
        NoopSandbox(),
        llm=StubChatModel(responses=[AIMessage(content="summary done")]),
        tool_root=str(tmp_path),
    )
    lc_result = AgentNodeRunner({"coder": lc_coder}).run(node_def, context)
    assert lc_result.status == "ok"
    assert lc_result.next_node == "next"
    assert lc_result.output == "summary done"
