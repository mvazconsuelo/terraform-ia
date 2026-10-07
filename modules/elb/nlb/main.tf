resource "aws_lb" "this" {
  name                             = var.name
  load_balancer_type               = "network"
  internal                         = var.internal
  subnets                          = var.subnet_ids
  security_groups                  = var.security_group_ids
  enable_deletion_protection       = var.enable_deletion_protection
  enable_cross_zone_load_balancing = var.enable_cross_zone_load_balancing

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition     = alltrue([for l in values(var.listeners) : contains(keys(var.target_groups), l.target_group)])
      error_message = "Every listener.target_group must be a key of target_groups."
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
    protocol = each.value.health_check_protocol
    port     = each.value.health_check_port
    path     = each.value.health_check_protocol == "TCP" ? null : each.value.health_check_path
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
  ssl_policy        = each.value.protocol == "TLS" ? each.value.ssl_policy : null

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.value.target_group].arn
  }

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}
