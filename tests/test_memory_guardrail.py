"""Tests for the secret-pattern write guardrail (GT-P5-05)."""

import pytest

from geartrain.memory import MarkdownMemoryStore, MemoryScope, MemorySystem
from geartrain.memory.guardrail import scan_for_secrets


class TestScanForSecrets:
    def test_clean_content_passes(self):
        result = scan_for_secrets("Run the tests before opening a PR.")
        assert result.ok
        assert result.findings == []

    @pytest.mark.parametrize(
        "content",
        [
            "AKIAIOSFODNN7EXAMPLE",
            "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "-----BEGIN RSA PRIVATE KEY-----",
            "password=hunter2secret",
            "api_key = 'sk-abcdefghijklmnopqrstuvwxyz'",
            "xoxb-1234567890-abcdefghijkl",
        ],
    )
    def test_secret_shapes_flagged(self, content):
        result = scan_for_secrets(content)
        assert not result.ok
        assert result.findings

    def test_findings_name_patterns_without_values(self):
        result = scan_for_secrets("AKIAIOSFODNN7EXAMPLE")
        assert "aws-access-key-id" in result.findings
        # The report carries labels, not the secret itself.
        assert "AKIA" not in "".join(result.findings)


class TestGuardrailOnWrite:
    def test_write_with_secret_rejected(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        result = store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="The deploy key is AKIAIOSFODNN7EXAMPLE, keep it safe.",
        )
        assert result.status == "rejected"
        assert result.path == ""
        assert result.guardrail["ok"] is False
        assert "aws-access-key-id" in result.guardrail["findings"]
        # Nothing was written.
        assert store.list_entries(
            system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
        ) == []

    def test_clean_write_succeeds(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        result = store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="Use the staging environment for smoke tests.",
        )
        assert result.ok
        assert result.guardrail == {"ok": True, "findings": []}

    def test_update_with_secret_rejected(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        result = store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="clean note",
        )
        rejected = store.update(
            result.path,
            content="now leaking ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        )
        assert rejected.status == "rejected"
        # Original content is untouched.
        kept = store.list_entries(
            system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
        )
        assert kept[0].content == "clean note"
