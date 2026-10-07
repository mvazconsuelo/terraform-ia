mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name                    = "web-dev"
  subnet_ids              = ["subnet-a", "subnet-b"]
  launch_template_id      = "lt-0123456789abcdef0"
  launch_template_version = "3"
  min_size                = 1
  desired_size            = 2
  max_size                = 4
}

run "plain_launch_template_asg" {
  command = plan

  assert {
    condition = (
      length(aws_autoscaling_group.this.launch_template) == 1 &&
      length(aws_autoscaling_group.this.mixed_instances_policy) == 0 &&
      length(aws_autoscaling_group.this.instance_refresh) == 1
    )
    error_message = "Plain launch template with instance refresh expected."
  }
}

run "mandatory_tags_propagate" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains([for t in aws_autoscaling_group.this.tag : t.key], k)
    ])
    error_message = "ASG tag blocks need mandatory tags."
  }

  assert {
    condition     = alltrue([for t in aws_autoscaling_group.this.tag : t.propagate_at_launch])
    error_message = "ASG tags must propagate to instances."
  }
}

run "mixed_instances_spot" {
  command = plan

  variables {
    mixed_instances = {
      instance_types                           = ["t3.small", "t3a.small", "t3.medium"]
      on_demand_base_capacity                  = 1
      on_demand_percentage_above_base_capacity = 25
    }
  }

  assert {
    condition = (
      length(aws_autoscaling_group.this.launch_template) == 0 &&
      length(aws_autoscaling_group.this.mixed_instances_policy) == 1
    )
    error_message = "Mixed instances policy must replace the plain launch_template block."
  }
}

run "scaling_and_schedules" {
  command = plan

  variables {
    scaling_policies = {
      cpu = { predefined_metric = "ASGAverageCPUUtilization", target_value = 60 }
    }
    scheduled_actions = {
      night = { recurrence = "0 20 * * *", desired_size = 1 }
    }
  }

  assert {
    condition     = length(aws_autoscaling_policy.this) == 1 && aws_autoscaling_schedule.this["night"].min_size == -1 && aws_autoscaling_schedule.this["night"].desired_capacity == 1
    error_message = "Policy and schedule expected; unspecified sizes stay unchanged (-1)."
  }
}

run "alb_metric_requires_label" {
  command = plan

  variables {
    scaling_policies = {
      req = { predefined_metric = "ALBRequestCountPerTarget", target_value = 1000 }
    }
  }

  expect_failures = [var.scaling_policies]
}

run "rejects_inverted_sizes" {
  command = plan

  variables {
    min_size     = 5
    desired_size = 2
  }

  expect_failures = [var.max_size]
}

run "rejects_bad_health_check_type" {
  command = plan

  variables {
    health_check_type = "NONE"
  }

  expect_failures = [var.health_check_type]
}
