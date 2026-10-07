output "launch_template_id" {
  description = "ID of the launch template."
  value       = aws_launch_template.this.id
}

output "launch_template_arn" {
  description = "ARN of the launch template."
  value       = aws_launch_template.this.arn
}

output "latest_version" {
  description = "Latest template version number. Pass to ec2/asg so a template change triggers an instance refresh."
  value       = aws_launch_template.this.latest_version
}

output "default_version" {
  description = "Default template version number (what `$Default` resolves to)."
  value       = aws_launch_template.this.default_version
}
