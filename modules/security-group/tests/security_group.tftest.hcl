mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name        = "app"
  description = "App tier"
  vpc_id      = "vpc-123"
}

run "least_privilege_defaults" {
  command = plan

  assert {
    condition     = length(aws_vpc_security_group_egress_rule.allow_all) == 0 && length(aws_vpc_security_group_ingress_rule.this) == 0
    error_message = "No rules by default, including no allow-all egress."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_security_group.this.tags), k)
    ])
    error_message = "Security group is missing mandatory tags."
  }
}

run "sg_to_sg_rule" {
  command = plan

  variables {
    ingress_rules = {
      from_nlb = { description = "From NLB", from_port = 8080, to_port = 8080, referenced_security_group_id = "sg-abc" }
    }
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.this["from_nlb"].from_port == 8080
    error_message = "Rule not created."
  }
}

run "public_ingress_blocked_by_default" {
  command = plan

  variables {
    ingress_rules = {
      web = { description = "HTTPS", from_port = 443, to_port = 443, cidr_ipv4 = "0.0.0.0/0" }
    }
  }

  expect_failures = [aws_security_group.this]
}

run "public_ingress_when_explicit" {
  command = plan

  variables {
    allow_public_ingress = true
    ingress_rules = {
      web = { description = "HTTPS", from_port = 443, to_port = 443, cidr_ipv4 = "0.0.0.0/0" }
    }
  }

  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.this) == 1
    error_message = "Explicit public ingress should be allowed."
  }
}

run "rule_requires_single_source" {
  command = plan

  variables {
    ingress_rules = {
      bad = { description = "x", from_port = 1, to_port = 1, cidr_ipv4 = "10.0.0.0/8", referenced_security_group_id = "sg-1" }
    }
  }

  expect_failures = [var.ingress_rules]
}
