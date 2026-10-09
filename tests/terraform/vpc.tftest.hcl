# modules/vpc: a private network. The public tier and the NAT gateways are opt-in, and the module checks that they fit together.

mock_provider "aws" {}

variables {
  name                 = "test-vpc"
  cidr_block           = "10.0.0.0/16"
  availability_zones   = ["us-east-1a", "us-east-1b"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  tags                 = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_is_private_with_no_nat" {
  command = apply
  module {
    source = "../../modules/vpc"
  }
  assert {
    condition     = length(aws_subnet.private) == 2 && length(aws_subnet.public) == 0 && length(aws_internet_gateway.this) == 0 && length(aws_nat_gateway.this) == 0
    error_message = "by default there are only private subnets, no internet gateway and no NAT"
  }
}

run "the_free_s3_gateway_endpoint_is_on_by_default" {
  command = apply
  module {
    source = "../../modules/vpc"
  }
  assert {
    condition     = length(aws_vpc_endpoint.s3) == 1
    error_message = "the S3 gateway endpoint costs nothing, so it is created by default"
  }
}

run "public_subnets_bring_an_internet_gateway" {
  command = apply
  module {
    source = "../../modules/vpc"
  }
  variables {
    public_subnet_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
  }
  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_internet_gateway.this) == 1
    error_message = "a public tier needs its subnets and the internet gateway"
  }
}

run "a_single_nat_gateway_is_one" {
  command = apply
  module {
    source = "../../modules/vpc"
  }
  variables {
    public_subnet_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
    nat_gateway_mode    = "single"
  }
  assert {
    condition     = length(aws_nat_gateway.this) == 1
    error_message = "nat_gateway_mode = single must create one NAT gateway"
  }
}

run "a_nat_gateway_per_zone_is_one_for_each_zone" {
  command = apply
  module {
    source = "../../modules/vpc"
  }
  variables {
    public_subnet_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
    nat_gateway_mode    = "per_az"
  }
  assert {
    condition     = length(aws_nat_gateway.this) == 2
    error_message = "nat_gateway_mode = per_az must create a NAT gateway in each zone"
  }
}

run "a_nat_gateway_without_public_subnets_is_rejected" {
  command = plan
  module {
    source = "../../modules/vpc"
  }
  variables {
    nat_gateway_mode = "single"
  }
  expect_failures = [aws_vpc.this]
}

run "a_different_number_of_subnets_than_zones_is_rejected" {
  command = plan
  module {
    source = "../../modules/vpc"
  }
  variables {
    private_subnet_cidrs = ["10.0.10.0/24"]
  }
  expect_failures = [aws_vpc.this]
}

run "an_unknown_nat_mode_is_rejected" {
  command = plan
  module {
    source = "../../modules/vpc"
  }
  variables {
    nat_gateway_mode = "always"
  }
  expect_failures = [var.nat_gateway_mode]
}

run "a_single_zone_is_rejected" {
  command = plan
  module {
    source = "../../modules/vpc"
  }
  variables {
    availability_zones = ["us-east-1a"]
  }
  expect_failures = [var.availability_zones]
}

run "an_invalid_cidr_is_rejected" {
  command = plan
  module {
    source = "../../modules/vpc"
  }
  variables {
    cidr_block = "10.0.0.0"
  }
  expect_failures = [var.cidr_block]
}
