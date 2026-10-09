# modules/elb/nlb

Network Load Balancer with target groups and listeners. Internal and deletion-protected by default.
**Non-goals:** target registration (done by EKS/ASG), ALB/GWLB, WAF.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
nlb:
  name: "${project}-${environment}"
  target_groups:
    app:
      port: 8080
  listeners:
    http:
      port: 80
      target_group: app
```

```hcl
module "nlb" {
  source = "../../../modules/elb/nlb"

  name          = templatestring(local.inputs.nlb.name, local.tags)
  target_groups = local.inputs.nlb.target_groups
  listeners     = local.inputs.nlb.listeners
  tags          = local.tags
  vpc_id        = module.vpc.vpc_id
  subnet_ids    = module.vpc.private_subnet_ids
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
