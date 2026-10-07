output "security_group_id" {
  description = "ID of the security group."
  value       = aws_security_group.this.id
}

output "security_group_arn" {
  description = "ARN of the security group."
  value       = aws_security_group.this.arn
}

output "ingress_rules" {
  description = "Resolved ingress rules keyed by rule name (protocol, ports and source), for auditing and tests."
  value = {
    for k, r in aws_vpc_security_group_ingress_rule.this : k => {
      protocol                     = r.ip_protocol
      from_port                    = r.from_port
      to_port                      = r.to_port
      cidr_ipv4                    = r.cidr_ipv4
      referenced_security_group_id = r.referenced_security_group_id
    }
  }
}

output "egress_rules" {
  description = "Resolved egress rules keyed by rule name (protocol, ports and destination)."
  value = {
    for k, r in aws_vpc_security_group_egress_rule.this : k => {
      protocol                     = r.ip_protocol
      from_port                    = r.from_port
      to_port                      = r.to_port
      cidr_ipv4                    = r.cidr_ipv4
      referenced_security_group_id = r.referenced_security_group_id
    }
  }
}
