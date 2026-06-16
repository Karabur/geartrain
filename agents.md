# Agent Instructions

Shared instructions for all AI coding agents working in this project. Agent-specific config files (listed below) symlink here so every agent reads the same rules.

## Writing Style

All generated documentation — READMEs, inline comments, PR descriptions, commit messages, design docs — must follow the style defined in [WRITING_STYLE.md](WRITING_STYLE.md). Read it before producing any written content.

## General Rules

Work in an agent-agnostic and model-agnostic way. Don't rely on features unique to one agent or model. Keep instructions, prompts, and tooling portable across providers.

Agent-specific config files should be symlinks to this file, not copies. One source of truth.

## Task Tracking

Tasks are tracked as markdown files in `work/`, not in Linear or any external tracker. `work/ROADMAP.md` defines the phases; tasks move through `work/todo|in-progress|done/` and carry a `phase` frontmatter field. See `work/README.md` for the format.

## Imported Claude Cowork project instructions

All work done here should be in agent and model agnostic way. agent-specific files should be symlinks to generic instructions and skills.
