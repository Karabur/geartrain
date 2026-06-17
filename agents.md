# Agent Instructions

Shared instructions for all AI coding agents working in this project. Agent-specific config files (listed below) symlink here so every agent reads the same rules.

## Writing Style

All generated documentation — READMEs, inline comments, PR descriptions, commit messages, design docs — must follow the style defined in [WRITING_STYLE.md](WRITING_STYLE.md). Read it before producing any written content.

## General Rules

Work in an agent-agnostic and model-agnostic way. Don't rely on features unique to one agent or model. Keep instructions, prompts, and tooling portable across providers.

Agent-specific config files should be symlinks to this file, not copies. One source of truth.

## Task Tracking

Tasks are tracked as markdown files in `work/`, not in Linear or any external tracker. `work/ROADMAP.md` defines the phases; tasks move through `work/todo|in-progress|done/` and carry a `phase` frontmatter field. See `work/README.md` for the format.

## Python Environment

The venv is already activated in this shell. Do not call `source` or activate the venv before running Python commands — just run them directly.

## Multi-Ticket Workflow

When working through a queue of tasks:
1. Take the next ticket from `work/todo/`
2. Spawn a subagent to implement it
3. Commit the changes
4. Move the ticket file to `work/done/`
5. Repeat

## Imported Claude Cowork project instructions

All work done here should be in agent and model agnostic way. agent-specific files should be symlinks to generic instructions and skills.
