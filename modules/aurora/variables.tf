variable "name" {
  description = "Cluster identifier prefix, e.g. `payments-dev`."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}[a-z0-9]$", var.name))
    error_message = "name must be lowercase alphanumerics and hyphens, starting with a letter."
  }
}

variable "engine" {
  description = "Database engine: `postgresql` (aurora-postgresql) or `mysql` (aurora-mysql). Immutable: changing it replaces the cluster."
  type        = string

  validation {
    condition     = contains(["postgresql", "mysql"], var.engine)
    error_message = "engine must be `postgresql` or `mysql`."
  }
}

variable "tags" {
  description = "Mandatory tags (environment, owner, cost_center, project) applied to every taggable resource. See docs/module-standard.md."
  type = object({
    environment = string
    owner       = string
    cost_center = string
    project     = string
  })

  validation {
    condition     = contains(["dev", "staging", "prod"], var.tags.environment)
    error_message = "tags.environment must be one of: dev, staging, prod."
  }

  validation {
    condition     = alltrue([for v in values(var.tags) : length(trimspace(v)) > 0])
    error_message = "All mandatory tag values must be non-empty."
  }
}

variable "extra_tags" {
  description = "Extra tags merged with the mandatory tags; the mandatory tags win on key conflicts."
  type        = map(string)
  default     = {}
}

variable "engine_version" {
  description = "Engine version. PostgreSQL: `16.4`. MySQL: `8.0.mysql_aurora.3.05.2`. No default: pick a currently supported version (`aws rds describe-db-engine-versions --engine aurora-<engine>`)."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+(\\.mysql_aurora\\.[0-9]+\\.[0-9]+\\.[0-9]+)?$", var.engine_version))
    error_message = "engine_version must look like `16.4` (postgresql) or `8.0.mysql_aurora.3.05.2` (mysql)."
  }
}

variable "subnet_ids" {
  description = "Private subnet IDs for the DB subnet group."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Aurora needs subnets in at least 2 availability zones."
  }
}

variable "security_group_ids" {
  description = "Security groups attached to the cluster (create with modules/security-group)."
  type        = list(string)
}

variable "port" {
  description = "Listener port. Null uses the engine default (5432 postgresql, 3306 mysql)."
  type        = number
  default     = null

  validation {
    condition     = var.port == null ? true : (var.port >= 1150 && var.port <= 65535)
    error_message = "port must be between 1150 and 65535."
  }
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = null
}

variable "master_username" {
  description = "Master username. Null uses the engine default (`postgres` / `admin`). The password is generated and managed in Secrets Manager (never in state outputs or variables)."
  type        = string
  default     = null
}

variable "instances" {
  description = "Cluster instances keyed by a stable logical name. Aurora elects the writer by `promotion_tier` (lowest wins); the rest are readers. Per-instance overrides fall back to the module-level values."
  type = map(object({
    instance_class               = optional(string)
    promotion_tier               = optional(number, 1)
    performance_insights_enabled = optional(bool)
  }))
  default = {
    "1" = { promotion_tier = 0 }
    "2" = { promotion_tier = 1 }
  }

  validation {
    condition     = length(var.instances) >= 1 && length(var.instances) <= 15
    error_message = "Provide between 1 and 15 instances."
  }

  validation {
    condition     = alltrue([for i in values(var.instances) : i.promotion_tier >= 0 && i.promotion_tier <= 15])
    error_message = "promotion_tier must be 0-15."
  }

  validation {
    condition     = alltrue([for i in values(var.instances) : i.instance_class == null ? true : can(regex("^db\\.", i.instance_class))])
    error_message = "instance_class must start with `db.`."
  }
}

variable "instance_class" {
  description = "Default instance class, e.g. `db.r6g.large`. Ignored when serverless_v2 is set."
  type        = string
  default     = "db.t4g.medium"

  validation {
    condition     = can(regex("^db\\.", var.instance_class))
    error_message = "instance_class must start with `db.`."
  }
}

variable "serverless_v2" {
  description = "Aurora Serverless v2 capacity in ACUs. When set, all instances use `db.serverless`."
  type = object({
    min_capacity = number
    max_capacity = number
  })
  default = null

  validation {
    condition     = var.serverless_v2 == null ? true : (var.serverless_v2.min_capacity >= 0 && var.serverless_v2.min_capacity <= var.serverless_v2.max_capacity)
    error_message = "serverless_v2 requires 0 <= min_capacity <= max_capacity."
  }
}

variable "cluster_parameters" {
  description = "Cluster-level parameters (e.g. `rds.force_ssl`, `log_statement`, `character_set_server`). Creates a dedicated cluster parameter group."
  type = map(object({
    value        = string
    apply_method = optional(string, "immediate")
  }))
  default = {}

  validation {
    condition     = alltrue([for p in values(var.cluster_parameters) : contains(["immediate", "pending-reboot"], p.apply_method)])
    error_message = "apply_method must be `immediate` or `pending-reboot`."
  }
}

variable "instance_parameters" {
  description = "Instance-level parameters (e.g. `shared_preload_libraries`, `slow_query_log`). Creates a dedicated DB parameter group."
  type = map(object({
    value        = string
    apply_method = optional(string, "immediate")
  }))
  default = {}

  validation {
    condition     = alltrue([for p in values(var.instance_parameters) : contains(["immediate", "pending-reboot"], p.apply_method)])
    error_message = "apply_method must be `immediate` or `pending-reboot`."
  }
}

variable "parameter_group_family" {
  description = "Parameter group family override, e.g. `aurora-postgresql16`. Null derives it from engine and engine_version."
  type        = string
  default     = null
}

variable "enabled_cloudwatch_logs_exports" {
  description = "Log types exported to CloudWatch. Null uses engine defaults (postgresql: [postgresql]; mysql: [audit, error, general, slowquery])."
  type        = list(string)
  default     = null
}

variable "storage_type" {
  description = "`aurora` (standard) or `aurora-iopt1` (I/O-Optimized, better for I/O-heavy workloads)."
  type        = string
  default     = "aurora"

  validation {
    condition     = contains(["aurora", "aurora-iopt1"], var.storage_type)
    error_message = "storage_type must be `aurora` or `aurora-iopt1`."
  }
}

variable "kms_key_id" {
  description = "KMS key ARN for storage encryption. Null uses the AWS-managed aws/rds key. Storage is always encrypted."
  type        = string
  default     = null
}

variable "backup_retention_days" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be 1-35."
  }
}

variable "preferred_backup_window" {
  description = "Daily backup window in UTC, e.g. `03:00-04:00`. Null lets AWS choose."
  type        = string
  default     = null
}

variable "preferred_maintenance_window" {
  description = "Weekly maintenance window in UTC, e.g. `sun:05:00-sun:06:00`. Null lets AWS choose."
  type        = string
  default     = null
}

variable "deletion_protection" {
  description = "Block deletion of the cluster. Disable deliberately before destroying."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on deletion. Keep false outside of throwaway environments."
  type        = bool
  default     = false
}

variable "performance_insights_enabled" {
  description = "Default Performance Insights setting for instances (overridable per instance)."
  type        = bool
  default     = true
}

variable "iam_database_authentication" {
  description = "Enable IAM database authentication."
  type        = bool
  default     = true
}

variable "allow_major_version_upgrade" {
  description = "Allow engine_version changes that cross a major version."
  type        = bool
  default     = false
}

variable "apply_immediately" {
  description = "Apply modifications immediately instead of in the next maintenance window (may cause downtime)."
  type        = bool
  default     = false
}
