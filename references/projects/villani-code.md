# Villani Code

**Type:** Open-source Python coding-agent runtime
**Repository:** [mmprotest/villani-code](https://github.com/mmprotest/villani-code)
**Reviewed:** June 8, 2026 at commit [`e7631f9`](https://github.com/mmprotest/villani-code/commit/e7631f9895b8f4e48c49f31587fdebbc3f4e336c)

## What It Does

Villani Code runs coding tasks against local or OpenAI-compatible models. It targets bounded repository work where success can be checked with files, diffs, commands, and tests.

Its main claim is that runtime design can make the same small model complete more tasks. The runtime narrows the model's choices, injects repository evidence, rejects broad or unsupported edits, verifies effects, and starts bounded repair attempts when validation fails.

Villani is a coding-agent runtime. GearTrain is a workflow engine that can run coding agents as nodes. The useful lesson is therefore not to replace GearTrain with Villani. It is to move some coding reliability out of prompts and into GearTrain's runtime contracts.

## Evidence And Claim Limits

Villani has published two different benchmark stories.

An earlier self-published comparison reported Villani against Claude Code on 40 project-authored tasks using the same Qwen3.5 model sizes:

| Model | Villani | Claude Code |
|---|---:|---:|
| Qwen3.5 4B | 33/40 | 28/40 |
| Qwen3.5 9B | 34/40 | 30/40 |
| Qwen3.5 27B | 37/40 | 28/40 |

The repository classified the runners as only approximately comparable because their telemetry and internal behavior differed. The benchmark also supplied both runners with a shared task contract containing expected files, allowed paths, visible verification commands, and time limits. Villani additionally consumed those fields as runtime policy.

The current `main` branch instead leads with a Terminal-Bench 2.0 result: Qwen3.5-9B completed 92 of 445 attempts across 89 tasks, or 20.67%. This is a broader external benchmark, but the reported leaderboard position is calculated by the project rather than published as an official Terminal-Bench submission.

These results support a narrower conclusion than "Villani is better than Claude Code": Villani's control layer improves small-model performance on bounded, verifier-friendly tasks. They don't establish an advantage for open-ended development, architecture work, long interactive sessions, or frontier models.

Sources:

- [Current README and Terminal-Bench claim](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/README.md)
- [Current Terminal-Bench report](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/docs/Villani_Code_9B_Terminal_Bench_Technical_Report_Leaderboard.pdf)
- [Earlier same-model comparison](https://github.com/mmprotest/villani-code/blob/d5d9472/README.md)
- [Benchmark prompt contract](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/benchmark/prompt_contract.py)
- [Claude Code benchmark adapter](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/benchmark/agents/claude_code.py)

## How The Runtime Improves Results

### 1. It Turns The Task Into An Execution Contract

Villani classifies the task, identifies likely target files, estimates scope and impact, defines a success predicate, and records no-go paths before the main tool loop starts.

The model receives a short instruction to name a likely target file, keep scope tight, verify the required behavior, and stop if verification repeats without new evidence.

This removes decisions that small models handle poorly from every turn. The runtime owns task boundaries. The model works inside them.

Source: [planning.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/planning.py)

### 2. It Supplies A Compact Repository Map

Villani builds a local repository index, extracts symbols and snippets, creates an 8,000-character repository map, and uses BM25 retrieval to inject up to eight likely files before a model call.

This is simple retrieval, not semantic RAG. Its value comes from being cheap, deterministic, and tied to paths and symbols. The model starts with a shortlist instead of exploring the whole repository.

Sources:

- [indexing.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/indexing.py)
- [retrieval.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/retrieval.py)
- [repo_map.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/repo_map.py)

### 3. It Enforces Tool Discipline In Code

The runtime uses strict Pydantic schemas for tools and rejects extra fields. In constrained modes it also:

- auto-reads an existing file before editing it
- blocks writes to ignored or non-authoritative paths
- locks edits to intended targets
- allows one evidence-backed scope expansion
- caps reads, search results, and tool output
- rejects large whole-file writes
- converts safe full-file writes into patches
- rejects rewrite-heavy patches

This is stronger than telling the model to "make a minimal change." The runtime makes broad or unsupported actions impossible.

Sources:

- [tools.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/tools.py)
- [state_runtime.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/state_runtime.py)
- [state_tooling.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/state_tooling.py)

### 4. It Uses Evidence Instead Of Model Self-Reporting

Villani tracks intended targets, pre-edit contents, attributed git changes, command exit codes, validation artifacts, and files examined. Effectful tasks can't pass without a real change. Validation tasks can't pass without command evidence.

It also checks whether cumulative changes match the intended effect. A final answer isn't treated as proof of completion.

Sources:

- [autonomy.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/autonomy.py)
- [evidence.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/evidence.py)

### 5. It Selects Validation From The Change

The validation planner classifies changed files and change impact. It runs cheap checks first, maps source files to nearby tests, uses targeted tests where possible, and broadens validation for config, dependency, package-wide, or uncertain changes.

On failure, a separate repair call receives only the task summary, changed files, failing step, compact failure signal, and prior attempts. Repair is capped at two attempts by default.

Sources:

- [validation_loop.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/validation_loop.py)
- [repair.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/repair.py)

### 6. It Detects Stalls And Stops Them

A bounded task gets 20 turns, 40 tool calls, 180 seconds, eight no-edit turns, and six consecutive reconnaissance turns. Repeated no-progress responses trigger progressively narrower recovery instructions. Repeated verification without new evidence forces a strategy change or stop.

This prevents a weak model from spending its full budget rereading files or rerunning the same failed command.

Sources:

- [execution.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/execution.py)
- [state.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/state.py)

### 7. It Treats Context As Runtime State

Villani preserves recent tool-call pairs, compacts older tool results, records why context was included or excluded, measures budget pressure, detects stale context, and writes compact checkpoints after validation.

The implementation is basic and character-based, but the ownership is correct: context selection and compaction belong to the runtime, not each agent prompt.

Sources:

- [context_budget.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/context_budget.py)
- [context_governance.py](https://github.com/mmprotest/villani-code/blob/e7631f9895b8f4e48c49f31587fdebbc3f4e336c/villani_code/context_governance.py)

## What GearTrain Should Adopt

### Add A Runtime Execution Contract

GearTrain's workflow nodes currently pass prompts and plain text outputs. Add an optional execution contract generated before an agent runs:

```yaml
execution:
  task_mode: fix_failing_test
  target_files:
    - geartrain/agents/codex.py
  allowed_paths:
    - geartrain/agents/
    - tests/
  max_files_changed: 3
  success_predicate: "non-zero Codex exits become clear engine errors"
  validation:
    - pytest -q tests/test_codex_agent.py
  budget:
    max_seconds: 180
    max_attempts: 2
```

The contract should live in workflow run state and be available to any agent adapter. Codex can receive it as prompt context now. Future native runtimes can enforce it directly.

### Store Evidence As A First-Class Node Result

Keep the agent's plain text response, but don't use it as the workflow's completion signal. Add a runtime-owned result envelope:

```yaml
status: passed
exit_code: 0
changed_files:
  - geartrain/agents/codex.py
validation:
  - command: pytest -q tests/test_codex_agent.py
    exit_code: 0
artifacts:
  stdout: coder-output.md
  stderr: coder-stderr.txt
```

This fits GearTrain's file-backed state model. It also gives the lead agent compact, trustworthy inputs instead of another agent's narrative.

### Add A Verifier Node Before Lead Review

The first `geartrain-dev` workflow should become:

```text
select task -> build contract -> run coder -> collect evidence -> verify -> lead review -> log
```

The verifier can start deterministic:

- required files changed when the task is effectful
- changes stay within allowed paths
- configured validation commands exit zero
- the run did not exceed file or time budgets
- no new runtime artifacts appeared outside `.geartrain/state/`

This should be engine code, not a second LLM. Add model-based review only after deterministic evidence is exhausted.

### Add Bounded Repair As A Workflow Policy

If verification fails, rerun `coder` with only:

- the original execution contract
- changed files
- the failed command
- a compact error excerpt
- prior repair attempts

Cap repair at one attempt for the first milestone. Store each attempt separately. Don't append the full original transcript.

### Add Cheap Repository Retrieval Before Semantic RAG

GearTrain already plans explicit context budgets and later retrieval. Villani shows that a small local index plus path, symbol, and snippet ranking is enough to improve localization.

Start with:

1. repository tree and manifest detection
2. symbol extraction for supported languages
3. BM25 or equivalent keyword ranking
4. a fixed top-k file briefing
5. explicit inclusion reasons in run state

This is a better first step than introducing embeddings or a vector database.

### Add Progress Budgets To Agent Definitions

Extend the existing `runtime` block with adapter-neutral limits:

```yaml
runtime:
  timeout_seconds: 180
  max_attempts: 2
  max_files_changed: 3
  max_no_progress_attempts: 1
  require_change_evidence: true
  require_validation_evidence: true
```

For `codex exec`, GearTrain can enforce elapsed time, process exit, workspace diff, and retry count even though Codex owns its internal tool loop.

### Build The Eval Harness Early

Villani's strongest product practice is measuring the runtime rather than assuming prompt changes help.

GearTrain should keep a small fixture suite with:

- single-file bug fix
- file localization
- terminal or config repair
- two-file contract change
- false-fix trap with a hidden check
- no-op task that must not produce a patch

Run the same task and model through different GearTrain contracts or adapters. Record solve rate, time, attempts, files touched, validation commands, and failure class.

## What GearTrain Should Not Copy

**Don't expose benchmark answers as production context.** Villani's benchmark runtime receives expected files, allowlists, and visible verification commands. This is useful for controlled evaluation but can overstate general file-localization ability.

**Don't make autonomous repository cleanup the core workflow.** Villani mode uses fixed heuristics such as missing tests, importability, TODOs, and docs drift. GearTrain should keep task selection in workflow definitions and user-controlled work queues.

**Don't rely on its verifier as sufficient proof.** Parts of Villani's adversarial verifier are shallow heuristics such as TODO detection and file-count thresholds. GearTrain should prefer task-specific deterministic checks.

**Don't make an LLM critic mandatory.** Villani uses a small model call to judge whether cumulative effects match intent. This adds cost and can create another unverified opinion. Treat it as optional review after deterministic checks.

**Don't copy shell execution shortcuts.** Some validation paths use `shell=True`. GearTrain should keep structured command arguments, explicit working directories, timeouts, and captured outputs.

## Recommended Order

1. Add the execution contract and evidence envelope to the first milestone's file-backed run state.
2. Add deterministic post-Codex verification to `geartrain-dev`.
3. Add one bounded repair attempt with compact failure context.
4. Add timeout, file-count, path-scope, and no-progress policies.
5. Add the fixture-based same-model eval harness.
6. Add repository indexing and retrieval after the executable loop works.
7. Add deeper context governance and dynamic tools when GearTrain runs native agent loops.

The first three steps provide most of Villani's useful discipline without changing GearTrain's current Codex-first milestone or requiring GearTrain to own the model's internal tool loop.
