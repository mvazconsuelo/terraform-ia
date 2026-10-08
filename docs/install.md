# Setup

[← README](../README.md) · English · [Español](es/install.md)

## Requirements

A GitHub repository, one or two AWS accounts, Terraform ≥ 1.11 (S3 native state lock, no DynamoDB; the repo is developed on 1.16), the AWS CLI, `gh`, and Python 3.12 with PyYAML.

## 1. Branches

`main` is production (keep it as the default branch), `develop` is non-production.

```bash
git switch -c develop && git push -u origin develop
```

Protect `main` (pull request required, status checks required): production applies run on the merge, so that protection is the gate.

## 2. `common.yaml`

```yaml
project: shop
backend:
  encrypt: true
  use_lockfile: true
ai:
  enabled: false                # true once GEMINI_API_KEY exists
terraform:
  accounts:                     # AWS account id of each branch's keys; the pipeline stops on a mismatch
    develop: "111111111111"
    main: "222222222222"
  deploy:                       # roots each branch may apply on push (globs)
    develop:
      - infra-example/dev/*
    main:
      - infra-example/prod/*
```

Everything under `terraform:` except `accounts` is optional. See [architecture](architecture.md#configuration).

## 3. State bucket (once per account and region)

```bash
B=shop-tfstate-<account id>-<region>
aws s3api create-bucket --bucket $B --region <region>      # outside us-east-1 add: --create-bucket-configuration LocationConstraint=<region>
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 4. Secrets (repository level)

| Secret | Required | Use |
| --- | --- | --- |
| `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | yes | `develop` and every other branch |
| `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | yes | `main` (production) |
| `AWS_REGION` | yes | Provider region and state bucket |
| `INFRACOST_API_KEY` | no | Cost section (`infracost auth login` for a free key) |
| `GEMINI_API_KEY` | no | AI summary (Google AI Studio) |
| `GEMINI_MODEL` | no | Overrides the default model; leave unset otherwise |
| `GEMINI_FALLBACK_MODEL` | no | A second model, used only when the main one is overloaded (503) or out of quota (429); quotas are per model |

```bash
gh secret set AWS_ACCESS_KEY_ID_DEVELOP
```

Never commit keys; rotate any that were exposed.

## 5. Open a PR

Branch from `develop`, change something small and open a PR into `develop`. You get one check per concern, a read-only `plan` for each affected root, and a comment with the verdict, the plan, the cost and the environment it lands on. Merging into `develop` applies the roots that merge affected and that `terraform.deploy.develop` allows; the first apply creates billable resources (Aurora, load balancer).

Manual runs:

```bash
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=plan
```

If no check appears on a PR, a workflow file is invalid: run `actionlint .github/workflows/*.yml`.
