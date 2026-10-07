output "addon_arns" {
  description = "Add-on ARNs keyed by add-on name."
  value       = { for k, a in aws_eks_addon.this : k => a.arn }
}

output "addon_versions" {
  description = "Installed add-on versions keyed by add-on name."
  value       = { for k, a in aws_eks_addon.this : k => a.addon_version }
}
