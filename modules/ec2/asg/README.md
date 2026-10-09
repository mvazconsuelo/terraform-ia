# modules/ec2/asg

Auto Scaling Group on top of a launch template: rolling instance refresh, tag propagation, optional mixed On-Demand/Spot, target-tracking policies and scheduled actions.
**Non-goals:** the instance definition (`ec2/launch-template`), EKS nodes (use `eks/node-group`: EKS owns its ASGs), load balancers (pass `target_group_arns` from `modules/elb/nlb`).

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
web:
  name: "${project}-${environment}-web"
  min_size: 2
  desired_size: 2
  max_size: 6
  health_check_type: ELB
  scaling_policies:
    cpu:
      predefined_metric: ASGAverageCPUUtilization
      target_value: 60
```

```hcl
module "web" {
  source = "../../../modules/ec2/asg"

  name                    = templatestring(local.inputs.web.name, local.tags)
  min_size                = local.inputs.web.min_size
  desired_size            = local.inputs.web.desired_size
  max_size                = local.inputs.web.max_size
  health_check_type       = local.inputs.web.health_check_type
  scaling_policies        = local.inputs.web.scaling_policies
  tags                    = local.tags
  subnet_ids              = module.vpc.private_subnet_ids
  launch_template_id      = module.web_template.launch_template_id
  launch_template_version = module.web_template.latest_version
  target_group_arns       = [module.nlb.target_group_arns["app"]]
}
```

## Resources and tags

`aws_autoscaling_group` (takes repeated `tag` blocks with `propagate_at_launch`, enforced by rule `GOV-003`), `aws_autoscaling_policy`, `aws_autoscaling_schedule`. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `subnet_ids`, `launch_template_id`, `launch_template_version`, `min_size`/`desired_size`/`max_size`, `target_group_arns`, `health_check_type`, `health_check_grace_period`, `mixed_instances`, `scaling_policies`, `scheduled_actions`, `enable_instance_refresh`, `instance_refresh_min_healthy_percentage`. See `variables.tf` for types, defaults and validations.

## Outputs

`autoscaling_group_name`, `autoscaling_group_arn`.

## Lifecycle

`desired_capacity` is in `ignore_changes` (policies and schedules own it). A new `launch_template_version` triggers a rolling refresh (`min_healthy_percentage` 90). `create_before_destroy` with `name_prefix` lets the group be replaced without a name clash. Switching between plain and mixed-instances mode replaces the launch configuration of the group.

## Cost

Instance type x average capacity; Spot lowers cost but can be interrupted; scheduled scale-down is the cheapest saving for non-production.
