mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name               = "payments-dev"
  engine             = "postgresql"
  engine_version     = "16.4"
  subnet_ids         = ["subnet-a", "subnet-b"]
  security_group_ids = ["sg-1"]
}

run "postgresql_secure_defaults" {
  command = plan

  assert {
    condition = (
      aws_rds_cluster.this.engine == "aurora-postgresql" &&
      aws_rds_cluster.this.port == 5432 &&
      aws_rds_cluster.this.master_username == "postgres" &&
      aws_rds_cluster.this.storage_encrypted &&
      aws_rds_cluster.this.deletion_protection &&
      aws_rds_cluster.this.manage_master_user_password &&
      !aws_rds_cluster.this.skip_final_snapshot
    )
    error_message = "PostgreSQL defaults must be encrypted, protected, secret-managed with engine defaults."
  }

  assert {
    condition     = length(aws_rds_cluster_instance.this) == 2 && alltrue([for i in aws_rds_cluster_instance.this : !i.publicly_accessible])
    error_message = "Two private instances expected by default."
  }

  assert {
    condition     = length(aws_rds_cluster_parameter_group.this) == 0 && length(aws_db_parameter_group.this) == 0
    error_message = "No parameter groups unless parameters are given."
  }
}

run "mysql_engine_defaults" {
  command = plan

  variables {
    engine         = "mysql"
    engine_version = "8.0.mysql_aurora.3.05.2"
  }

  assert {
    condition = (
      aws_rds_cluster.this.engine == "aurora-mysql" &&
      aws_rds_cluster.this.port == 3306 &&
      aws_rds_cluster.this.master_username == "admin" &&
      contains(aws_rds_cluster.this.enabled_cloudwatch_logs_exports, "slowquery")
    )
    error_message = "MySQL must use aurora-mysql, port 3306, admin user and MySQL log exports."
  }

  assert {
    condition     = output.parameter_group_family == "aurora-mysql8.0"
    error_message = "MySQL family must derive to aurora-mysql8.0."
  }
}

run "postgresql_family_derived" {
  command = plan

  assert {
    condition     = output.parameter_group_family == "aurora-postgresql16"
    error_message = "PostgreSQL family must derive to aurora-postgresql16."
  }
}

run "parameter_groups_created" {
  command = plan

  variables {
    cluster_parameters  = { "rds.force_ssl" = { value = "1" } }
    instance_parameters = { log_min_duration_statement = { value = "500" } }
  }

  assert {
    condition = (
      aws_rds_cluster_parameter_group.this[0].family == "aurora-postgresql16" &&
      length(aws_db_parameter_group.this) == 1 &&
      contains(keys(aws_rds_cluster_parameter_group.this[0].tags), "CostCenter") &&
      contains(keys(aws_db_parameter_group.this[0].tags), "CostCenter")
    )
    error_message = "Tagged parameter groups with the derived family expected."
  }
}

run "custom_port_user_and_logs" {
  command = plan

  variables {
    port                            = 15432
    master_username                 = "app_admin"
    enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  }

  assert {
    condition     = aws_rds_cluster.this.port == 15432 && aws_rds_cluster.this.master_username == "app_admin" && length(aws_rds_cluster.this.enabled_cloudwatch_logs_exports) == 2
    error_message = "Overrides must win over engine defaults."
  }
}

run "dynamic_instances_with_overrides" {
  command = plan

  variables {
    instances = {
      writer   = { promotion_tier = 0, instance_class = "db.r6g.xlarge" }
      reader-a = { promotion_tier = 1 }
      reader-b = { promotion_tier = 2, performance_insights_enabled = false }
    }
  }

  assert {
    condition = (
      length(aws_rds_cluster_instance.this) == 3 &&
      aws_rds_cluster_instance.this["writer"].instance_class == "db.r6g.xlarge" &&
      aws_rds_cluster_instance.this["reader-a"].instance_class == "db.t4g.medium" &&
      !aws_rds_cluster_instance.this["reader-b"].performance_insights_enabled
    )
    error_message = "Per-instance overrides must fall back to module defaults."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_rds_cluster.this.tags), k) && contains(keys(aws_db_subnet_group.this.tags), k) && contains(keys(aws_rds_cluster_instance.this["1"].tags), k)
    ])
    error_message = "Cluster, subnet group and instances need mandatory tags."
  }
}

run "serverless_v2_for_mysql" {
  command = plan

  variables {
    engine         = "mysql"
    engine_version = "8.0.mysql_aurora.3.05.2"
    serverless_v2  = { min_capacity = 0.5, max_capacity = 4 }
    instances      = { "1" = { promotion_tier = 0 } }
  }

  assert {
    condition     = aws_rds_cluster_instance.this["1"].instance_class == "db.serverless"
    error_message = "Serverless v2 must use db.serverless instances."
  }
}

run "io_optimized_storage" {
  command = plan

  variables {
    storage_type = "aurora-iopt1"
  }

  assert {
    condition     = aws_rds_cluster.this.storage_type == "aurora-iopt1"
    error_message = "I/O-Optimized storage expected."
  }
}

run "rejects_engine_version_mismatch" {
  command = plan

  variables {
    engine = "mysql"
  }

  expect_failures = [aws_rds_cluster.this]
}

run "rejects_unknown_engine" {
  command = plan

  variables {
    engine = "oracle"
  }

  expect_failures = [var.engine]
}

run "rejects_inverted_capacity" {
  command = plan

  variables {
    serverless_v2 = { min_capacity = 8, max_capacity = 2 }
  }

  expect_failures = [var.serverless_v2]
}

run "rejects_single_subnet" {
  command = plan

  variables {
    subnet_ids = ["subnet-a"]
  }

  expect_failures = [var.subnet_ids]
}

run "rejects_bad_apply_method" {
  command = plan

  variables {
    cluster_parameters = { x = { value = "1", apply_method = "later" } }
  }

  expect_failures = [var.cluster_parameters]
}
