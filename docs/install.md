# Setup

English · [Español](es/install.md)

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
project: terraform-ia
backend:
  encrypt: true
  use_lockfile: true
ai:
  enabled: false                # true once GEMINI_API_KEY exists
terraform:
  environments:                 # each environment, defined once: the branch that deploys it, its AWS account and its roots
    dev:
      branch: develop
      account: "111111111111"   # the pipeline stops if the keys of that branch belong to another account
      roots:
        - infra-example/dev/web-demo
    prod:
      branch: main
      account: "222222222222"
      roots:
        - infra-example/prod/web-demo
```

In `terraform:`, `environments` is required (each one needs its `branch`, `account` and `roots`); the rest is optional. See [architecture](architecture.md#configuration).

## 3. State bucket (once per account and region)

```bash
B=terraform-ia-tfstate-<account id>-<region>
aws s3api create-bucket --bucket $B --region <region>      # outside us-east-1 add: --create-bucket-configuration LocationConstraint=<region>
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 4. Secrets (repository level)

| Secret | Required | Use | Where to get it |
| --- | --- | --- | --- |
| `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | yes | `develop` and every other branch | [AWS IAM console](https://console.aws.amazon.com/iam/home#/users) → the user → *Security credentials* → *Create access key*, in the **dev** account · [guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-key-self-managed.html) |
| `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | yes | `main` (production) | The same console, in the **production** account |
| `AWS_REGION` | yes | Provider region and state bucket | Your choice, for example `us-east-1` |
| `INFRACOST_API_KEY` | no | Cost section | [Infracost dashboard](https://dashboard.infracost.io) (free) · [docs](https://www.infracost.io/docs/) |
| `GEMINI_API_KEY` | no | AI summary | [Google AI Studio → API keys](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | no | Overrides the default model; leave unset otherwise | [Gemini models](https://ai.google.dev/gemini-api/docs/models) · [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) |
| `GEMINI_FALLBACK_MODEL` | no | A second model, used only when the main one is overloaded (503) or out of quota (429); quotas are per model | Same lists as above |

Where to store them: `https://github.com/<owner>/<repo>/settings/secrets/actions` (replace `<owner>/<repo>`) · [GitHub docs on secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) · [`gh secret set`](https://cli.github.com/manual/gh_secret_set).

```bash
gh secret set AWS_ACCESS_KEY_ID_DEVELOP
```

`gh secret set` stores one secret per command and asks for its value, so it never lands in your shell history. Never commit keys; rotate any that were exposed.


## 5. Open a PR

Branch from `develop`, change something small and open a PR into `develop`. You get one check per concern, a read-only `plan` for each affected root, and a comment with the verdict, the plan, the cost and the environment it lands on. **Merging never touches AWS.** To deploy, run `terraform.yml` by hand (below); the first apply creates billable resources (Aurora, load balancer).

Manual runs (the only way to deploy). `--ref` picks the branch, so the AWS account; the root must belong to an environment of that branch:

```bash
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=plan
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=apply
```

If no check appears on a PR, a workflow file is invalid: run `actionlint .github/workflows/*.yml`.

---

[README](../README.md) · [Next: How it works →](architecture.md)
