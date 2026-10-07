mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name       = "demo-dev"
  vpc_id     = "vpc-123"
  subnet_ids = ["subnet-a", "subnet-b"]
  target_groups = {
    app = { port = 8080 }
  }
  listeners = {
    http = { port = 80, target_group = "app" }
  }
}

run "internal_network_lb_by_default" {
  command = plan

  assert {
    condition     = aws_lb.this.internal && aws_lb.this.load_balancer_type == "network" && aws_lb.this.enable_deletion_protection
    error_message = "Defaults must be internal, network type and deletion-protected."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_lb.this.tags), k) && contains(keys(aws_lb_target_group.this["app"].tags), k)
    ])
    error_message = "LB and target groups need mandatory tags."
  }
}

run "listener_must_reference_known_target_group" {
  command = plan

  variables {
    listeners = { http = { port = 80, target_group = "missing" } }
  }

  expect_failures = [aws_lb.this]
}

run "tls_listener_requires_certificate" {
  command = plan

  variables {
    listeners = { tls = { port = 443, protocol = "TLS", target_group = "app" } }
  }

  expect_failures = [var.listeners]
}

run "rejects_single_subnet" {
  command = plan

  variables {
    subnet_ids = ["subnet-a"]
  }

  expect_failures = [var.subnet_ids]
}
