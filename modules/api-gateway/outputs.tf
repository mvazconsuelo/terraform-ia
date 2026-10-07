output "api_id" {
  description = "ID of the HTTP API."
  value       = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "Default endpoint URL of the API."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "execution_arn" {
  description = "Execution ARN, for IAM/Lambda permissions."
  value       = aws_apigatewayv2_api.this.execution_arn
}

output "stage_invoke_url" {
  description = "Invoke URL of the stage."
  value       = aws_apigatewayv2_stage.this.invoke_url
}

output "vpc_link_id" {
  description = "VPC Link V2 ID, or null when no VPC Link is configured."
  value       = one(aws_apigatewayv2_vpc_link.this[*].id)
}
