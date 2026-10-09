# modules/iam

IAM role with trust policy, managed/inline policies and an optional instance profile.
**Non-goals:** users, groups, OIDC/IRSA roles, policy authoring (build documents with `aws_iam_policy_document` in the caller).

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
lambda_role:
  name: "${project}-${environment}-worker"
  assume_role_services:
    - lambda.amazonaws.com
  managed_policy_arns:
    - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

```hcl
module "lambda_role" {
  source = "../../../modules/iam"

  name                 = templatestring(local.inputs.lambda_role.name, local.tags)
  assume_role_services = local.inputs.lambda_role.assume_role_services
  managed_policy_arns  = local.inputs.lambda_role.managed_policy_arns
  tags                 = local.tags
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
