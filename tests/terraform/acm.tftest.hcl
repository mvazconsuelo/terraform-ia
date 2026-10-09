# modules/acm: a public certificate validated by DNS. With a zone it waits for the validation; without one it does not.

mock_provider "aws" {}

variables {
  name        = "test-cert"
  domain_name = "example.com"
  tags        = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "without_a_zone_it_does_not_wait_for_the_validation" {
  command = apply
  module {
    source = "../../modules/acm"
  }
  assert {
    condition     = length(aws_acm_certificate_validation.this) == 0
    error_message = "with no zone_id there is no validation resource"
  }
}

run "with_a_zone_it_waits_for_the_validation" {
  command = apply
  module {
    source = "../../modules/acm"
  }
  variables {
    zone_id = "Z0123456789ABC"
  }
  assert {
    condition     = length(aws_acm_certificate_validation.this) == 1
    error_message = "with a zone_id the module validates the certificate"
  }
}

run "a_wildcard_domain_is_accepted" {
  command = plan
  module {
    source = "../../modules/acm"
  }
  variables {
    domain_name               = "*.example.com"
    subject_alternative_names = ["example.com"]
  }
}

run "an_invalid_domain_is_rejected" {
  command = plan
  module {
    source = "../../modules/acm"
  }
  variables {
    domain_name = "not a domain"
  }
  expect_failures = [var.domain_name]
}

run "an_invalid_zone_id_is_rejected" {
  command = plan
  module {
    source = "../../modules/acm"
  }
  variables {
    zone_id = "not-a-zone"
  }
  expect_failures = [var.zone_id]
}
