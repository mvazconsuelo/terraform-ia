---
name: new-rule
description: Add or change a rule of the PR reviewer (tools/rules). Use when the user wants the reviewer to check something new, or to change a severity, a requirement or a rule's text.
---

First decide what kind of rule it is, and say so:

- **A value in a root's `inputs.yaml`** that must meet a condition: add a requirement to the existing policy rule in `tools/rules/rules.yaml`
  (`POLICY-001` today: `path` plus one test `equals`, `any_equals`, `at_least` or `count_at_least`, and a `why`). No Python.
- **Something in the `.tf` code, or the plan or the cost:** a new rule, which has three parts that change together:
  1. its entry in `rules.yaml`: `id` (`FAMILY-NNN` with the family of its theme: MODULE, TAGS, ROOT, POLICY or PLAN, in that section), `reads` (`code`, `inputs` or `plan`), `category`, `severity`, `check` (the function name), `title`,
     `explanation`, `recommendation`, and its parameters;
  2. the function with that name in `code_rules.py` (reads `.tf`), `inputs_rules.py` (reads a root's `inputs.yaml`) or `plan_rules.py`, registered
     with `@check` or `@plan_check`, and built with `make_finding`;
  3. its row in `docs/checks.md` and `docs/es/checks.md`, and in `docs/module-standard.md` if it enforces the module standard.

Before writing, check that an external tool does not already cover it (terraform fmt/validate, tflint, Checkov, Infracost). The catalog holds
only what they cannot know. A rule naming a function that does not exist makes the review fail on purpose.

**The test is part of the rule.** Add to `tests/reviewer/test_rules_<theme>.py` (the theme of the rule) a test named `test_<rule id>_flags_<what>` that breaks a copy of the
repository on purpose with the `sandbox` and checks the finding with `findings_of`; follow the given / when / then comments of the other tests (see `CLAUDE.md`, Tests). That the real
repository passes is already tested for every rule. `test_every_rule_has_tests.py` fails if a rule has no flagging test. Only the pipeline runs the tests: run them once yourself to check them.

Verify with both faces of the rule:
1. From the repository root: `.venv/bin/ruff check tools tests` and `.venv/bin/mypy tools tests`.
2. The real repository gives no finding of the new rule, and a broken copy of the repository gives exactly one. Report what you saw.

End with the git commands (see `CLAUDE.md`).
