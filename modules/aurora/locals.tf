locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  engines = {
    postgresql = {
      engine   = "aurora-postgresql"
      port     = 5432
      username = "postgres"
      logs     = ["postgresql"]
    }
    mysql = {
      engine   = "aurora-mysql"
      port     = 3306
      username = "admin"
      logs     = ["audit", "error", "general", "slowquery"]
    }
  }

  spec = local.engines[var.engine]

  version_parts = split(".", var.engine_version)
  major_version = var.engine == "postgresql" ? local.version_parts[0] : "${local.version_parts[0]}.${local.version_parts[1]}"
  family        = coalesce(var.parameter_group_family, "${local.spec.engine}${local.major_version}")

  port            = coalesce(var.port, local.spec.port)
  master_username = coalesce(var.master_username, local.spec.username)
  log_exports     = coalesce(var.enabled_cloudwatch_logs_exports, local.spec.logs)

  instances = {
    for k, i in var.instances : k => {
      instance_class               = var.serverless_v2 != null ? "db.serverless" : coalesce(i.instance_class, var.instance_class)
      promotion_tier               = i.promotion_tier
      performance_insights_enabled = coalesce(i.performance_insights_enabled, var.performance_insights_enabled)
    }
  }
}
