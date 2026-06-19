# GearTrain Roadmap

MVP is the dogfooding milestone: the GearTrain team can clone the repo, run the feature-development workflow, and get a working PR. The MVP is delivered as a set of phases. Each phase covers one module and stands on its own. Phases 1-3 deliver the first runnable version of GearTrain; phases 1-8 deliver the MVP. Phase 9 is post-MVP UI and dashboards.

Tasks live as markdown files in `work/todo|in-progress|done/`. Each task's `phase` frontmatter field ties it to a phase here. The folder is the task state; this file is the grouping and order. Linear and other external trackers are not used.

Cross-cutting decisions: `geartrain validate` checks every MVP config file (workspace, engine, agent, workflow, memory). The CLI shape is `geartrain <module> <command>` or `geartrain <global-command>`. Workflow execution is run-based: workflow definitions are recipes, while runs own node state, attempts, checkpoints, and append-only events. Workflow error handling is log-and-stop. Memory is plain markdown files as the single source of truth, edited by humans and agents. Agent sandboxing is out of scope but a no-op sandbox layer keeps the architecture ready for it.

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
- `GT-P5-07` Scope File-Based Memory by Workflow Folder (follow-up)

## Phase 6: GitHub Integration

A workflow can create a branch, commit changes, open a PR, and read/update issues.

- `GT-P6-01` Implement GitHub Branch, Commit, and PR Creation
- `GT-P6-02` Implement GitHub Issue Read and Update
- `GT-P6-03` Expose GitHub as Tools and Integration Node
- `GT-P6-04` Add GitHub Integration Tests

## Phase 7: Run Observability Architecture

The engine exposes run-based observability without shipping dashboards. This phase makes runs, node runs, attempts, checkpoints, errors, timings, tool calls, and memory updates queryable and streamable. The MVP output is a minimal human-facing log plus a structured event log.

- `GT-P7-01` Implement Run Query API Endpoints
- `GT-P7-02` Implement Run Event Streaming
- `GT-P7-03` Record Tool Call Events
- `GT-P7-04` Record Memory Update Events
- `GT-P7-05` Add Error, Timing, and Event Log Summaries
- `GT-P7-06` Add Observability Contract Tests

## Phase 8: Dogfooding (MVP)

The GearTrain team can clone the repo, run the feature-development workflow, and get a working PR. This phase is the MVP.

- `GT-P8-00` Make Workflow Execution Config-Driven (prerequisite: remove the hardcoded geartrain-dev path)
- `GT-P8-01` Define Dogfooding Agents
- `GT-P8-02` Define feature-development Workflow
- `GT-P8-03` Seed Project Memory
- `GT-P8-04` Run End-to-End Dogfooding to a PR
- `GT-P8-05` Add Critical-Path Integration Tests
- `GT-P8-06` Write Setup, User, and Contributor Docs

## Phase 9: UI and Dashboards (post-MVP)

A local web UI makes GearTrain runs inspectable and comfortable to operate. It reads the run APIs and event streams built in Phase 7.

- `GT-P9-01` Scaffold React + Vite App
- `GT-P9-02` Build Workflow and Run Dashboards
- `GT-P9-03` Build Checkpoint Page
- `GT-P9-04` Build Memory Browser Page
- `GT-P9-05` Build Tool Call and Memory Update Inspectors
- `GT-P9-06` Add UI Smoke and Accessibility Tests
