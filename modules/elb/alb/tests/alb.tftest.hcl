mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name               = "shop-dev"
  vpc_id             = "vpc-123"
  subnet_ids         = ["subnet-a", "subnet-b"]
  security_group_ids = ["sg-1"]
  target_groups = {
    web = { port = 8080 }
    api = { port = 9090 }
  }
  listeners = {
    http = { port = 80, protocol = "HTTP", default_action = { type = "redirect", redirect = {} } }
    https = {
      port            = 443
      certificate_arn = "arn:aws:acm:us-east-1:111122223333:certificate/abc"
      default_action  = { type = "forward", target_group = "web" }
    }
  }
  rules = {
    api = { listener = "https", priority = 10, target_group = "api", path_patterns = ["/api/*"] }
  }
}

run "internal_application_lb_by_default" {
  command = plan

  assert {
    condition = (
      aws_lb.this.internal &&
      aws_lb.this.load_balancer_type == "application" &&
      aws_lb.this.enable_deletion_protection &&
      aws_lb.this.drop_invalid_header_fields
    )
    error_message = "Defaults must be internal, application type, deletion-protected and drop invalid headers."
  }
}

run "listeners_rules_and_redirect" {
  command = plan

  assert {
    condition     = length(aws_lb_listener.this) == 2 && length(aws_lb_listener_rule.this) == 1 && length(aws_wafv2_web_acl_association.this) == 0
    error_message = "Two listeners, one rule and no WAF association expected."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_lb.this.tags), k) && contains(keys(aws_lb_target_group.this["web"].tags), k) && contains(keys(aws_lb_listener.this["https"].tags), k) && contains(keys(aws_lb_listener_rule.this["api"].tags), k)
    ])
    error_message = "LB, target groups, listeners and rules need mandatory tags."
  }
}

run "waf_association" {
  command = plan

  variables {
    web_acl_arn = "arn:aws:wafv2:us-east-1:111122223333:regional/webacl/x/1"
  }

  assert {
    condition     = length(aws_wafv2_web_acl_association.this) == 1
    error_message = "WAF association expected."
  }
}

run "https_requires_certificate" {
  command = plan

  variables {
    listeners = { https = { port = 443, default_action = { type = "forward", target_group = "web" } } }
    rules     = {}
  }

  expect_failures = [var.listeners]
}

run "forward_must_reference_known_target_group" {
  command = plan

  variables {
    listeners = { http = { port = 80, protocol = "HTTP", default_action = { type = "forward", target_group = "missing" } } }
    rules     = {}
  }

  expect_failures = [aws_lb.this]
}

run "rule_priorities_unique_per_listener" {
  command = plan

  variables {
    rules = {
      a = { listener = "https", priority = 10, target_group = "api", path_patterns = ["/a/*"] }
      b = { listener = "https", priority = 10, target_group = "web", path_patterns = ["/b/*"] }
    }
  }

  expect_failures = [aws_lb.this]
}

run "rule_needs_a_condition" {
  command = plan

  variables {
    rules = { bad = { listener = "https", priority = 5, target_group = "api" } }
  }

  expect_failures = [var.rules]
}

run "alb_requires_security_group" {
  command = plan

  variables {
    security_group_ids = []
  }

  expect_failures = [var.security_group_ids]
}
