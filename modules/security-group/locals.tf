locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)
}

locals {
  # The rules as AWS takes them: `port` becomes from_port and to_port, cidr_ipv4 = "vpc" becomes the VPC CIDR and source_sg becomes the group ID.
  ingress_rules = {
    for k, r in var.ingress_rules : k => {
      description                  = r.description
      protocol                     = r.protocol
      from_port                    = r.port != null ? r.port : r.from_port
      to_port                      = r.port != null ? r.port : r.to_port
      cidr_ipv4                    = r.cidr_ipv4 == "vpc" ? var.vpc_cidr_block : r.cidr_ipv4
      referenced_security_group_id = r.source_sg != null ? var.source_security_groups[r.source_sg] : r.referenced_security_group_id
      prefix_list_id               = r.prefix_list_id
    }
  }

  egress_rules = {
    for k, r in var.egress_rules : k => {
      description                  = r.description
      protocol                     = r.protocol
      from_port                    = r.port != null ? r.port : r.from_port
      to_port                      = r.port != null ? r.port : r.to_port
      cidr_ipv4                    = r.cidr_ipv4 == "vpc" ? var.vpc_cidr_block : r.cidr_ipv4
      referenced_security_group_id = r.source_sg != null ? var.source_security_groups[r.source_sg] : r.referenced_security_group_id
      prefix_list_id               = r.prefix_list_id
    }
  }
}
