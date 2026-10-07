# Outputs
output "vpc_id" {
  description = "ID of the VPC."
  value       = module.vpc.vpc_id
}

output "alb_dns_name" {
  description = "DNS name of the load balancer."
  value       = module.alb.dns_name
}

output "database_endpoint" {
  description = "Aurora writer endpoint."
  value       = module.database.endpoint
}

output "database_reader_endpoint" {
  description = "Aurora reader endpoint."
  value       = module.database.reader_endpoint
}

output "database_secret_arn" {
  description = "Secrets Manager ARN with the generated master credentials."
  value       = module.database.master_user_secret_arn
}

output "autoscaling_group_name" {
  description = "Name of the web tier Auto Scaling Group."
  value       = module.web_asg.autoscaling_group_name
}

output "summary" {
  description = "Environment summary derived from the YAML."
  value = {
    name           = local.name
    environment    = local.tags.environment
    nat_mode       = local.nat_gateway_mode
    alb_internal   = local.inputs.alb.internal
    https_enabled  = local.has_https
    db_engine      = local.db_engine
    db_instances   = length(local.inputs.database.instances)
    db_deletion_on = local.inputs.database.deletion_protection
    web_min_size   = local.inputs.compute.min_size
    web_max_size   = local.inputs.compute.max_size
  }
}
