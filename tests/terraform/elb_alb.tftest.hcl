# modules/elb/alb: the module picks its subnets and resolves the certificate of each listener.

# The mock invents values; the provider rejects an ARN that is not shaped like one, so these two get a valid one.
mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:111122223333:loadbalancer/app/test/0123456789abcdef" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:111122223333:targetgroup/test-web/0123456789abcdef" }
  }
}

variables {
  name               = "test-alb"
  vpc_id             = "vpc-1"
  public_subnet_ids  = ["subnet-pub-1", "subnet-pub-2"]
  private_subnet_ids = ["subnet-priv-1", "subnet-priv-2"]
  security_group_ids = ["sg-1"]
  tags               = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  target_groups      = { web = { port = 8080 } }
}

run "works_with_the_minimum_inputs_and_is_internal_without_listeners" {
  command = apply
  module {
    source = "../../modules/elb/alb"
  }
  assert {
    condition     = aws_lb.this.internal == true && length(aws_lb_listener.this) == 0
    error_message = "by default the balancer is internal and has no listener"
  }
}

run "an_internet_facing_balancer_uses_the_public_subnets" {
  command = apply
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal = false
  }
  assert {
    condition     = toset(aws_lb.this.subnets) == toset(["subnet-pub-1", "subnet-pub-2"])
    error_message = "internal = false must use public_subnet_ids"
  }
}

run "an_internal_balancer_uses_the_private_subnets" {
  command = apply
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal = true
  }
  assert {
    condition     = toset(aws_lb.this.subnets) == toset(["subnet-priv-1", "subnet-priv-2"])
    error_message = "internal = true must use private_subnet_ids"
  }
}

run "an_https_listener_uses_the_certificate_it_names" {
  command = apply
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal     = false
    certificates = { web = "arn:aws:acm:us-east-1:111122223333:certificate/web" }
    listeners = {
      https = { port = 443, protocol = "HTTPS", certificate = "web", default_action = { type = "forward", target_group = "web" } }
    }
  }
  assert {
    condition     = aws_lb_listener.this["https"].certificate_arn == "arn:aws:acm:us-east-1:111122223333:certificate/web"
    error_message = "the listener must use the ARN of the certificate it names"
  }
}

run "an_https_listener_without_a_certificate_is_rejected" {
  command = plan
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal = false
    listeners = {
      https = { port = 443, protocol = "HTTPS", default_action = { type = "forward", target_group = "web" } }
    }
  }
  expect_failures = [var.listeners]
}

run "a_listener_naming_an_unknown_certificate_is_rejected" {
  command = plan
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal     = false
    certificates = { web = "arn:aws:acm:us-east-1:111122223333:certificate/web" }
    listeners = {
      https = { port = 443, protocol = "HTTPS", certificate = "other", default_action = { type = "forward", target_group = "web" } }
    }
  }
  expect_failures = [var.listeners]
}

run "fewer_than_two_subnets_are_rejected" {
  command = plan
  module {
    source = "../../modules/elb/alb"
  }
  variables {
    internal          = false
    public_subnet_ids = ["subnet-pub-1"]
  }
  expect_failures = [var.private_subnet_ids]
}
