mock_provider "aws" {
  mock_data "aws_region" {
    defaults = {
      region = "us-east-1"
    }
  }
}

variables {
  name = "test-dev"
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  cidr_block           = "10.0.0.0/16"
  availability_zones   = ["us-east-1a", "us-east-1b"]
  public_subnet_cidrs  = ["10.0.0.0/24", "10.0.1.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
}

run "private_only_no_nat_by_default" {
  command = plan

  assert {
    condition     = length(aws_nat_gateway.this) == 0
    error_message = "NAT must be opt-in."
  }

  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Expected one private subnet per AZ."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Environment", "Owner", "CostCenter", "Project", "ManagedBy", "Name"] :
      contains(keys(aws_vpc.this.tags), k)
    ])
    error_message = "VPC is missing mandatory tags."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.private : s.tags["CostCenter"] == "cc-1234"])
    error_message = "Subnets must carry mandatory tags."
  }
}

run "mandatory_tags_cannot_be_overridden" {
  command = plan

  variables {
    extra_tags = { Owner = "someone-else", Extra = "x" }
  }

  assert {
    condition     = aws_vpc.this.tags["Owner"] == "platform-team" && aws_vpc.this.tags["Extra"] == "x"
    error_message = "Mandatory tags must win over caller tags."
  }
}

run "single_nat" {
  command = plan

  variables {
    nat_gateway_mode = "single"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 1
    error_message = "single mode must create exactly one NAT."
  }
}

run "per_az_nat" {
  command = plan

  variables {
    nat_gateway_mode = "per_az"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 2
    error_message = "per_az mode must create one NAT per AZ."
  }
}

run "nat_requires_public_subnets" {
  command = plan

  variables {
    nat_gateway_mode    = "single"
    public_subnet_cidrs = []
  }

  expect_failures = [aws_vpc.this]
}

run "invalid_environment_rejected" {
  command = plan

  variables {
    tags = {
      environment = "sandbox"
      owner       = "a"
      cost_center = "b"
      project     = "c"
    }
  }

  expect_failures = [var.tags]
}
