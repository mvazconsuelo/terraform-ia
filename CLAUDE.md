# Terraform-ia

A Terraform module engineering platform: reusable AWS modules (`modules/`), example roots (`infra-example/`) and a deterministic
pull-request reviewer (`tools/`). The reviewer's AI summary (Gemini) is optional and only explains the evidence.

This file is the single place for the project's conventions. The agent `terraform-ia-engineer` and the skills `new-module`,
`new-rule` and `new-root` read it; change a convention here, not there.

## How to work in this repository

- **The owner writes in Spanish.** Answer in Spanish. Code, comments, docs and commit messages are in English.
- **Git is the owner's.** Never commit, push, merge, branch or open a PR. After a change, give the commands: `git status`,
  `git add <files>`, `git commit -m "<message>"`, `git push`, and the branch the PR targets. The commit message ends with
  `Co-Authored-By: Claude <noreply@anthropic.com>`; a PR body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- **A code change is not a deployment.** Changing files (modules, roots, reviewer, docs) ends in a pull request that the owner opens and merges;
  merging never touches AWS. A deployment is a different act, and only the owner does it: a manual run of `terraform.yml`
  (`gh workflow run`, first `plan`, then `apply`), the state bucket, the secrets and the AWS keys. Claude never runs `terraform apply`, `destroy`,
  `import` or `state`, never runs `gh workflow run`, and never touches AWS. When a change needs a deployment, say so and give the commands.
  These commands are also blocked in `.claude/settings.json`, so do not look for a way around the block.
- **Kinds of change, and what each one needs.** Say which kind a change is, propose the branch name from it, and say what happens after the merge:

  | Kind | Branch name | PR into | After the merge |
  | --- | --- | --- | --- |
  | Tooling, rules, docs, skills, agent (`tools/`, `.claude/`, `docs/`, `.github/`) | `chore/<what>`, `docs/<what>`, `feat/<what>` | `develop` | Nothing to deploy |
  | A module (`modules/`) | `feat/<module>-module`, `fix/<module>-<what>` | `develop` | Nothing deploys until a root uses it; the plan in the PR shows the roots it affects |
  | Infrastructure values or a root (`inputs.yaml`, a new environment or stack) | `infra/<environment>-<what>` | `develop` for non-production, `main` for production | The owner runs `plan`, then `apply`, by hand |

  A branch name never says "deploy": merging deploys nothing. Production reaches `main` by a PR from `develop`, after it was applied in `dev`.
- **Nothing secret in files or in the chat.** Never write or repeat a key or a token, and and never write an AWS account id in a file (it is the repository variable `AWS_ACCOUNT_ID_DEVELOP` or `AWS_ACCOUNT_ID_MAIN`). If the owner pastes a key, say it must be rotated.
- **Docs are English with a Spanish copy** (`README.es.md`, `docs/es/*.md`, `infra-example/README.es.md`). Change both, always. File
  names, rule IDs and code stay untranslated. Docs are short and describe what exists; no "run it locally" sections, everything runs from a PR.
- **Ask before outward or hard-to-reverse actions** (workflow or secret settings, deleting files). Read a file before you say what it holds.
- A hook (`.claude/hooks/after_edit.py`) runs `ruff` and `mypy` after a change in `tools/` or `tests/` and `terraform fmt` after a change in a `.tf` file, and
  hands the failures back to you. Run `ruff check tools tests` and `mypy tools tests` from the repository root (`.venv/bin/...`) to check the whole of it.
  After changing `.tf`: `terraform fmt -recursive`, then `terraform validate` in the folder (`init -backend=false` first).

## How the repository works

- **Branches:** `develop` is non-production, `main` is production, each with its own AWS account. A PR into `develop` runs fmt, validate,
  tflint, Checkov, the repository contract, a plan and a cost estimate, and comments the result. A PR into `main` runs the plan, the cost and the review.
- **Merging never touches AWS.** Deploying is a manual run of `terraform.yml` (`gh workflow run ... -f mode=plan|apply`) with that branch's keys.
- **Workflows have no logic.** `.github/workflows/*.yml` only wire steps. The logic is Python in `tools/ci/`, one file per step, named
  like the step (`terraform_validate.py`, `terraform_plan.py`...).
- **The verdict is deterministic code:** `REQUEST_CHANGES` when a confirmed finding is HIGH or CRITICAL or an external check failed. The AI never
  decides and never receives file contents.
- **`common.yaml` holds facts about the infrastructure:** `project`, `backend`, `ai`, and `terraform.environments` (each environment with its
  `branch` and its `roots`; the AWS account of each branch is a repository variable, not a file). Rules are not defined there: they live in `tools/rules/rules.yaml`, grouped by theme (MODULE, TAGS, ROOT, POLICY, PLAN).
- **Terraform `>= 1.11`.**

## Where things live

