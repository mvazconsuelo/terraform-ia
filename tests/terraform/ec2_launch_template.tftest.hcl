# modules/ec2/launch-template: the hardened definition of an instance (IMDSv2, encrypted root volume), shared by ec2/instances and ec2/asg.

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
}

variables {
  name               = "test-template"
  security_group_ids = ["sg-1"]
  tags               = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_requires_imdsv2" {
  command = apply
  module {
    source = "../../modules/ec2/launch-template"
  }
  assert {
    condition     = one(aws_launch_template.this.metadata_options).http_tokens == "required"
    error_message = "the instance metadata service must require tokens (IMDSv2)"
  }
}

run "the_root_volume_is_encrypted_gp3_of_20_gb_by_default" {
  command = apply
  module {
    source = "../../modules/ec2/launch-template"
  }
  assert {
    condition     = one(one(aws_launch_template.this.block_device_mappings).ebs).encrypted == "true" && one(one(aws_launch_template.this.block_device_mappings).ebs).volume_size == 20
    error_message = "the root volume is encrypted and 20 GB by default"
  }
}

run "the_ami_comes_from_the_ssm_parameter_unless_one_is_given" {
  command = apply
  module {
    source = "../../modules/ec2/launch-template"
  }
  assert {
    condition     = aws_launch_template.this.image_id == "ami-0123456789abcdef0"
    error_message = "with no ami_id the latest image of the SSM parameter is used"
  }
}

run "a_pinned_ami_wins_over_the_ssm_parameter" {
  command = apply
  module {
    source = "../../modules/ec2/launch-template"
  }
  variables {
    ami_id = "ami-0fedcba9876543210"
  }
  assert {
    condition     = aws_launch_template.this.image_id == "ami-0fedcba9876543210"
    error_message = "ami_id pins the image"
  }
}

run "an_instance_type_that_does_not_look_like_one_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/launch-template"
  }
  variables {
    instance_type = "huge"
  }
  expect_failures = [var.instance_type]
}

run "a_root_volume_too_small_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/launch-template"
  }
  variables {
    root_volume_size_gb = 1
  }
  expect_failures = [var.root_volume_size_gb]
}

run "an_unknown_root_volume_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/launch-template"
  }
  variables {
    root_volume_type = "floppy"
  }
  expect_failures = [var.root_volume_type]
}
