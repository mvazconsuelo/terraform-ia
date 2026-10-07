resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(local.tags, { Name = "${var.function_name}-logs" })
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = var.role_arn
  handler       = var.handler
  runtime       = var.runtime
  architectures = var.architectures
  memory_size   = var.memory_size
  timeout       = var.timeout
  layers        = var.layers

  filename         = var.filename
  source_code_hash = var.source_code_hash
  s3_bucket        = var.s3_bucket
  s3_key           = var.s3_key

  reserved_concurrent_executions = var.reserved_concurrent_executions

  tracing_config {
    mode = var.tracing_mode
  }

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [var.environment_variables] : []

    content {
      variables = environment.value
    }
  }

  dynamic "vpc_config" {
    for_each = var.vpc_config == null ? [] : [var.vpc_config]

    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  dynamic "dead_letter_config" {
    for_each = var.dead_letter_target_arn == null ? [] : [var.dead_letter_target_arn]

    content {
      target_arn = dead_letter_config.value
    }
  }

  tags = merge(local.tags, { Name = var.function_name })

  # The log group must exist first so the function cannot create an untagged, never-expiring one.
  depends_on = [aws_cloudwatch_log_group.this]

  lifecycle {
    precondition {
      condition     = (var.filename != null) != (var.s3_bucket != null && var.s3_key != null)
      error_message = "Provide either filename or both s3_bucket and s3_key (not both, not neither)."
    }
  }
}
