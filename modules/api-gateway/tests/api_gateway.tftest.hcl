mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name = "shop-dev"
  vpc_link = {
    subnet_ids         = ["subnet-a", "subnet-b"]
    security_group_ids = ["sg-1"]
  }
  routes = {
    orders = { route_key = "ANY /orders/{proxy+}", integration_type = "vpc_link", listener_arn = "arn:aws:elasticloadbalancing:us-east-1:111122223333:listener/net/x/1/2" }
    hello  = { route_key = "GET /hello", integration_type = "lambda", lambda_function_name = "hello", lambda_invoke_arn = "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:111122223333:function:hello/invocations" }
  }
}

run "private_integration_uses_vpc_link" {
  command = plan

  assert {
    condition     = aws_apigatewayv2_integration.this["orders"].connection_type == "VPC_LINK" && aws_apigatewayv2_integration.this["orders"].integration_type == "HTTP_PROXY"
    error_message = "Private routes must use a VPC_LINK HTTP_PROXY integration."
  }

  assert {
    condition     = aws_apigatewayv2_integration.this["hello"].connection_type == "INTERNET" && length(aws_lambda_permission.this) == 1
    error_message = "Lambda route should be an internet AWS_PROXY integration with one invoke permission."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_apigatewayv2_api.this.tags), k) && contains(keys(aws_apigatewayv2_stage.this.tags), k) && contains(keys(aws_cloudwatch_log_group.access.tags), k)
    ])
    error_message = "API, stage and log group need mandatory tags."
  }
}

run "vpc_link_route_requires_vpc_link" {
  command = plan

  variables {
    vpc_link = null
  }

  expect_failures = [aws_apigatewayv2_api.this]
}

run "lambda_route_requires_arns" {
  command = plan

  variables {
    routes = { bad = { route_key = "GET /x", integration_type = "lambda" } }
  }

  expect_failures = [var.routes]
}

run "rejects_unknown_integration" {
  command = plan

  variables {
    routes = { bad = { route_key = "GET /x", integration_type = "http" } }
  }

  expect_failures = [var.routes]
}
