output "bus_name" {
  description = "Event bus name (`default` when create_bus is false)."
  value       = local.bus_name
}

output "bus_arn" {
  description = "Custom event bus ARN, or null when using the default bus."
  value       = one(aws_cloudwatch_event_bus.this[*].arn)
}

output "rule_arns" {
  description = "Rule ARNs keyed by logical name."
  value       = { for k, r in aws_cloudwatch_event_rule.this : k => r.arn }
}
