mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name               = "web-dev"
  security_group_ids = ["sg-1"]
  ami_id             = "ami-0123456789abcdef0"
}

run "hardened_defaults" {
  command = plan

  assert {
    condition = (
      aws_launch_template.this.metadata_options[0].http_tokens == "required" &&
      aws_launch_template.this.block_device_mappings[0].ebs[0].encrypted &&
      aws_launch_template.this.block_device_mappings[0].ebs[0].volume_type == "gp3"
    )
    error_message = "IMDSv2, encrypted gp3 root volume are mandatory."
  }

  assert {
    condition     = length(aws_launch_template.this.instance_market_options) == 0 && length(data.aws_ssm_parameter.ami) == 0
    error_message = "On-demand and no SSM lookup when ami_id is set."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_launch_template.this.tags), k) && alltrue([for ts in aws_launch_template.this.tag_specifications : contains(keys(ts.tags), k)])
    ])
    error_message = "Template and its instance/volume tag specifications need mandatory tags."
  }
}

run "spot_profile_and_placement" {
  command = plan

  variables {
    use_spot                  = true
    iam_instance_profile_name = "web-dev"
    placement_group           = "pg-1"
  }

  assert {
    condition = (
      length(aws_launch_template.this.instance_market_options) == 1 &&
      length(aws_launch_template.this.iam_instance_profile) == 1 &&
      length(aws_launch_template.this.placement) == 1
    )
    error_message = "Spot, instance profile and placement expected."
  }
}

run "resolves_ami_from_ssm_when_unset" {
  command = plan

  variables {
    ami_id = null
  }

  assert {
    condition     = length(data.aws_ssm_parameter.ami) == 1
    error_message = "SSM AMI lookup expected when ami_id is null."
  }
}

run "rejects_bad_instance_type" {
  command = plan

  variables {
    instance_type = "large"
  }

  expect_failures = [var.instance_type]
}

run "rejects_small_root_volume" {
  command = plan

  variables {
    root_volume_size_gb = 2
  }

  expect_failures = [var.root_volume_size_gb]
}
