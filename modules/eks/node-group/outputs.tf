output "node_group_arns" {
  description = "Node group ARNs keyed by logical group name."
  value       = { for k, g in aws_eks_node_group.this : k => g.arn }
}

output "node_group_names" {
  description = "Physical node group names keyed by logical group name."
  value       = { for k, g in aws_eks_node_group.this : k => g.node_group_name }
}

output "node_group_status" {
  description = "Node group status keyed by logical group name."
  value       = { for k, g in aws_eks_node_group.this : k => g.status }
}
