resource "aws_lb" "this" {
  name                       = var.name
  load_balancer_type         = "application"
  internal                   = var.internal
  subnets                    = var.subnet_ids
  security_groups            = var.security_group_ids
  enable_deletion_protection = var.enable_deletion_protection
  idle_timeout               = var.idle_timeout
  drop_invalid_header_fields = true

  dynamic "access_logs" {
    for_each = var.access_logs_bucket == null ? [] : [var.access_logs_bucket]

    content {
      bucket  = access_logs.value
      enabled = true
    }
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition = alltrue(concat(
        [for l in values(var.listeners) : l.default_action.type != "forward" || contains(keys(var.target_groups), l.default_action.target_group)],
        [for r in values(var.rules) : contains(keys(var.target_groups), r.target_group) && contains(keys(var.listeners), r.listener)]
      ))
      error_message = "Every forward target_group must be a key of target_groups and every rule.listener a key of listeners."
    }

    precondition {
      condition     = length(distinct([for r in values(var.rules) : "${r.listener}/${r.priority}"])) == length(var.rules)
      error_message = "Rule priorities must be unique per listener."
    }
  }
}

resource "aws_lb_target_group" "this" {
  for_each = var.target_groups

  name                 = "${var.name}-${each.key}"
  port                 = each.value.port
  protocol             = each.value.protocol
  target_type          = each.value.target_type
  vpc_id               = var.vpc_id
  deregistration_delay = each.value.deregistration_delay

  health_check {
    path                = each.value.health_check.path
    matcher             = each.value.health_check.matcher
    interval            = each.value.health_check.interval
    healthy_threshold   = each.value.health_check.healthy_threshold
    unhealthy_threshold = each.value.health_check.unhealthy_threshold
  }

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    precondition {
      condition     = length("${var.name}-${each.key}") <= 32
      error_message = "Target group name `<name>-<key>` must be 32 characters or fewer."
    }
  }
}

resource "aws_lb_listener" "this" {
  for_each = var.listeners

  load_balancer_arn = aws_lb.this.arn
  port              = each.value.port
  protocol          = each.value.protocol
  certificate_arn   = each.value.certificate_arn
  ssl_policy        = each.value.protocol == "HTTPS" ? each.value.ssl_policy : null

  default_action {
    type             = each.value.default_action.type
    target_group_arn = each.value.default_action.type == "forward" ? aws_lb_target_group.this[each.value.default_action.target_group].arn : null

    dynamic "redirect" {
      for_each = each.value.default_action.redirect == null ? [] : [each.value.default_action.redirect]

      content {
        port        = redirect.value.port
        protocol    = redirect.value.protocol
        status_code = redirect.value.status_code
      }
    }

    dynamic "fixed_response" {
      for_each = each.value.default_action.fixed_response == null ? [] : [each.value.default_action.fixed_response]

      content {
        status_code  = fixed_response.value.status_code
        content_type = fixed_response.value.content_type
        message_body = fixed_response.value.message_body
      }
    }
  }

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}

resource "aws_lb_listener_rule" "this" {
  for_each = var.rules

  listener_arn = aws_lb_listener.this[each.value.listener].arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.value.target_group].arn
  }

  dynamic "condition" {
    for_each = length(each.value.path_patterns) > 0 ? [each.value.path_patterns] : []

    content {
      path_pattern {
        values = condition.value
      }
    }
  }

  dynamic "condition" {
    for_each = length(each.value.host_headers) > 0 ? [each.value.host_headers] : []

    content {
      host_header {
        values = condition.value
      }
    }
  }

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}

resource "aws_wafv2_web_acl_association" "this" {
  count = var.web_acl_arn == null ? 0 : 1

  resource_arn = aws_lb.this.arn
  web_acl_arn  = var.web_acl_arn
}
