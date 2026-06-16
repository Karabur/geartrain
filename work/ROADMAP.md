# GearTrain Roadmap

MVP is the dogfooding milestone: the GearTrain team can clone the repo, run the feature-development workflow, and get a working PR. The MVP is delivered as a set of phases. Each phase covers one module and stands on its own. Phases 1-3 deliver the first runnable version of GearTrain; phases 1-8 deliver the MVP.

Tasks live as markdown files in `work/todo|in-progress|done/`. Each task's `phase` frontmatter field ties it to a phase here. The folder is the task state; this file is the grouping and order. Linear and other external trackers are not used.

Cross-cutting decisions: `geartrain validate` checks every MVP config file (workspace, engine, agent, workflow, memory). The CLI shape is `geartrain <module> <command>` or `geartrain <global-command>`. Workflow error handling is log-and-stop. Memory is plain markdown files as the single source of truth, edited by humans and agents. Agent sandboxing is out of scope but a no-op sandbox layer keeps the architecture ready for it.

## Phase 1: Engine Foundation & Config

The engine starts, loads and validates every MVP config file, writes file-backed state, and serves a local HTTP API. No agents run yet.

- `GT-P1-01` Create Project Backbone
- `GT-P1-02` Create Workspace and Engine Config Scaffold
- `GT-P1-03` Define Config Models and YAML Loading
- `GT-P1-04` Implement Config Validation and `geartrain validate`
- `GT-P1-05` Implement File-Backed Engine and Run State
- `GT-P1-06` Implement Engine HTTP Service
- `GT-P1-07` Implement Engine CLI Lifecycle Commands
- `GT-P1-08` Add No-op Sandbox and Memory Managers

## Phase 2: CLI Agent Type & Direct Execution

A named `cli` agent (default `codex exec`) runs one-shot behind the shared agent interface, callable directly from the CLI.

- `GT-P2-01` Define Agent Interface and Factory
- `GT-P2-02` Implement Shared Context Builder
- `GT-P2-03` Implement CLI Agent Runner
- `GT-P2-04` Implement Direct Agent CLI Command
- `GT-P2-05` Add CLI Agent Tests

## Phase 3: Workflow Engine & Runnable Version (runnable version)

The generic YAML-driven workflow engine runs the `geartrain-dev` workflow end to end from the CLI. This phase delivers the first runnable version of GearTrain.

- `GT-P3-01` Implement Work Folder Task Helpers
- `GT-P3-02` Implement Workflow Factory
- `GT-P3-03` Implement Node Types
- `GT-P3-04` Implement Workflow Error Handling
- `GT-P3-05` Implement Workflow Locking
- `GT-P3-06` Implement geartrain-dev Workflow
- `GT-P3-07` Implement Workflow Start CLI Command
- `GT-P3-08` Add Lead Workflow-Start Tool
- `GT-P3-09` Add Runnable-Version Smoke Tests
- `GT-P3-10` Write Runnable-Version Documentation

## Phase 4: LangChain Agent Type

A `langchain` agent runs in-process with GearTrain tools and context, selectable per agent with no workflow change.

- `GT-P4-01` Implement LangChain Agent Runner
- `GT-P4-02` Implement Core File and Search Tools
- `GT-P4-03` Implement Shell and Git Tools
- `GT-P4-04` Implement LLM Provider Resolution
- `GT-P4-05` Wire Context and Prompt Interpolation for LangChain
- `GT-P4-06` Add LangChain Agent Tests

## Phase 5: Memory & Knowledge System

Agents read from and write to git-backed markdown memory. The markdown files are the single source of truth, editable by both humans and agents.

- `GT-P5-01` Define MemoryStore Protocol and Scopes
- `GT-P5-02` Implement MarkdownMemoryStore
- `GT-P5-03` Implement Memory and Knowledge Tools
- `GT-P5-04` Implement Scope Isolation and Visibility
- `GT-P5-05` Implement Secret-Pattern Write Guardrail
- `GT-P5-06` Add Memory Tests

## Phase 6: GitHub Integration

A workflow can create a branch, commit changes, open a PR, and read/update issues.

- `GT-P6-01` Implement GitHub Branch, Commit, and PR Creation
- `GT-P6-02` Implement GitHub Issue Read and Update
- `GT-P6-03` Expose GitHub as Tools and Integration Node
- `GT-P6-04` Add GitHub Integration Tests

## Phase 7: Web UI

A minimal local web UI shows workflow state, handles human checkpoints, and browses memory.

- `GT-P7-01` Implement Web API Endpoints
- `GT-P7-02` Implement WebSocket State Updates
- `GT-P7-03` Scaffold React + Vite App
- `GT-P7-04` Build Dashboard and Workflow Detail Pages
- `GT-P7-05` Build Checkpoint Page
- `GT-P7-06` Build Memory Browser Page

## Phase 8: Dogfooding (MVP)

The GearTrain team can clone the repo, run the feature-development workflow, and get a working PR. This phase is the MVP.

- `GT-P8-01` Define Dogfooding Agents
- `GT-P8-02` Define feature-development Workflow
- `GT-P8-03` Seed Project Memory
- `GT-P8-04` Run End-to-End Dogfooding to a PR
- `GT-P8-05` Add Critical-Path Integration Tests
- `GT-P8-06` Write Setup, User, and Contributor Docs
