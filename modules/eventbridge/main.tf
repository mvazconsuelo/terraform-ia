resource "aws_cloudwatch_event_bus" "this" {
  count = var.create_bus ? 1 : 0

  name = var.name

  tags = merge(local.tags, { Name = var.name })
}

resource "aws_cloudwatch_event_rule" "this" {
  for_each = var.rules

  name                = "${var.name}-${each.key}"
  description         = each.value.description
  event_bus_name      = local.bus_name
  schedule_expression = each.value.schedule_expression
  event_pattern       = each.value.event_pattern
  state               = each.value.enabled ? "ENABLED" : "DISABLED"

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    precondition {
      condition     = each.value.schedule_expression == null || !var.create_bus
      error_message = "Schedule rules are only supported on the default event bus; set create_bus = false."
    }
  }

  depends_on = [aws_cloudwatch_event_bus.this]
}

resource "aws_cloudwatch_event_target" "this" {
  for_each = local.targets

  rule           = aws_cloudwatch_event_rule.this[each.value.rule].name
  event_bus_name = local.bus_name
  target_id      = each.value.target
  arn            = each.value.arn
  role_arn       = each.value.role_arn
  input          = each.value.input

  retry_policy {
    maximum_retry_attempts       = each.value.retry_attempts
    maximum_event_age_in_seconds = each.value.max_event_age_seconds
  }

  dynamic "dead_letter_config" {
    for_each = each.value.dead_letter_arn == null ? [] : [each.value.dead_letter_arn]

    content {
      arn = dead_letter_config.value
    }
  }
}

resource "aws_lambda_permission" "this" {
  for_each = { for k, t in local.targets : k => t if t.lambda_function_name != null }

  statement_id  = "AllowEventBridge-${replace(each.key, "/", "-")}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this[each.value.rule].arn
}
