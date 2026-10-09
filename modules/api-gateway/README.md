# modules/api-gateway

API Gateway **HTTP API** with Lambda and private (VPC Link V2 -> NLB/ALB listener) integrations, access logs and throttling.
**Non-goals:** REST APIs, custom domains/ACM, authorizers, WAF.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
api:
  name: "${project}-${environment}"
  routes:
    app:
      route_key: ANY /app/{proxy+}
      integration_type: vpc_link
```

```hcl
module "api" {
  source = "../../../modules/api-gateway"

  name = templatestring(local.inputs.api.name, local.tags)
  tags = local.tags

  vpc_link = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpclink_sg.security_group_id]
  }

  # The route comes from inputs.yaml; its listener is another module's output, so it is wired here.
  routes = {
    for key, route in local.inputs.api.routes : key => merge(route, { listener_arn = module.nlb.listener_arns["http"] })
  }
}
```

## Resources and tags

`aws_apigatewayv2_api`, `aws_apigatewayv2_vpc_link`, `aws_apigatewayv2_stage`, `aws_cloudwatch_log_group` (taggable, tagged); integrations, routes and Lambda permissions are not. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `routes` (`lambda` or `vpc_link`), `vpc_link` (required if any route uses it), `stage_name`, `throttling_*`, `access_log_retention_days`, `cors`, `description`. See `variables.tf` for types, defaults and validations.

## Outputs

`api_id`, `api_endpoint`, `execution_arn`, `stage_invoke_url`, `vpc_link_id`.

## Lifecycle

`auto_deploy` is on, so route changes go live immediately. Changing the VPC Link subnets/SGs updates it in place; replacing it briefly interrupts private routes. A **VPC Link is not a VPC endpoint**: it carries API Gateway -> private NLB traffic; VPC endpoints carry workload -> AWS service traffic.

## Cost

Per-request pricing; VPC Link V2 has no hourly charge itself but the NLB and ENIs it uses do.
