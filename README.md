<div align="center">

<img src="docs/images/brand/hero.svg" alt="terra-ai: Terraform Module Engineering Platform" width="100%">

<br>

![Terraform](https://img.shields.io/badge/terraform-%E2%89%A5_1.11-0B0F14?logo=terraform&logoColor=22D3EE&labelColor=0B0F14)
![CI](https://img.shields.io/badge/ci-GitHub_Actions-0B0F14?logo=githubactions&logoColor=22D3EE&labelColor=0B0F14)
![Modules](https://img.shields.io/badge/modules-reusable_AWS-0B0F14?logo=terraform&logoColor=22D3EE&labelColor=0B0F14)
![Review](https://img.shields.io/badge/review-deterministic-0B0F14?logo=python&logoColor=22D3EE&labelColor=0B0F14)
![AI](https://img.shields.io/badge/AI_summary-optional-0B0F14?logo=googlegemini&logoColor=22D3EE&labelColor=0B0F14)

**[Setup](docs/install.md)** · **[How it works](docs/architecture.md)** · **[What each file is](docs/files.md)** · **[The checks](docs/checks.md)** · **[Module standard](docs/module-standard.md)**

</div>

## What it is

A Terraform platform: a library of reusable AWS modules, the root configurations built from them, and a pull-request pipeline that

- finds **which root configurations a change affects** (including the ones that only use a changed shared module) and runs Terraform only for those,
- plans, estimates cost and checks the change against the repository's own contract,
- **decides pass or fail with code**, and optionally has an AI write a plain-language summary of the evidence,
- applies on merge, with **`develop` and `main` mapped to separate AWS accounts**.

No folder names are assumed: it works the same for `infra/web`, `terraform/networking` or `environments/dev`.

![Architecture: branches, pull-request.yml, terraform.yml, the reviewer, the PR comment and the two AWS accounts](docs/images/architecture.svg)

## Highlights

| | |
| --- | --- |
| **Affected-root discovery** | A module-call graph built from local `source` paths. Edited roots, edited modules (transitively) and edited shared files are mapped to roots. Docs trigger nothing. |
| **Branch → account** | `develop` and `main` use different AWS keys. Before `init`, the pipeline compares the keys' account with `terraform.accounts` and stops on a mismatch. |
| **Deterministic verdict** | `REQUEST_CHANGES` on any HIGH or CRITICAL finding or failed check; otherwise `PASS`. The AI never takes part. |
| **Reviewer** | Rules (module boundaries, mandatory tags, plan and cost against the standards) on top of `terraform`, TFLint, Checkov and Infracost. |
| **AI summary** | One text, schema-validated and grounded: every resource, file and price it mentions is checked against the evidence. Off by default; a failing model never changes the result. |
| **Modules** | Reusable AWS modules, each with a README and typed, validated inputs. |

## Stack

<img alt="Terraform" src="https://img.shields.io/badge/Terraform-844FBA?style=for-the-badge&logo=terraform&logoColor=white">&nbsp;<img alt="AWS" src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonwebservices&logoColor=white">&nbsp;<img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white">&nbsp;<img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">&nbsp;<img alt="TFLint" src="https://img.shields.io/badge/TFLint-5C4EE5?style=for-the-badge&logo=terraform&logoColor=white">&nbsp;<img alt="Checkov" src="https://img.shields.io/badge/Checkov-1F2A37?style=for-the-badge">&nbsp;<img alt="Infracost" src="https://img.shields.io/badge/Infracost-FF6B35?style=for-the-badge">&nbsp;<img alt="Gemini" src="https://img.shields.io/badge/Gemini_(optional)-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white">

To run the pipeline on your own repository: [Setup](docs/install.md).

> [!NOTE]
> Plans, checks and the PR comment have run on GitHub. `terraform apply` on merge and the AI summary have not been validated end to end yet.

<details>
<summary><b>Repository layout</b></summary>

```text
modules/              Reusable AWS modules (README each)
infra-example/        Example roots: dev/web-demo and prod/web-demo
tools/reviewer/       The reviewer: ci/ (one file per workflow step) · lib/ · terraform/ · rules/ · review/ · infracost/ · aws/ · ai/
.github/workflows/    pull-request.yml (checks, plans, comment) · terraform.yml (plan / apply)
common.yaml           project, state settings, AI switch, AWS account and deployable roots per branch
docs/                 Setup, architecture, file map, the checks, module standard
.claude/agents/       terra-ai-engineer: assistant that knows how this repository is built (proposes, never runs commands)
```

</details>
