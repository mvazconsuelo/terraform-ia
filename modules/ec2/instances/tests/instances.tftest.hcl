mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name               = "bastion-dev"
  launch_template_id = "lt-0123456789abcdef0"
  instances = {
    a = { subnet_id = "subnet-a" }
    b = {
      subnet_id     = "subnet-b"
      instance_type = "t3.medium"
      data_volumes  = { data = { device_name = "/dev/sdf", size_gb = 100 } }
    }
  }
}

run "private_instances_from_template" {
  command = plan

  assert {
    condition = (
      length(aws_instance.this) == 2 &&
      !aws_instance.this["a"].associate_public_ip_address &&
      aws_instance.this["a"].launch_template[0].version == "$Default"
    )
    error_message = "Private instances launched from the template's default version expected."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      alltrue([for i in values(aws_instance.this) : contains(keys(i.tags), k) && contains(keys(i.volume_tags), k)]) &&
      alltrue([for v in values(aws_ebs_volume.this) : contains(keys(v.tags), k)])
    ])
    error_message = "Instances, their volumes and data volumes need mandatory tags."
  }

  assert {
    condition     = aws_instance.this["a"].tags["Name"] == "bastion-dev-a"
    error_message = "Name tag must be <name>-<key>."
  }
}

run "data_volumes_encrypted_and_attached" {
  command = plan

  assert {
    condition     = length(aws_ebs_volume.this) == 1 && aws_ebs_volume.this["b/data"].encrypted && length(aws_volume_attachment.this) == 1
    error_message = "One encrypted data volume attached to instance b expected."
  }
}

run "termination_protection" {
  command = plan

  variables {
    termination_protection = true
  }

  assert {
    condition     = alltrue([for i in values(aws_instance.this) : i.disable_api_termination])
    error_message = "Termination protection expected."
  }
}

run "rejects_empty_instances" {
  command = plan

  variables {
    instances = {}
  }

  expect_failures = [var.instances]
}

run "rejects_bad_private_ip" {
  command = plan

  variables {
    instances = { a = { subnet_id = "subnet-a", private_ip = "not-an-ip" } }
  }

  expect_failures = [var.instances]
}
