resource "aws_security_group" "this" {
  name_prefix = "${var.name}-"
  description = var.description
  vpc_id      = var.vpc_id

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    create_before_destroy = true

    precondition {
      condition     = var.allow_public_ingress || !contains([for r in values(var.ingress_rules) : r.cidr_ipv4], "0.0.0.0/0")
      error_message = "Ingress from 0.0.0.0/0 requires allow_public_ingress = true (internet-facing load balancers only)."
    }
  }
}

resource "aws_vpc_security_group_ingress_rule" "this" {
  for_each = var.ingress_rules

  security_group_id            = aws_security_group.this.id
  description                  = each.value.description
  ip_protocol                  = each.value.protocol
  from_port                    = each.value.protocol == "-1" ? null : each.value.from_port
  to_port                      = each.value.protocol == "-1" ? null : each.value.to_port
  cidr_ipv4                    = each.value.cidr_ipv4
  referenced_security_group_id = each.value.referenced_security_group_id
  prefix_list_id               = each.value.prefix_list_id

  tags = merge(local.tags, { Name = "${var.name}-in-${each.key}" })
}

resource "aws_vpc_security_group_egress_rule" "this" {
  for_each = var.egress_rules

  security_group_id            = aws_security_group.this.id
  description                  = each.value.description
  ip_protocol                  = each.value.protocol
  from_port                    = each.value.protocol == "-1" ? null : each.value.from_port
  to_port                      = each.value.protocol == "-1" ? null : each.value.to_port
  cidr_ipv4                    = each.value.cidr_ipv4
  referenced_security_group_id = each.value.referenced_security_group_id
  prefix_list_id               = each.value.prefix_list_id

  tags = merge(local.tags, { Name = "${var.name}-out-${each.key}" })
}

resource "aws_vpc_security_group_egress_rule" "allow_all" {
  count = var.allow_all_egress ? 1 : 0

  security_group_id = aws_security_group.this.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = merge(local.tags, { Name = "${var.name}-out-all" })
}
