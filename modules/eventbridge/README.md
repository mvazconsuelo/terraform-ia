# modules/eventbridge

EventBridge rules and targets on the default bus or an optional custom bus, with retries, DLQ and Lambda invoke permissions.
**Non-goals:** archives/replay, pipes, schedulers, cross-account bus policies.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
events:
  name: "${project}-${environment}"
  rules:
    nightly:
      schedule_expression: cron(0 3 * * ? *)
```

```hcl
module "events" {
  source = "../../../modules/eventbridge"

  name = templatestring(local.inputs.events.name, local.tags)
  tags = local.tags

  # The rule comes from inputs.yaml; its target is another module's output, so it is wired here.
  rules = {
    for key, rule in local.inputs.events.rules : key => merge(rule, {
      targets = { job = { arn = module.worker.function_arn, lambda_function_name = module.worker.function_name } }
    })
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
