# GearTrain — Example: Software Development Workflow

This document describes a complete software development workflow as implemented in GearTrain. It serves as both a reference example and the target workflow for GearTrain's own development (dogfooding).

---

## Team Setup

```yaml
team: geartrain-core
integrations: [github, slack (deferred)]
engine: local (developer workstation)
memory: project-scoped, markdown-backed (MVP)
```

---

## Sub-Workflows

The software development workflow is not a single pipeline but a family of interconnected sub-workflows, each handling a distinct phase of development.

### 1. Feature Development Workflow

**Trigger:** Manual (developer starts it) or event (issue assigned in tracker)
**Engine:** Developer's local workstation
**Channels:** Web UI (MVP), Slack (deferred)

```
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────┐
│  Intake  │────▶│ Human Review │────▶│ Implement │────▶│   Test   │
│(TeamLead)│     │ (Checkpoint) │     │  (Coder)  │     │   (QA)   │
└──────────┘     └──────────────┘     └───────────┘     └──────────┘
                        │ rejected           │ blocked       │ fail
                        ▼                    ▼               ▼
                   ┌──────────┐        ┌──────────────┐  (back to
                   │  Intake  │        │ Human Review │   Implement)
                   │  (redo)  │        │  (clarify)   │
                   └──────────┘        └──────────────┘
                                                          │ pass
                                                          ▼
                                           ┌──────────────────────┐
                                           │   Code Review        │
                                           │   (Reviewer Agent)   │
                                           └──────────────────────┘
                                              │ approved    │ changes
                                              ▼             │ requested
                                           ┌────────────┐   ▼
                                           │ Create PR  │  (back to
                                           │(TeamLead)  │  Implement)
                                           └────────────┘
                                              │
                                              ▼
                                           ┌────────────────────┐
                                           │ Update Tracker &   │
                                           │ Knowledge Base     │
                                           └────────────────────┘
```

#### Agents Involved

**Team Lead Agent**
- Role: Task decomposition, planning, coordination, communication
- Tools: Issue tracker read/write, project memory read/write, GitHub PR creation
- Key behaviors:
  - Reads task from issue tracker, gathers context from project memory
  - Produces an implementation plan with acceptance criteria
  - Communicates with human for clarification or approval
  - Creates PR with description linking back to the task
  - Updates issue tracker status at each phase transition

**Coder Agent**
- Role: Code implementation following the plan
- Tools: File read/write, shell execution, git operations, project search, test runner
- Key behaviors:
  - Receives plan from team lead, reads relevant codebase context
  - Implements changes following project conventions (from project memory)
  - Writes tests alongside implementation
  - Can request clarification from team lead or human
  - Reports completion with a summary of changes

**QA Agent**
- Role: Verification that the implementation meets requirements
- Tools: Test runner, file read, shell execution, browser automation [deferred]
- Key behaviors:
  - Runs existing test suite to check for regressions
  - Runs new tests written by coder
  - Verifies the implementation matches the acceptance criteria
  - Produces a test report with pass/fail/coverage

**Reviewer Agent**
- Role: Code quality, standards compliance, architectural consistency
- Tools: File read, git diff, linter, project memory (coding standards)
- Key behaviors:
  - Reviews diff against project coding standards
  - Runs deterministic tools (linter, type checker, formatter)
  - Checks for security issues, performance concerns, maintainability
  - Produces review comments (approve, request changes, or comment)

#### Human Interaction Points

| Point | Type | When | Channel |
|-------|------|------|---------|
| Plan review | Approval + Input | After team lead produces plan | Web UI |
| Clarification | Input | When coder or team lead needs context | Web UI |
| PR review | Review | After automated review, before merge | GitHub + Web UI |
| Conflict resolution | Choice | When agents disagree or are stuck | Web UI |

---

### 2. CI/CD Review Workflow

