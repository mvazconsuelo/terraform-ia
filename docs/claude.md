# Working with Claude Code

English · [Español](es/claude.md)

The repository is ready for [Claude Code](https://code.claude.com/docs): it knows the conventions, has an engineer agent, three skills and two safety nets.
You do not need it to use the project; it is for whoever maintains it.

## What is in the repository

| File | What it does |
| --- | --- |
| [`CLAUDE.md`](../CLAUDE.md) | Claude reads it in every session: how the repository works and every convention. |
| `.claude/agents/terraform-ia-engineer.md` | The engineer: proposes first, edits only after you approve, never runs commands. |
| `.claude/skills/new-module`, `new-rule`, `new-root` | The step-by-step lists Claude follows when you ask for a module, a rule or an environment. |
| `.claude/settings.json`, `.claude/hooks/after_edit.py` | After every edit: `ruff` and `mypy` on Python, `terraform fmt` on `.tf`. Blocks the commands that are yours: git writes, `gh` commands that publish, `terraform apply`. |

## Install

1. Install Claude Code: [documentation](https://code.claude.com/docs).
2. Open a terminal in the root of the repository and run `claude`. The first time it asks to trust the project's hook and settings: accept.

## Use it

**A normal session**: run `claude` and ask. The skills start by themselves when the request matches (*"create a module for SQS"*, *"add a rule that..."*, *"add a staging environment"*).

**The engineer agent**: for a change with several parts, where you want a proposal before anything is edited.

```bash
claude --agent terraform-ia-engineer
```

Or, inside a session, `@agent-terraform-ia-engineer ...`, or *"use the terraform-ia-engineer agent to ..."*. An alias saves typing: `alias tia='claude --agent terraform-ia-engineer'`.

| You want | Use |
| --- | --- |
| A module, a rule or an environment, with a proposal first | The agent |
| A small change, to run the checks, to review a pull request | A normal session |

## The flow with the agent

1. You ask. For example: *"I want an `sqs` module with a dead-letter queue. Propose first."*
2. It answers with what it understood, what it still needs to know and a proposal (files and docs). **It changes nothing yet.**
3. You approve in your next message (*"approved, go ahead"*).
4. It edits. The hook formats and checks each file.
5. It gives you the commands to run: the verification and the git commands. It has no terminal.

Every module or rule it creates comes with its test, and the documentation in English and Spanish. The pipeline runs the tests.

## What Claude never does

It does not commit, push, merge or open pull requests; it does not deploy or touch AWS; it does not write keys or account ids. Those commands are blocked in `.claude/settings.json`.
Git and every deployment are yours: [How it works](architecture.md).

---

[← Previous: The checks](checks.md) · [README](../README.md)
