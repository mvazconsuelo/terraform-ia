# modules/security-group: the module resolves the rules a project writes in its inputs.yaml.
# Each `run` block is one case: what is given, and what must come out.

mock_provider "aws" {}

# The inputs the module requires and nothing else: every case adds what it needs.
variables {
  name        = "test-app"
  description = "test"
  vpc_id      = "vpc-1"
  tags        = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_creates_no_rules" {
  command = apply
  module {
    source = "../../modules/security-group"
  }
  assert {
    condition     = length(output.ingress_rules) == 0 && length(output.egress_rules) == 0
    error_message = "with no rules given, the group must have no rules (no ingress and no egress by default)"
  }
}

run "port_sets_from_port_and_to_port" {
  command = apply
  module {
    source = "../../modules/security-group"
  }
  variables {
    egress_rules = { https = { description = "https", port = 443, cidr_ipv4 = "10.1.0.0/16" } }
  }
  assert {
    condition     = output.egress_rules.https.from_port == 443 && output.egress_rules.https.to_port == 443
    error_message = "port must set both from_port and to_port"
  }
}

run "vpc_becomes_the_vpc_cidr" {
  command = apply
  module {
    source = "../../modules/security-group"
  }
  variables {
    vpc_cidr_block = "10.0.0.0/16"
    egress_rules   = { to_db = { description = "db", port = 5432, cidr_ipv4 = "vpc" } }
  }
  assert {
    condition     = output.egress_rules.to_db.cidr_ipv4 == "10.0.0.0/16"
    error_message = "cidr_ipv4 = vpc must become vpc_cidr_block"
  }
}

run "source_sg_becomes_the_group_id" {
  command = apply
  module {
    source = "../../modules/security-group"
  }
  variables {
    source_security_groups = { alb = "sg-alb" }
    ingress_rules          = { from_alb = { description = "alb", port = 8080, source_sg = "alb" } }
  }
  assert {
    condition     = output.ingress_rules.from_alb.referenced_security_group_id == "sg-alb"
    error_message = "source_sg must become the id in source_security_groups"
  }
}

run "an_unknown_source_sg_is_rejected" {
  command = plan
  module {
    source = "../../modules/security-group"
  }
  variables {
    ingress_rules = { x = { description = "x", port = 1, source_sg = "nope" } }
  }
  expect_failures = [var.ingress_rules]
}

run "a_rule_with_two_sources_is_rejected" {
  command = plan
  module {
    source = "../../modules/security-group"
  }
  variables {
    ingress_rules = { x = { description = "x", port = 1, cidr_ipv4 = "10.0.0.0/8", prefix_list_id = "pl-1" } }
  }
  expect_failures = [var.ingress_rules]
}

run "open_to_the_internet_needs_the_explicit_switch" {
  command = plan
  module {
    source = "../../modules/security-group"
  }
  variables {
    ingress_rules = { web = { description = "web", port = 443, cidr_ipv4 = "0.0.0.0/0" } }
  }
  expect_failures = [aws_security_group.this]
}
