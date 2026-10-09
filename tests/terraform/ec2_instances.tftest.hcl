# modules/ec2/instances: standalone instances from a launch template. Private by default, with optional data volumes.

mock_provider "aws" {}

variables {
  name               = "test-instances"
  launch_template_id = "lt-0123456789abcdef0"
  tags               = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  instances          = { app-1 = { subnet_id = "subnet-1" } }
}

run "works_with_the_minimum_inputs_and_is_private_without_termination_protection" {
  command = apply
  module {
    source = "../../modules/ec2/instances"
  }
  assert {
    condition     = length(aws_instance.this) == 1 && aws_instance.this["app-1"].associate_public_ip_address == false && aws_instance.this["app-1"].disable_api_termination == false
    error_message = "an instance gets no public IP and, unless asked, no termination protection"
  }
}

run "termination_protection_can_be_turned_on" {
  command = apply
  module {
    source = "../../modules/ec2/instances"
  }
  variables {
    termination_protection = true
  }
  assert {
    condition     = aws_instance.this["app-1"].disable_api_termination == true
    error_message = "termination_protection = true must protect the instances"
  }
}

run "no_data_volumes_without_asking" {
  command = apply
  module {
    source = "../../modules/ec2/instances"
  }
  assert {
    condition     = length(aws_ebs_volume.this) == 0 && length(aws_volume_attachment.this) == 0
    error_message = "volumes are created only for the instances that list them"
  }
}

run "each_data_volume_is_created_and_attached" {
  command = apply
  module {
    source = "../../modules/ec2/instances"
  }
  variables {
    instances = { app-1 = { subnet_id = "subnet-1", data_volumes = { data = { device_name = "/dev/sdf", size_gb = 50 } } } }
  }
  assert {
    condition     = length(aws_ebs_volume.this) == 1 && length(aws_volume_attachment.this) == 1
    error_message = "a data volume needs its volume and its attachment"
  }
}

run "no_instances_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/instances"
  }
  variables {
    instances = {}
  }
  expect_failures = [var.instances]
}

run "a_private_ip_that_is_not_ipv4_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/instances"
  }
  variables {
    instances = { app-1 = { subnet_id = "subnet-1", private_ip = "not-an-ip" } }
  }
  expect_failures = [var.instances]
}

run "a_data_volume_of_an_unknown_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/ec2/instances"
  }
  variables {
    instances = { app-1 = { subnet_id = "subnet-1", data_volumes = { data = { device_name = "/dev/sdf", size_gb = 50, type = "floppy" } } } }
  }
  expect_failures = [var.instances]
}
