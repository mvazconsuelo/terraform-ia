# modules/eventbridge

EventBridge rules and targets on the default bus or an optional custom bus, with retries, DLQ and Lambda invoke permissions.
**Non-goals:** archives/replay, pipes, schedulers, cross-account bus policies.

## Usage

```hcl
module "events" {
  source = "../../modules/eventbridge"

  name = "payments-dev"
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  rules = {
    nightly = {
      schedule_expression = "cron(0 3 * * ? *)"
      targets = { job = { arn = module.worker.function_arn, lambda_function_name = module.worker.function_name } }
    }
  }
}
```

## Resources and tags

`aws_cloudwatch_event_bus` and `aws_cloudwatch_event_rule` (taggable, tagged); targets and Lambda permissions are not. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `create_bus` (false), `rules` (each: `schedule_expression` and/or `event_pattern`, `enabled`, `targets` with `arn`, `role_arn`, `input`, `dead_letter_arn`, `lambda_function_name`, retry settings). See `variables.tf` for types, defaults and validations.

## Outputs

`bus_name`, `bus_arn`, `rule_arns`.

## Lifecycle

Schedule rules only work on the default bus (enforced by a precondition). Renaming a rule key replaces the rule and its targets.

## Cost

Custom/partner events are billed per million events; scheduled and AWS-service events on the default bus are free.
