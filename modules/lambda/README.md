# modules/lambda

Lambda function with its log group (retention enforced), optional VPC attachment, DLQ and tracing.
**Non-goals:** execution role (use `modules/iam`), triggers/permissions (API Gateway and EventBridge modules create their own), layers authoring, code packaging.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
worker:
  function_name: "${project}-${environment}-worker"
  handler: index.handler
  runtime: python3.12
  filename: build/worker.zip
```

```hcl
module "worker" {
  source = "../../../modules/lambda"

  function_name    = templatestring(local.inputs.worker.function_name, local.tags)
  handler          = local.inputs.worker.handler
  runtime          = local.inputs.worker.runtime
  filename         = local.inputs.worker.filename
  source_code_hash = filebase64sha256(local.inputs.worker.filename)
  tags             = local.tags
  role_arn         = module.lambda_role.role_arn
}
```

## Resources and tags

`aws_lambda_function` and `aws_cloudwatch_log_group` (taggable, tagged). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`function_name`, `tags`, `extra_tags`, `role_arn`, `handler`, `runtime`, package via `filename` **or** `s3_bucket`+`s3_key`, `source_code_hash`, `architectures` (arm64), `memory_size` (128), `timeout` (10), `environment_variables` (no secrets), `vpc_config`, `log_retention_days` (30), `tracing_mode`, `reserved_concurrent_executions`, `dead_letter_target_arn`, `layers`. See `variables.tf` for types, defaults and validations.

## Outputs

`function_name`, `function_arn`, `invoke_arn`, `log_group_name`.

## Lifecycle

Changing `function_name` replaces the function. The log group is created first so the function cannot spawn an untagged, never-expiring one.

## Cost

Requests x duration x memory; arm64 is cheaper than x86_64; tracing and VPC attachment add cost/latency.
