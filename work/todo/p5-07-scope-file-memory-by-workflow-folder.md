---
id: GT-P5-07
phase: 5
status: todo
depends_on:
  - GT-P5-02
  - GT-P5-04
  - GT-P8-00
---

# Scope File-Based Memory by Workflow Folder

Make file-based memory providers scope workflow memory to a per-workflow folder
under the workspace's configured memory roots, with cwd-independent paths.

## Problem

`EngineApp` builds the store as `MarkdownMemoryStore(self.workspace.memory.root)`
from a single `memory.root` that is cwd-relative — it was not anchored to the
workspace config location when GT-P8-00 anchored state, logs, and work paths.

The store also ignores the workspace's configured memory folders. The workspace
config declares separate roots (`memory.workspace`, `memory.workflows`,
`memory.agent_types`), but `MarkdownMemoryStore._dir` derives its own layout
under the single root (`<root>/<system>/workflow/<name>/`). Workflow-scoped
memory is namespaced by workflow name inside that shared root rather than living
in the workflow's own configured folder.

## Scope

- Anchor the file store root(s) to the workspace config location at load,
  consistent with GT-P8-00's path anchoring. This is a file-provider concern;
  other backing stores (DB, S3) resolve paths their own way.
- Map memory scopes to the workspace's configured folders: `workspace` →
  `memory.workspace`, `workflow` → `memory.workflows/<workflow>`, `agent_level`
  → `memory.agent_types/<agent_type>`. Keep the memory/knowledge system split.
- Give each workflow its own folder so workflow-scoped entries are isolated:
  one workflow cannot read another's workflow-scoped memory.
- Update the `EngineApp` wiring to build the file store from the anchored,
  configured roots.

## Requirements

- Scope isolation and visibility from GT-P5-04 are preserved: a workflow's reads
  and writes target only its own folder.
- Memory paths resolve independent of the working directory.
- The memory and knowledge bases stay separated.
- This targets file-based providers; the `MemoryStore` protocol and any
  non-file providers are unaffected.

## Acceptance Criteria

- Workflow-scoped writes land under `memory.workflows/<workflow>`; a second
  workflow cannot read the first workflow's workflow-scoped entries.
- Workspace- and agent-level scopes resolve to their configured folders.
- Memory reads and writes work the same regardless of `os.getcwd()`.
- Tests cover per-workflow folder scoping, the scope→folder mapping, and
  cwd-independent resolution. The full suite stays green.
