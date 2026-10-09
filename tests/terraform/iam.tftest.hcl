# modules/iam: a role with its trust policy, policies and an optional instance profile.

mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

variables {
  name = "test-role"
  tags = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_a_trusted_service_and_has_no_instance_profile" {
  command = apply
  module {
    source = "../../modules/iam"
  }
  variables {
    assume_role_services = ["ec2.amazonaws.com"]
  }
  assert {
    condition     = length(aws_iam_instance_profile.this) == 0
    error_message = "an instance profile is created only when asked"
  }
}

run "an_instance_profile_is_created_when_asked" {
  command = apply
  module {
    source = "../../modules/iam"
  }
  variables {
    assume_role_services    = ["ec2.amazonaws.com"]
    create_instance_profile = true
  }
  assert {
    condition     = length(aws_iam_instance_profile.this) == 1
    error_message = "create_instance_profile = true must create the profile"
  }
}

run "each_managed_policy_is_attached" {
  command = apply
  module {
    source = "../../modules/iam"
  }
  variables {
    assume_role_services = ["ec2.amazonaws.com"]
    managed_policy_arns  = ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore", "arn:aws:iam::aws:policy/ReadOnlyAccess"]
  }
  assert {
    condition     = length(aws_iam_role_policy_attachment.this) == 2
    error_message = "one attachment per managed policy"
  }
}

run "a_role_with_no_one_who_can_assume_it_is_rejected" {
  command = plan
  module {
    source = "../../modules/iam"
  }
  expect_failures = [aws_iam_role.this]
}

run "an_inline_policy_that_is_not_json_is_rejected" {
  command = plan
  module {
    source = "../../modules/iam"
  }
  variables {
    assume_role_services = ["ec2.amazonaws.com"]
    inline_policies      = { broken = "not json" }
  }
  expect_failures = [var.inline_policies]
}

run "a_session_duration_out_of_range_is_rejected" {
  command = plan
  module {
    source = "../../modules/iam"
  }
  variables {
    assume_role_services = ["ec2.amazonaws.com"]
    max_session_duration = 60
  }
  expect_failures = [var.max_session_duration]
}
