# modules/iam

IAM role with trust policy, managed/inline policies and an optional instance profile.
**Non-goals:** users, groups, OIDC/IRSA roles, policy authoring (build documents with `aws_iam_policy_document` in the caller).

## Usage

```hcl
module "lambda_role" {
  source = "../../modules/iam"

  name                 = "payments-dev-worker"
  assume_role_services = ["lambda.amazonaws.com"]
  managed_policy_arns  = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }
}
```

## Resources and tags

`aws_iam_role` and `aws_iam_instance_profile` (taggable, tagged); policy attachments and inline policies are not taggable. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `assume_role_services`, `assume_role_principal_arns` (at least one trust principal), `managed_policy_arns`, `inline_policies` (JSON), `create_instance_profile`, `permissions_boundary_arn`, `path`, `max_session_duration`. See `variables.tf` for types, defaults and validations.

## Outputs

`role_arn`, `role_name`, `instance_profile_name`, `instance_profile_arn`.

## Lifecycle

Renaming the role replaces it (and breaks anything referencing the old ARN). Changing the trust policy is in-place.

## Cost

Free.

## Testing

`terraform init -backend=false && terraform test` (uses `mock_provider`; no credentials).
