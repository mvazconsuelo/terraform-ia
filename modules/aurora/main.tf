resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids

  tags = merge(local.tags, { Name = var.name })
}

resource "aws_rds_cluster_parameter_group" "this" {
  count = length(var.cluster_parameters) > 0 ? 1 : 0

  name_prefix = "${var.name}-"
  family      = local.family
  description = "${var.name} cluster parameters"

  dynamic "parameter" {
    for_each = var.cluster_parameters

    content {
      name         = parameter.key
      value        = parameter.value.value
      apply_method = parameter.value.apply_method
    }
  }

  tags = merge(local.tags, { Name = "${var.name}-cluster" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_parameter_group" "this" {
  count = length(var.instance_parameters) > 0 ? 1 : 0

  name_prefix = "${var.name}-"
  family      = local.family
  description = "${var.name} instance parameters"

  dynamic "parameter" {
    for_each = var.instance_parameters

    content {
      name         = parameter.key
      value        = parameter.value.value
      apply_method = parameter.value.apply_method
    }
  }

  tags = merge(local.tags, { Name = "${var.name}-instance" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_rds_cluster" "this" {
  cluster_identifier = var.name
  engine             = local.spec.engine
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  port               = local.port
  database_name      = var.database_name

  master_username             = local.master_username
  manage_master_user_password = true

  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = var.security_group_ids
  db_cluster_parameter_group_name = one(aws_rds_cluster_parameter_group.this[*].name)

  storage_type                        = var.storage_type == "aurora" ? null : var.storage_type
  storage_encrypted                   = true
  kms_key_id                          = var.kms_key_id
  iam_database_authentication_enabled = var.iam_database_authentication
  backup_retention_period             = var.backup_retention_days
  preferred_backup_window             = var.preferred_backup_window
  preferred_maintenance_window        = var.preferred_maintenance_window
  deletion_protection                 = var.deletion_protection
  skip_final_snapshot                 = var.skip_final_snapshot
  final_snapshot_identifier           = var.skip_final_snapshot ? null : "${var.name}-final"
  copy_tags_to_snapshot               = true
  enabled_cloudwatch_logs_exports     = local.log_exports
  allow_major_version_upgrade         = var.allow_major_version_upgrade
  apply_immediately                   = var.apply_immediately

  dynamic "serverlessv2_scaling_configuration" {
    for_each = var.serverless_v2 == null ? [] : [var.serverless_v2]

    content {
      min_capacity = serverlessv2_scaling_configuration.value.min_capacity
      max_capacity = serverlessv2_scaling_configuration.value.max_capacity
    }
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    # Stateful: replacement destroys data. Identifier, engine, encryption, KMS key and subnet group are immutable.
    # engine_version: AWS applies minor upgrades (auto minor upgrade); bump it via a deliberate, reviewed change.
    ignore_changes = [engine_version]

    precondition {
      condition     = var.engine == "postgresql" ? can(regex("^[0-9]+\\.[0-9]+$", var.engine_version)) : can(regex("\\.mysql_aurora\\.", var.engine_version))
      error_message = "engine_version does not match the engine: postgresql expects `16.4`, mysql expects `8.0.mysql_aurora.3.05.2`."
    }
  }
}

resource "aws_rds_cluster_instance" "this" {
  for_each = local.instances

  identifier                   = "${var.name}-${each.key}"
  cluster_identifier           = aws_rds_cluster.this.id
  engine                       = aws_rds_cluster.this.engine
  engine_version               = aws_rds_cluster.this.engine_version
  instance_class               = each.value.instance_class
  db_subnet_group_name         = aws_db_subnet_group.this.name
  db_parameter_group_name      = one(aws_db_parameter_group.this[*].name)
  publicly_accessible          = false
  auto_minor_version_upgrade   = true
  performance_insights_enabled = each.value.performance_insights_enabled
  promotion_tier               = each.value.promotion_tier
  apply_immediately            = var.apply_immediately

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}
