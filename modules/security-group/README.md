# modules/security-group

Least-privilege security group with rule-per-resource management (`aws_vpc_security_group_*_rule`). No rules and no egress by default.
**Non-goals:** NACLs, prefix-list management, per-service canned rule sets.

## Usage

```hcl
module "app_sg" {
  source = "../../modules/security-group"

  name        = "payments-dev-app"
  description = "App tier"
  vpc_id      = module.vpc.vpc_id
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  ingress_rules = {
    from_nlb = { description = "From NLB", from_port = 8080, to_port = 8080, referenced_security_group_id = module.nlb_sg.security_group_id }
  }
  egress_rules = {
    https = { description = "HTTPS out", from_port = 443, to_port = 443, cidr_ipv4 = "0.0.0.0/0" }
  }
}
```

## Resources and tags

`aws_security_group`, ingress/egress rules (all taggable and tagged). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `description`, `vpc_id`, `tags`, `extra_tags`, `ingress_rules`, `egress_rules` (one source/destination each; protocol tcp/udp/icmp/-1), `allow_public_ingress` (default false; required for 0.0.0.0/0), `allow_all_egress` (default false). See `variables.tf` for types, defaults and validations.

## Outputs

`security_group_id`, `security_group_arn`, `ingress_rules`, `egress_rules` (resolved rules, for auditing).

## Lifecycle

Uses `name_prefix` + `create_before_destroy`, so replacement (e.g. changed `description`, which is immutable) swaps the group without name collisions; attached resources are re-pointed in the same apply.

## Cost

Free.

## Testing

`terraform init -backend=false && terraform test` (uses `mock_provider`; no credentials).
