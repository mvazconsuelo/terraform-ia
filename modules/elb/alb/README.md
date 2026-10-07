# modules/elb/alb

Application Load Balancer (layer 7): HTTP/HTTPS listeners, path/host forwarding rules, redirects and fixed responses, optional WAF association and access logs. Internal and deletion-protected by default; invalid headers are dropped.
**Non-goals:** NLB (`elb/nlb`), target registration (done by EKS/ASG), certificates (ACM), WAF rule sets, Route 53 records.

## Usage

```hcl
module "alb" {
  source = "../../../modules/elb/alb"

  name               = "shop-dev"
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.alb_sg.security_group_id]
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "shop" }

  target_groups = { web = { port = 8080 }, api = { port = 9090 } }
  listeners = {
    http  = { port = 80, protocol = "HTTP", default_action = { type = "redirect", redirect = {} } }
    https = { port = 443, certificate_arn = var.certificate_arn, default_action = { type = "forward", target_group = "web" } }
  }
  rules = {
    api = { listener = "https", priority = 10, target_group = "api", path_patterns = ["/api/*"] }
  }
}
```

## Resources and tags

`aws_lb`, `aws_lb_target_group`, `aws_lb_listener`, `aws_lb_listener_rule` (all taggable, tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`); `aws_wafv2_web_acl_association` is not taggable.

## Inputs

`name` (<=24 chars), `tags`, `extra_tags`, `vpc_id`, `subnet_ids` (>=2), `security_group_ids` (>=1), `internal` (true), `enable_deletion_protection` (true), `idle_timeout`, `access_logs_bucket`, `web_acl_arn`, `target_groups` (port, protocol, target_type, deregistration_delay, health_check), `listeners` (default action `forward`, `redirect` or `fixed_response`; HTTPS needs `certificate_arn`), `rules` (listener, unique priority, target_group, path_patterns/host_headers). Cross-references between listeners, rules and target groups are checked by preconditions.

## Outputs

`lb_arn`, `lb_arn_suffix`, `dns_name`, `zone_id`, `listener_arns` (an API Gateway VPC Link can target an ALB listener), `target_group_arns`, `target_group_arn_suffixes` (for `ec2/asg` `ALBRequestCountPerTarget` labels).

## Lifecycle

Changing `name`, type or the subnets' AZs replaces the ALB (new DNS name, downtime). Target group `port`/`protocol`/`target_type` changes replace the group and drop registrations. Rule priorities are unique per listener; reordering priorities is an in-place update.

## Cost

Hourly + LCU (connections, bytes, rule evaluations): many rules raise LCUs. An internal ALB in private subnets avoids public exposure but not the hourly charge.

## Testing

`terraform init -backend=false && terraform test` (mock provider, no credentials).