**Trigger:** Event (new PR created on GitHub)
**Engine:** Cloud server [deferred; MVP: manual trigger on local]
**Channels:** GitHub PR comments, Slack [deferred]

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Review PR    │────▶│ Leave        │────▶│ Merge        │
│ (Reviewer)   │     │ Comments     │     │ Decision     │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    ▼                       ▼
                              ┌──────────┐          ┌──────────────┐
                              │  Merge   │          │ Request      │
                              │  PR      │          │ Changes      │
                              └──────────┘          └──────────────┘
                                    │
                                    ▼
                              ┌──────────────┐     ┌──────────────┐
                              │ Deploy to    │────▶│ Smoke Test   │
                              │ Staging      │     │ (QA Agent)   │
                              └──────────────┘     └──────────────┘
                                                         │
                                                         ▼
                                                   ┌──────────────┐
                                                   │ Update       │
                                                   │ Tracker      │
                                                   └──────────────┘
```

#### MVP Scope
For MVP, this workflow is simplified to: manual trigger → reviewer agent reads diff → produces review comments → human decides merge. Deployment and smoke testing are deferred.

---

### 3. Product Planning Workflow

**Trigger:** Schedule (daily/weekly) or manual
**Engine:** Developer workstation or dedicated server
**Channels:** Web UI, Slack [deferred]

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Analyze      │────▶│ Generate     │────▶│ Present to   │
│ Project      │     │ Report       │     │ Human        │
│ State        │     │              │     │ (Checkpoint) │
└──────────────┘     └──────────────┘     └──────────────┘
```

#### What the Planning Agent Does
- Reads project memory: current sprint goals, timeline, scope
- Reads issue tracker: open tasks, velocity, blockers, bug count
- Reads workflow history: recent completions, failure patterns
- Generates a structured report: progress, risks, recommendations
- Presents to human for review and action

#### MVP Scope
Deferred entirely. For the first two weeks, project planning is manual.

---

### 4. User Support Workflow

**Trigger:** Event (user feedback received via channel)
**Engine:** Cloud server [deferred]
**Channels:** Support chat, email, feedback forms

Deferred entirely for MVP. Documented here for architectural completeness.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Receive      │────▶│ Search       │────▶│ Draft        │
│ Feedback     │     │ Knowledge    │     │ Response     │
│              │     │ Base         │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    ▼                       ▼
                              ┌──────────┐          ┌──────────────┐
                              │ Auto-    │          │ Escalate to  │
                              │ Respond  │          │ Human        │
                              └──────────┘          └──────────────┘
                                    │                      │
                                    ▼                      ▼
                              ┌──────────────┐     ┌──────────────┐
                              │ Log &        │     │ Create       │
                              │ Categorize   │     │ Issue        │
                              └──────────────┘     └──────────────┘
```

---

## Dogfooding: GearTrain Develops GearTrain

The first concrete workflow instance is GearTrain developing itself. This creates a virtuous cycle: improving GearTrain improves the tool that develops GearTrain.

### Initial Setup
- **Team:** `geartrain-core`
- **Repo:** `github.com/[org]/geartrain`
- **Engine:** Local (each developer's workstation)
- **Workflow:** Feature development (simplified for MVP)

### MVP Feature Development Flow
1. Developer selects a task (from docs or issue tracker)
2. Starts the workflow: `geartrain run feature-development --task "implement memory store"`
3. Team lead agent reads the task, reads project memory, produces a plan
4. Developer reviews and approves plan (web UI)
5. Coder agent implements the feature
6. QA agent runs tests
7. Reviewer agent reviews the diff
8. On approval, team lead agent creates a PR
9. Developer reviews PR on GitHub, merges
10. Project memory is updated with what was learned

### What We Learn by Dogfooding
- Is the workflow definition format expressive enough?
- Are human checkpoints at the right granularity?
- Does project memory actually help agents make better decisions?
- Where do agents get stuck and need better tools?
- What's the overhead of the framework vs. just using Claude Code directly?
