# modules/security-group

Least-privilege security group with rule-per-resource management (`aws_vpc_security_group_*_rule`). No rules and no egress by default.
**Non-goals:** NACLs, prefix-list management, per-service canned rule sets.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
app_sg:
  name: "${project}-${environment}-app"
  description: App tier
  ingress:
    from_alb:
      description: Traffic from the load balancer
      port: 8080
      source_sg: alb
  egress:
    to_db:
      description: Database traffic
      port: 5432
      cidr_ipv4: vpc
    https_out:
      description: HTTPS out
      port: 443
      cidr_ipv4: 0.0.0.0/0
```

```hcl
module "app_sg" {
  source = "../../../modules/security-group"

  name                   = templatestring(local.inputs.app_sg.name, local.tags)
  description            = local.inputs.app_sg.description
  vpc_id                 = module.vpc.vpc_id
  vpc_cidr_block         = module.vpc.vpc_cidr_block
  source_security_groups = { alb = module.alb_sg.security_group_id }
  ingress_rules          = local.inputs.app_sg.ingress
  egress_rules           = local.inputs.app_sg.egress
  tags                   = local.tags
}
```

The module resolves the rules, the call only passes values: `port` sets `from_port` and `to_port`, `cidr_ipv4: vpc` is `vpc_cidr_block`, and `source_sg` is a key of `source_security_groups`. Use `vpc` or `source_sg` instead of a group on each side of a pair, because two groups that reference each other are a dependency cycle.

## Resources and tags

`aws_security_group`, ingress/egress rules (all taggable and tagged). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `description`, `vpc_id`, `vpc_cidr_block`, `source_security_groups`, `tags`, `extra_tags`, `ingress_rules`, `egress_rules` (one source/destination each: `cidr_ipv4`, `source_sg`, `referenced_security_group_id` or `prefix_list_id`; a `port` or `from_port`/`to_port`; protocol tcp/udp/icmp/-1), `allow_public_ingress` (default false; required for 0.0.0.0/0), `allow_all_egress` (default false). See `variables.tf` for types, defaults and validations.

## Outputs

`security_group_id`, `security_group_arn`, `ingress_rules`, `egress_rules` (resolved rules, for auditing).

## Lifecycle

Uses `name_prefix` + `create_before_destroy`, so replacement (e.g. changed `description`, which is immutable) swaps the group without name collisions; attached resources are re-pointed in the same apply.

## Cost

Free.
