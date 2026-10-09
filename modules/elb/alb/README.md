# modules/elb/alb

Application Load Balancer (layer 7): HTTP/HTTPS listeners, path/host forwarding rules, redirects and fixed responses, optional WAF association and access logs. Internal and deletion-protected by default; invalid headers are dropped.
**Non-goals:** NLB (`elb/nlb`), target registration (done by EKS/ASG), creating certificates (`acm`), WAF rule sets, Route 53 records.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
alb:
  name: "${project}-${environment}"
  target_groups:
    web:
      port: 8080
    api:
      port: 9090
  listeners:
    http:
      port: 80
      protocol: HTTP
      default_action:
        type: redirect
        redirect:
          status_code: HTTP_301
    https:
      port: 443
      certificate: web # a key of the certificates the call passes
      default_action:
        type: forward
        target_group: web
  rules:
    api:
      listener: https
      priority: 10
      target_group: api
      path_patterns:
        - /api/*
```

```hcl
module "alb" {
  source = "../../../modules/elb/alb"

  name               = templatestring(local.inputs.alb.name, local.tags)
  target_groups      = local.inputs.alb.target_groups
  listeners          = local.inputs.alb.listeners
  rules              = local.inputs.alb.rules
  certificates       = { web = module.certificate.certificate_arn }
  tags               = local.tags
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [module.alb_sg.security_group_id]
}
```

## Resources and tags

`aws_lb`, `aws_lb_target_group`, `aws_lb_listener`, `aws_lb_listener_rule` (all taggable, tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`); `aws_wafv2_web_acl_association` is not taggable.

## Inputs

`name` (<=24 chars), `tags`, `extra_tags`, `vpc_id`, `public_subnet_ids` and `private_subnet_ids` (the module uses the private ones when `internal`, else the public ones; >=2), `security_group_ids` (>=1), `internal` (true), `enable_deletion_protection` (true), `idle_timeout`, `access_logs_bucket`, `web_acl_arn`, `target_groups` (port, protocol, target_type, deregistration_delay, health_check), `listeners` (default action `forward`, `redirect` or `fixed_response`; HTTPS needs a `certificate`, a key of `certificates`, or a `certificate_arn`), `certificates` (name to ARN, for example the output of `acm`), `rules` (listener, unique priority, target_group, path_patterns/host_headers). Cross-references between listeners, rules and target groups are checked by preconditions.

## Outputs

`lb_arn`, `lb_arn_suffix`, `dns_name`, `zone_id`, `listener_arns` (an API Gateway VPC Link can target an ALB listener), `target_group_arns`, `target_group_arn_suffixes` (for `ec2/asg` `ALBRequestCountPerTarget` labels).

## Lifecycle

Changing `name`, type or the subnets' AZs replaces the ALB (new DNS name, downtime). Target group `port`/`protocol`/`target_type` changes replace the group and drop registrations. Rule priorities are unique per listener; reordering priorities is an in-place update.

## Cost

Hourly + LCU (connections, bytes, rule evaluations): many rules raise LCUs. An internal ALB in private subnets avoids public exposure but not the hourly charge.
