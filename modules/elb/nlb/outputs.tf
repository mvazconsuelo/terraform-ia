output "lb_arn" {
  description = "ARN of the network load balancer."
  value       = aws_lb.this.arn
}

output "lb_arn_suffix" {
  description = "ARN suffix for CloudWatch metrics."
  value       = aws_lb.this.arn_suffix
}

output "dns_name" {
  description = "DNS name of the load balancer."
  value       = aws_lb.this.dns_name
}

output "zone_id" {
  description = "Route 53 zone ID of the load balancer."
  value       = aws_lb.this.zone_id
}

output "listener_arns" {
  description = "Listener ARNs keyed by logical name. API Gateway VPC Link integrations target a listener ARN."
  value       = { for k, l in aws_lb_listener.this : k => l.arn }
}

output "target_group_arns" {
  description = "Target group ARNs keyed by logical name (register EKS/ASG targets against these)."
  value       = { for k, t in aws_lb_target_group.this : k => t.arn }
}
