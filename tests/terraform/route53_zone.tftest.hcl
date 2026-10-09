# modules/route53/zone: a hosted zone, public or private, that is not destroyed by accident.

mock_provider "aws" {}

variables {
  name = "example.com"
  tags = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_is_a_public_zone_that_is_protected" {
  command = apply
  module {
    source = "../../modules/route53/zone"
  }
  assert {
    condition     = aws_route53_zone.this.name == "example.com" && length(aws_route53_zone.this.vpc) == 0 && aws_route53_zone.this.force_destroy == false
    error_message = "by default the zone is public and cannot be destroyed with records in it"
  }
}

run "vpc_ids_make_the_zone_private" {
  command = apply
  module {
    source = "../../modules/route53/zone"
  }
  variables {
    vpc_ids = ["vpc-0123abcd"]
  }
  assert {
    condition     = length(aws_route53_zone.this.vpc) == 1
    error_message = "a zone with vpc_ids is private to those VPCs"
  }
}

run "an_invalid_domain_name_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/zone"
  }
  variables {
    name = "not a domain"
  }
  expect_failures = [var.name]
}

run "a_vpc_id_that_is_not_a_vpc_id_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/zone"
  }
  variables {
    vpc_ids = ["subnet-123"]
  }
  expect_failures = [var.vpc_ids]
}