| Folder | What is in it |
| --- | --- |
| `modules/<capability>` or `modules/<domain>/<component>` | The reusable modules. |
| `infra-example/{dev,prod}/web-demo` | Example roots that consume the modules. |
| `tests/` | All the tests, in one place: `tests/reviewer` (pytest, the reviewer) and `tests/terraform` (`terraform test`, the modules). |
| `tools/ci/` | One entry point per workflow step. |
| `tools/lib/` | Shared helpers: `git_diff`, `github_actions`, `redact_secrets`, `workflow_jobs`. |
| `tools/terraform/` | Reading the Terraform code (`terraform_map.Repo`, `read_tf_files`, `affected_roots`) and the plan (`read_plan_json`). |
| `tools/rules/` | `rules.yaml` (the catalog, single source of truth), `registry.py`, `code_rules.py` (reads `.tf`), `inputs_rules.py` (reads a root's `inputs.yaml`), `plan_rules.py` (plan and cost). |
| `tools/review/` | `run_review.py` (checks, verdict, AI), `render_pr_comment.py` (the comment), `finding.py`. |
| `tools/ai/` | The optional AI summary: `summary.py`, `client.py`, `grounding.py`, `prompt.md`, `schema.json`. |
| `tools/{aws,infracost,versions}/` | The account guard, the Infracost reader, the newer-releases lookup (information only). |
| `.github/` | Workflows, `CODEOWNERS`, `dependabot.yml`. |
| `docs/` | `files.md` (every file), `checks.md` (every rule), `module-standard.md`, `architecture.md`, `install.md`. |

Read `docs/module-standard.md`, `docs/files.md` and `tools/rules/rules.yaml` before you change modules, files or rules.

## Conventions

### Modules

- **A module is the source of truth of how it is called.** Its `variables.tf` and README are its contract. Never edit a module, its README
  or the standard to suit one project's `inputs.yaml`.
- **A module has no `inputs.yaml`.** That file belongs to the project that builds infrastructure, next to the `.tf` that call the modules.
- **A module call holds no logic.** It passes `local.inputs.*` values as they are: no `for`, `try`, `if` or conditions that reshape them.
  Resolving and defaulting is the module's job (the security-group module resolves `port`, `cidr_ipv4: vpc` and `source_sg`; the ALB
  module picks its subnets from `internal`). Use `nullable = false` when `null` must mean "the default".
  `ROOT-005` flags a call that uses `for`, `try`, `merge`, a conditional and the like. **If you find yourself writing logic in a call, the logic goes in the module.**
- **A value that comes from another module's output** is passed as a map: the receiving module takes `source_security_groups = { alb = module.alb_sg.security_group_id }`
  or `certificates = { web = module.certificate.certificate_arn }`, and `inputs.yaml` names the key (`source_sg: alb`, `certificate: web`). Never build it with `for` or `merge` in the root.

### Roots (`infra-example/<env>/<stack>`)

- **No literal values.** Names, CIDRs, ports, sizes and rules come from `inputs.yaml`. Every block carries its own port as a number; there is no shared `ports` block.
- **The `.tf` files are identical in every environment;** only `inputs.yaml` differs.
- **`main.tf` reads the YAML and nothing else:** `inputs.yaml` into `local.inputs`, and `common.yaml` for `project` and `environment`
  (the environment whose `roots` has this root's path). It joins them in `local.tags`.
- **Tags:** `owner` and `cost_center` live in the root's `inputs.yaml` (every project sets its own); `project` and `environment` come from
  `common.yaml`. Every call passes `tags = local.tags`.
- **Names:** the full physical name is a `name` in `inputs.yaml` with `"${project}-${environment}-<component>"` placeholders, completed in the
  call by `templatestring(local.inputs.<x>.name, local.tags)`. Never build a name in the `.tf`.
- **Every `data` block goes in `data.tf`,** never in the files that create resources.
- **`inputs.yaml` is block-style YAML** (no braces, no inline lists) with a comment divider `# ---- name ----` before each top-level block.
  Never use `---` between blocks: `yamldecode` and `safe_load` read one document only.
- **Policy is data, not code.** A root has no validation block: modules validate their own inputs and the reviewer checks the project's
  policy (`ROOT-003`, `ROOT-004`, `POLICY-*`; the requirements live in `rules.yaml`). Never hard-code `dev`, `staging` or `prod` in a rule or a root.

### Tests

- **All tests live in `tests/` and only the pipeline runs them.** The job `tests` runs `tools/ci/run_tests.py`; a failed test makes the verdict
  `REQUEST_CHANGES`. No doc, skill or answer asks the owner to run tests locally. Run them yourself once, to check what you wrote.
- **`tests/reviewer`** (pytest) tests the code that decides: one file per theme, in the order of `rules.yaml` (`test_rules_module.py`, `test_rules_root.py`...),
  plus `test_verdict.py`, `test_select_roots.py`, `test_affected_roots.py` and `test_redact_secrets.py`.
  **`tests/terraform`** (`terraform test`, AWS mocked) tests what a module does: **every module has one** `.tftest.hcl`, named after its path with `/` and `-` as `_` (`modules/elb/alb` is `elb_alb.tftest.hcl`, `modules/security-group` is `security_group.tftest.hcl`).
- **Readable.** One test per case. The name is a sentence: `test_<rule id>_flags_<what>` for a rule that fires (`test_root_003_flags_a_root_outside_every_environment`),
  `a_manual_run_from_a_branch_no_environment_names_reaches_nothing` for a behaviour. Three comment lines in every test: `given` (what is set up or broken),
  `when` (what runs), `then` (what must come out). `conftest.py` has the `sandbox` (a copy of the repository to break) and `findings_of`.
- **Every rule has a test that flags it, and every module has a `.tftest.hcl`.** `test_every_rule_has_tests.py` fails when a rule has none, and
  `test_every_rule_passes_on_the_repository` fails when the repository breaks its own rules. `test_every_module_has_a_terraform_test.py` fails when a module has
  none, except the ones listed in its `PENDING` (empty today: every module has its test; a new module brings its test in the same change). A rule, a module or a behaviour is not done without its test.
- **What a module test holds, at least:** a plan that works with the minimum inputs, and one input that the module must reject. A module that resolves, defaults
  or picks something also tests that, one case for each.

### Python (`tools`)

- Put code where its function says: a workflow step in `ci/`, a shared helper in `lib/`, a Terraform reader in `terraform/`, a rule in `rules/`.
  Names say what the thing does (`resource_missing_mandatory_tags`, not `check3`).
- In `run_review.py` keep one import per line for `code_rules`, `inputs_rules` and `plan_rules`, each with `# noqa: F401`: a linter may drop
  them as unused and silently turn rules off.
