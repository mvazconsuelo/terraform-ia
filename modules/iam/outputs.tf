output "role_arn" {
  description = "ARN of the IAM role."
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Name of the IAM role."
  value       = aws_iam_role.this.name
}

output "instance_profile_name" {
  description = "Instance profile name, or null when not created."
  value       = one(aws_iam_instance_profile.this[*].name)
}

output "instance_profile_arn" {
  description = "Instance profile ARN, or null when not created."
  value       = one(aws_iam_instance_profile.this[*].arn)
}
