mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name                 = "app-lambda"
  assume_role_services = ["lambda.amazonaws.com"]
}

run "role_with_mandatory_tags" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_iam_role.this.tags), k)
    ])
    error_message = "Role is missing mandatory tags."
  }

  assert {
    condition     = length(aws_iam_instance_profile.this) == 0
    error_message = "Instance profile must be opt-in."
  }
}

run "attachments_and_instance_profile" {
  command = plan

  variables {
    managed_policy_arns     = ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
    inline_policies         = { s3 = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
    create_instance_profile = true
  }

  assert {
    condition     = length(aws_iam_role_policy_attachment.this) == 1 && length(aws_iam_role_policy.this) == 1 && length(aws_iam_instance_profile.this) == 1
    error_message = "Expected one attachment, one inline policy and one instance profile."
  }
}

run "requires_a_principal" {
  command = plan

  variables {
    assume_role_services = []
  }

  expect_failures = [aws_iam_role.this]
}

run "rejects_invalid_inline_policy" {
  command = plan

  variables {
    inline_policies = { bad = "not json" }
  }

  expect_failures = [var.inline_policies]
}
