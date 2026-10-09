# modules/api-gateway: an HTTP API whose routes point at a Lambda function or, through a VPC Link, at an internal load balancer.

# The mock invents values; the provider rejects an ARN that is not shaped like one, so these two get a valid one.
mock_provider "aws" {
  mock_resource "aws_apigatewayv2_api" {
    defaults = { execution_arn = "arn:aws:execute-api:us-east-1:111122223333:abcdef1234" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:111122223333:log-group:/test" }
  }
}

variables {
  name = "test-api"
  tags = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  routes = {
    hello = {
      route_key            = "GET /hello"
      integration_type     = "lambda"
      lambda_function_name = "hello"
      lambda_invoke_arn    = "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:111122223333:function:hello/invocations"
    }
  }
}

run "works_with_the_minimum_inputs_and_needs_no_vpc_link" {
  command = apply
  module {
    source = "../../modules/api-gateway"
  }
  assert {
    condition     = length(aws_apigatewayv2_vpc_link.this) == 0 && length(aws_apigatewayv2_route.this) == 1 && length(aws_apigatewayv2_integration.this) == 1
    error_message = "a lambda-only API has a route, an integration and no VPC Link"
  }
}

run "a_lambda_route_lets_the_api_invoke_the_function" {
  command = apply
  module {
    source = "../../modules/api-gateway"
  }
  assert {
    condition     = length(aws_lambda_permission.this) == 1
    error_message = "each lambda route needs the invoke permission"
  }
}

run "the_stage_is_throttled_by_default" {
  command = apply
  module {
    source = "../../modules/api-gateway"
  }
  assert {
    condition     = aws_apigatewayv2_stage.this.default_route_settings[0].throttling_burst_limit == 100 && aws_apigatewayv2_stage.this.default_route_settings[0].throttling_rate_limit == 50
    error_message = "the default throttling is 100 burst and 50 per second"
  }
}

run "a_private_route_brings_the_vpc_link" {
  command = apply
  module {
    source = "../../modules/api-gateway"
  }
  variables {
    vpc_link = { subnet_ids = ["subnet-1", "subnet-2"], security_group_ids = ["sg-1"] }
    routes = {
      private = {
        route_key        = "ANY /private/{proxy+}"
        integration_type = "vpc_link"
        listener_arn     = "arn:aws:elasticloadbalancing:us-east-1:111122223333:listener/net/test/0123456789abcdef/0123456789abcdef"
      }
    }
  }
  assert {
    condition     = length(aws_apigatewayv2_vpc_link.this) == 1
    error_message = "a vpc_link route needs the VPC Link"
  }
}

run "a_private_route_without_the_vpc_link_is_rejected" {
  command = plan
  module {
    source = "../../modules/api-gateway"
  }
  variables {
    routes = {
      private = {
        route_key        = "ANY /private/{proxy+}"
        integration_type = "vpc_link"
        listener_arn     = "arn:aws:elasticloadbalancing:us-east-1:111122223333:listener/net/test/0123456789abcdef/0123456789abcdef"
      }
    }
  }
  expect_failures = [aws_apigatewayv2_api.this]
}

run "a_lambda_route_without_the_function_is_rejected" {
  command = plan
  module {
    source = "../../modules/api-gateway"
  }
  variables {
    routes = { broken = { route_key = "GET /x", integration_type = "lambda" } }
  }
  expect_failures = [var.routes]
}

run "an_unknown_integration_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/api-gateway"
  }
  variables {
    routes = { broken = { route_key = "GET /x", integration_type = "http" } }
  }
  expect_failures = [var.routes]
}

run "a_route_key_that_is_not_method_and_path_is_rejected" {
  command = plan
  module {
    source = "../../modules/api-gateway"
  }
  variables {
    routes = { broken = { route_key = "hello", integration_type = "lambda", lambda_function_name = "hello", lambda_invoke_arn = "arn:aws:apigateway:us-east-1:lambda:path/x" } }
  }
  expect_failures = [var.routes]
}
