resource "aws_apigatewayv2_api" "this" {
  name          = var.name
  description   = var.description
  protocol_type = "HTTP"

  dynamic "cors_configuration" {
    for_each = var.cors == null ? [] : [var.cors]

    content {
      allow_origins = cors_configuration.value.allow_origins
      allow_methods = cors_configuration.value.allow_methods
      allow_headers = cors_configuration.value.allow_headers
      max_age       = cors_configuration.value.max_age
    }
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition     = length(local.vpc_link_routes) == 0 || var.vpc_link != null
      error_message = "Routes with integration_type `vpc_link` require the vpc_link input."
    }
  }
}

# VPC Link V2: carries API Gateway -> private NLB/ALB traffic. Not a VPC endpoint.
resource "aws_apigatewayv2_vpc_link" "this" {
  count = var.vpc_link == null ? 0 : 1

  name               = var.name
  subnet_ids         = var.vpc_link.subnet_ids
  security_group_ids = var.vpc_link.security_group_ids

  tags = merge(local.tags, { Name = var.name })
}

resource "aws_apigatewayv2_integration" "this" {
  for_each = var.routes

  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = each.value.integration_type == "lambda" ? "AWS_PROXY" : "HTTP_PROXY"
  integration_uri        = each.value.integration_type == "lambda" ? each.value.lambda_invoke_arn : each.value.listener_arn
  integration_method     = each.value.integration_type == "lambda" ? "POST" : "ANY"
  payload_format_version = each.value.integration_type == "lambda" ? "2.0" : "1.0"
  connection_type        = each.value.integration_type == "lambda" ? "INTERNET" : "VPC_LINK"
  connection_id          = each.value.integration_type == "lambda" ? null : one(aws_apigatewayv2_vpc_link.this[*].id)
  timeout_milliseconds   = each.value.timeout_ms
}

resource "aws_apigatewayv2_route" "this" {
  for_each = var.routes

  api_id    = aws_apigatewayv2_api.this.id
  route_key = each.value.route_key
  target    = "integrations/${aws_apigatewayv2_integration.this[each.key].id}"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.name}"
  retention_in_days = var.access_log_retention_days

  tags = merge(local.tags, { Name = "${var.name}-access" })
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = var.stage_name
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = var.throttling_burst_limit
    throttling_rate_limit  = var.throttling_rate_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      requestTime      = "$context.requestTime"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      integrationError = "$context.integrationErrorMessage"
      responseLatency  = "$context.responseLatency"
    })
  }

  tags = merge(local.tags, { Name = "${var.name}-${var.stage_name}" })
}

resource "aws_lambda_permission" "this" {
  for_each = local.lambda_routes

  statement_id  = "AllowAPIGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
