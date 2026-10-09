# Contributing

English · [Español](docs/es/contributing.md)

This is a personal project. **Anyone can open an issue; pull requests are opened and merged by the maintainer.** The repository does not accept pull requests from others.

## Ideas and bugs: open an issue

Use the form that fits: **Bug** (something does not work as the documentation says) or **Improvement** (a module, a rule or a change you would like).
For a security problem, do not open an issue: see [`SECURITY.md`](SECURITY.md).

## How a change travels (the maintainer)

1. Branch from `develop` (non-production). `main` is production.
2. Open a pull request into `develop`. The pipeline runs `terraform fmt`, `validate`, TFLint, Checkov, `ruff`, `mypy`, the **tests**, the repository contract, a read-only plan of the roots the change affects, and comments the result.
3. A confirmed High or Critical finding, or any failed check, makes the verdict `REQUEST_CHANGES`.
4. Merging deploys nothing: only the maintainer deploys, by hand. Production reaches `main` by a pull request from `develop`.

## What every change brings

| You change | It must also have |
| --- | --- |
| A module (`modules/`) | Its README in the standard format, its test in `tests/terraform/` (one file per module), and the entry in the module tables of the READMEs and `docs/files.md` |
| A reviewer rule (`tools/rules/`) | The entry in `rules.yaml`, the function, a test in `tests/reviewer/` that breaks it on purpose, and its row in `docs/checks.md` |
| Infrastructure values (`inputs.yaml`) | Nothing hard-coded in the `.tf`: the `.tf` files are the same in every environment |
| Any documentation | The English file and its Spanish copy (`docs/es/`, `README.es.md`) |

- A module call in a root passes values as they are: no `for`, `try`, `merge` or conditions. If you need logic, it goes in the module (rule `ROOT-005`).
- The tests are run by the pipeline, not by hand. They live only in `tests/`.
- Never commit a key, a token, an account id or a state file.

## Where to start

The conventions are in [`CLAUDE.md`](CLAUDE.md). [`docs/module-standard.md`](docs/module-standard.md) is the contract of a module, [`docs/checks.md`](docs/checks.md) lists every rule and
[`docs/files.md`](docs/files.md) says what each file is. The repository has an agent and the skills `new-module`, `new-rule` and `new-root` for Claude Code that follow all of this.
