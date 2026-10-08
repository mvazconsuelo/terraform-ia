# modules/api-gateway

API Gateway **HTTP API** with Lambda and private (VPC Link V2 -> NLB/ALB listener) integrations, access logs and throttling.
**Non-goals:** REST APIs, custom domains/ACM, authorizers, WAF.

## Usage

```hcl
module "api" {
  source = "../../modules/api-gateway"

  name = "payments-dev"
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  vpc_link = { subnet_ids = module.vpc.private_subnet_ids, security_group_ids = [module.vpclink_sg.security_group_id] }
  routes = {
    orders = { route_key = "ANY /orders/{proxy+}", integration_type = "vpc_link", listener_arn = module.nlb.listener_arns["http"] }
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
