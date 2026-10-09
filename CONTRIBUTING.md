# Contributing

English · [Español](docs/es/contributing.md)

Thanks for helping. A change is welcome when it follows the conventions of the project, which are short and written down in [`CLAUDE.md`](CLAUDE.md).

## How a change travels

1. Fork the repository and branch from `develop` (non-production). `main` is production.
2. Open a pull request into `develop`. The pipeline runs `terraform fmt`, `validate`, TFLint, Checkov, `ruff`, `mypy`, the **tests**, the repository contract, a read-only plan of the roots your change affects, and comments the result.
3. A confirmed High or Critical finding, or any failed check, makes the verdict `REQUEST_CHANGES`.
4. Merging deploys nothing: only the owner deploys, by hand. Pull requests from forks get no AWS keys, so they have no plan.

## What every change brings

| You change | It must also have |
| --- | --- |
| A module (`modules/`) | Its README in the standard format, its test in `tests/terraform/` (one file per module), and the entry in the module tables of the READMEs and `docs/files.md` |
| A reviewer rule (`tools/rules/`) | The entry in `rules.yaml`, the function, a test in `tests/reviewer/` that breaks it on purpose, and its row in `docs/checks.md` |
| Infrastructure values (`inputs.yaml`) | Nothing hard-coded in the `.tf`: the `.tf` files are the same in every environment |
| Any documentation | The English file and its Spanish copy (`docs/es/`, `README.es.md`) |

- A module call in a root passes values as they are: no `for`, `try`, `merge` or conditions. If you need logic, it goes in the module (rule `ROOT-005`).
- The tests are run by the pipeline, not by hand. They live only in `tests/`.
- Never commit a key, a token or a state file.

## Where to start

[`docs/module-standard.md`](docs/module-standard.md) is the contract of a module, [`docs/checks.md`](docs/checks.md) lists every rule and [`docs/files.md`](docs/files.md)
says what each file is. If you use Claude Code, the repository already has the agent and the skills `new-module`, `new-rule` and `new-root` that follow all of this.
