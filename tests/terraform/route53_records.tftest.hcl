# modules/route53/records: records in an existing zone, either standard (values) or alias, never both.

mock_provider "aws" {}

variables {
  zone_id = "Z0123456789ABC"
}

run "works_with_the_minimum_inputs_and_creates_no_records" {
  command = apply
  module {
    source = "../../modules/route53/records"
  }
  assert {
    condition     = length(aws_route53_record.this) == 0
    error_message = "with no records given there is nothing to create"
  }
}

run "a_standard_record_has_a_ttl_of_300_by_default" {
  command = apply
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { www = { name = "www.example.com", type = "A", values = ["192.0.2.1"] } }
  }
  assert {
    condition     = length(aws_route53_record.this) == 1 && aws_route53_record.this["www"].ttl == 300
    error_message = "a standard record is created with a ttl of 300"
  }
}

run "an_alias_record_points_at_an_aws_resource" {
  command = apply
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { app = { name = "app.example.com", type = "A", alias = { name = "my-alb-123.us-east-1.elb.amazonaws.com", zone_id = "Z35SXDOTRQ7X7K" } } }
  }
  assert {
    condition     = length(aws_route53_record.this["app"].alias) == 1
    error_message = "an alias record has an alias block"
  }
}

run "a_record_with_values_and_alias_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { x = { name = "x.example.com", type = "A", values = ["192.0.2.1"], alias = { name = "a.example.com", zone_id = "Z35SXDOTRQ7X7K" } } }
  }
  expect_failures = [var.records]
}

run "a_record_with_neither_values_nor_alias_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { x = { name = "x.example.com", type = "A" } }
  }
  expect_failures = [var.records]
}

run "an_alias_that_is_not_type_a_or_aaaa_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { x = { name = "x.example.com", type = "CNAME", alias = { name = "a.example.com", zone_id = "Z35SXDOTRQ7X7K" } } }
  }
  expect_failures = [var.records]
}

run "an_unknown_record_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/records"
  }
  variables {
    records = { x = { name = "x.example.com", type = "PTR", values = ["a.example.com"] } }
  }
  expect_failures = [var.records]
}

run "an_invalid_zone_id_is_rejected" {
  command = plan
  module {
    source = "../../modules/route53/records"
  }
  variables {
    zone_id = "not-a-zone"
  }
  expect_failures = [var.zone_id]
}
