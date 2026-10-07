output "instance_ids" {
  description = "Instance IDs keyed by logical name."
  value       = { for k, i in aws_instance.this : k => i.id }
}

output "private_ips" {
  description = "Private IPs keyed by logical name."
  value       = { for k, i in aws_instance.this : k => i.private_ip }
}

output "availability_zones" {
  description = "Availability zones keyed by logical name."
  value       = { for k, i in aws_instance.this : k => i.availability_zone }
}

output "data_volume_ids" {
  description = "Data volume IDs keyed by `<instance>/<volume>`."
  value       = { for k, v in aws_ebs_volume.this : k => v.id }
}
