output "function_name" {
  description = "Function name."
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "Function ARN."
  value       = aws_lambda_function.this.arn
}

output "invoke_arn" {
  description = "Invoke ARN, used by API Gateway integrations."
  value       = aws_lambda_function.this.invoke_arn
}

output "log_group_name" {
  description = "CloudWatch log group name."
  value       = aws_cloudwatch_log_group.this.name
}
