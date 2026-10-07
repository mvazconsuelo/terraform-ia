output "cluster_id" {
  description = "Cluster identifier."
  value       = aws_rds_cluster.this.id
}

output "cluster_arn" {
  description = "Cluster ARN."
  value       = aws_rds_cluster.this.arn
}

output "engine" {
  description = "Aurora engine name (`aurora-postgresql` or `aurora-mysql`)."
  value       = aws_rds_cluster.this.engine
}

output "endpoint" {
  description = "Writer endpoint."
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "Load-balanced reader endpoint."
  value       = aws_rds_cluster.this.reader_endpoint
}

output "port" {
  description = "Database port."
  value       = aws_rds_cluster.this.port
}

output "instance_endpoints" {
  description = "Per-instance endpoints keyed by logical instance name."
  value       = { for k, i in aws_rds_cluster_instance.this : k => i.endpoint }
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the generated master credentials (the secret value is not exposed)."
  value       = try(aws_rds_cluster.this.master_user_secret[0].secret_arn, null)
}

output "parameter_group_family" {
  description = "Parameter group family used for custom parameter groups."
  value       = local.family
}
