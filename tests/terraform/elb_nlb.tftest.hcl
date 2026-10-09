# modules/elb/nlb: a Network Load Balancer with target groups and listeners that forward to them.

mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:111122223333:loadbalancer/net/test/0123456789abcdef" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:111122223333:targetgroup/test-web/0123456789abcdef" }
  }
}

variables {
  name          = "test-nlb"
  vpc_id        = "vpc-1"
  subnet_ids    = ["subnet-1", "subnet-2"]
  tags          = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  target_groups = { web = { port = 8080 } }
}

run "works_with_the_minimum_inputs_and_is_internal_and_protected" {
  command = apply
  module {
    source = "../../modules/elb/nlb"
  }
  assert {
    condition     = aws_lb.this.internal == true && aws_lb.this.enable_deletion_protection == true && aws_lb.this.load_balancer_type == "network"
    error_message = "by default the balancer is a network one, internal and protected from deletion"
  }
}

run "a_listener_forwards_to_its_target_group" {
  command = apply
  module {
    source = "../../modules/elb/nlb"
  }
  variables {
    listeners = { tcp = { port = 80, target_group = "web" } }
  }
  assert {
    condition     = length(aws_lb_listener.this) == 1 && aws_lb_listener.this["tcp"].protocol == "TCP"
    error_message = "a listener is TCP unless told otherwise"
  }
}

run "a_listener_to_an_unknown_target_group_is_rejected" {
  command = plan
  module {
    source = "../../modules/elb/nlb"
  }
  variables {
    listeners = { tcp = { port = 80, target_group = "missing" } }
  }
  expect_failures = [aws_lb.this]
}

run "a_tls_listener_without_a_certificate_is_rejected" {
  command = plan
  module {
    source = "../../modules/elb/nlb"
  }
  variables {
    listeners = { tls = { port = 443, protocol = "TLS", target_group = "web" } }
  }
  expect_failures = [var.listeners]
}

run "fewer_than_two_subnets_are_rejected" {
  command = plan
  module {
    source = "../../modules/elb/nlb"
  }
  variables {
    subnet_ids = ["subnet-1"]
  }
  expect_failures = [var.subnet_ids]
}

run "an_unknown_target_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/elb/nlb"
  }
  variables {
    target_groups = { web = { port = 8080, target_type = "magic" } }
  }
  expect_failures = [var.target_groups]
}
