# modules/lambda

Lambda function with its log group (retention enforced), optional VPC attachment, DLQ and tracing.
**Non-goals:** execution role (use `modules/iam`), triggers/permissions (API Gateway and EventBridge modules create their own), layers authoring, code packaging.

## Usage

```hcl
module "worker" {
  source = "../../modules/lambda"

  function_name    = "payments-dev-worker"
  role_arn         = module.lambda_role.role_arn
  handler          = "index.handler"
  runtime          = "python3.12"
  filename         = "build/worker.zip"
  source_code_hash = filebase64sha256("build/worker.zip")
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }
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

## Testing

`terraform init -backend=false && terraform test` (uses `mock_provider`; no credentials).
