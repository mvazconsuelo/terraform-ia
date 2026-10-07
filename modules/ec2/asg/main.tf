resource "aws_autoscaling_group" "this" {
  name_prefix         = "${var.name}-"
  min_size            = var.min_size
  max_size            = var.max_size
  desired_capacity    = var.desired_size
  vpc_zone_identifier = var.subnet_ids

  health_check_type         = var.health_check_type
  health_check_grace_period = var.health_check_grace_period
  target_group_arns         = var.target_group_arns

  dynamic "launch_template" {
    for_each = var.mixed_instances == null ? [1] : []

    content {
      id      = var.launch_template_id
      version = var.launch_template_version
    }
  }

  dynamic "mixed_instances_policy" {
    for_each = var.mixed_instances == null ? [] : [var.mixed_instances]

    content {
      instances_distribution {
        on_demand_base_capacity                  = mixed_instances_policy.value.on_demand_base_capacity
        on_demand_percentage_above_base_capacity = mixed_instances_policy.value.on_demand_percentage_above_base_capacity
        spot_allocation_strategy                 = "price-capacity-optimized"
      }

      launch_template {
        launch_template_specification {
          launch_template_id = var.launch_template_id
          version            = var.launch_template_version
        }

        dynamic "override" {
          for_each = mixed_instances_policy.value.instance_types

          content {
            instance_type = override.value
          }
        }
      }
    }
  }

  dynamic "instance_refresh" {
    for_each = var.enable_instance_refresh ? [1] : []

    content {
      strategy = "Rolling"

      preferences {
        min_healthy_percentage = var.instance_refresh_min_healthy_percentage
      }
    }
  }

  # ASGs take tags as repeated `tag` blocks (not a `tags` map); propagate so instances are cost-attributable.
  dynamic "tag" {
    for_each = merge(local.tags, { Name = var.name })

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    create_before_destroy = true
    # Scaling policies / scheduled actions own desired capacity after creation.
    ignore_changes = [desired_capacity]
  }
}

resource "aws_autoscaling_policy" "this" {
  for_each = var.scaling_policies

  name                      = "${var.name}-${each.key}"
  autoscaling_group_name    = aws_autoscaling_group.this.name
  policy_type               = "TargetTrackingScaling"
  estimated_instance_warmup = each.value.warmup_seconds

  target_tracking_configuration {
    target_value = each.value.target_value

    predefined_metric_specification {
      predefined_metric_type = each.value.predefined_metric
      resource_label         = each.value.resource_label
    }
  }
}

resource "aws_autoscaling_schedule" "this" {
  for_each = var.scheduled_actions

  scheduled_action_name  = "${var.name}-${each.key}"
  autoscaling_group_name = aws_autoscaling_group.this.name
  recurrence             = each.value.recurrence
  time_zone              = each.value.time_zone
  min_size               = each.value.min_size
  max_size               = each.value.max_size
  desired_capacity       = each.value.desired_size
}
