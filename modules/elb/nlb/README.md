# modules/elb/nlb

Network Load Balancer with target groups and listeners. Internal and deletion-protected by default.
**Non-goals:** target registration (done by EKS/ASG), ALB/GWLB, WAF.

## Usage

```hcl
module "nlb" {
  source = "../../../modules/elb/nlb"

  name       = "payments-dev"
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  target_groups = { app = { port = 8080 } }
  listeners     = { http = { port = 80, target_group = "app" } }
}
```

## Resources and tags

`aws_lb`, `aws_lb_target_group`, `aws_lb_listener` (all taggable, tagged). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name` (<=24 chars), `tags`, `extra_tags`, `vpc_id`, `subnet_ids` (>=2), `internal` (true), `security_group_ids`, `enable_deletion_protection` (true), `enable_cross_zone_load_balancing` (false), `target_groups`, `listeners` (TLS needs `certificate_arn`). See `variables.tf` for types, defaults and validations.

## Outputs

`lb_arn`, `lb_arn_suffix`, `dns_name`, `zone_id`, `listener_arns` (feed API Gateway VPC Link routes), `target_group_arns`.

## Lifecycle

Changing `name`, type or subnets' AZs replaces the NLB (new DNS name, downtime). Target group `port`/`protocol`/`target_type` changes replace the group and drop registrations.

## Cost

Hourly + LCU; cross-zone adds inter-AZ data charges.
