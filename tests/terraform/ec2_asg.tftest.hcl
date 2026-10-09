# modules/ec2/asg: an Auto Scaling Group over a launch template, with rolling refresh and optional scaling.

mock_provider "aws" {}

variables {
  name                    = "test-asg"
  subnet_ids              = ["subnet-1", "subnet-2"]
  launch_template_id      = "lt-0123456789abcdef0"
  launch_template_version = "1"
  min_size                = 1
  desired_size            = 1
  max_size                = 2
  tags                    = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_has_no_scaling_policies" {
  command = apply
  module {
    source = "../../modules/ec2/asg"
  }
  assert {
    condition     = aws_autoscaling_group.this.min_size == 1 && aws_autoscaling_group.this.max_size == 2 && length(aws_autoscaling_policy.this) == 0
    error_message = "the group takes the given sizes and has no scaling policy unless asked"
  }
}

run "the_health_check_is_ec2_with_a_grace_period_of_300_seconds_by_default" {
  command = apply
  module {
    source = "../../modules/ec2/asg"
  }
  assert {
    condition     = aws_autoscaling_group.this.health_check_type == "EC2" && aws_autoscaling_group.this.health_check_grace_period == 300
    error_message = "defaults: EC2 health check and 300 seconds of grace"
  }
}

run "a_scaling_policy_is_created_for_each_one_given" {
  command = apply
  module {
    source = "../../modules/ec2/asg"
  }
  variables {
    scaling_policies = { cpu = { predefined_metric = "ASGAverageCPUUtilization", target_value = 60 } }
  }
  assert {
    condition     = length(aws_autoscaling_policy.this) == 1
    error_message = "one target-tracking policy per entry"
  }
}

run "sizes_out_of_order_are_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/asg"
  }
  variables {
    min_size     = 3
    desired_size = 1
    max_size     = 2
  }
  expect_failures = [var.max_size]
}

run "no_subnets_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/asg"
  }
  variables {
    subnet_ids = []
  }
  expect_failures = [var.subnet_ids]
}

run "an_unknown_health_check_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/asg"
  }
  variables {
    health_check_type = "MAGIC"
  }
  expect_failures = [var.health_check_type]
}

run "a_request_count_policy_without_a_resource_label_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/asg"
  }
  variables {
    scaling_policies = { requests = { predefined_metric = "ALBRequestCountPerTarget", target_value = 100 } }
  }
  expect_failures = [var.scaling_policies]
}
