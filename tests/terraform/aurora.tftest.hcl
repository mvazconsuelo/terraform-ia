# modules/aurora: an Aurora cluster, PostgreSQL or MySQL. Safe by default: encrypted, deletion protected, a final snapshot, and a password it does not know.

mock_provider "aws" {
  mock_resource "aws_rds_cluster" {
    defaults = { arn = "arn:aws:rds:us-east-1:111122223333:cluster:test" }
  }
}

variables {
  name               = "test-db"
  engine             = "postgresql"
  engine_version     = "16.4"
  subnet_ids         = ["subnet-1", "subnet-2"]
  security_group_ids = ["sg-1"]
  tags               = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_is_safe_by_default" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  assert {
    condition     = aws_rds_cluster.this.storage_encrypted == true && aws_rds_cluster.this.deletion_protection == true && aws_rds_cluster.this.skip_final_snapshot == false
    error_message = "by default the cluster is encrypted, protected from deletion and keeps a final snapshot"
  }
}

run "the_master_password_is_managed_by_aws_and_never_known_to_terraform" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  assert {
    condition     = aws_rds_cluster.this.manage_master_user_password == true
    error_message = "the password lives in Secrets Manager, managed by RDS"
  }
}

run "postgresql_uses_the_aurora_postgresql_engine_on_port_5432" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  assert {
    condition     = aws_rds_cluster.this.engine == "aurora-postgresql" && aws_rds_cluster.this.port == 5432
    error_message = "engine = postgresql means aurora-postgresql on 5432"
  }
}

run "mysql_uses_the_aurora_mysql_engine_on_port_3306" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  variables {
    engine         = "mysql"
    engine_version = "8.0.mysql_aurora.3.05.2"
  }
  assert {
    condition     = aws_rds_cluster.this.engine == "aurora-mysql" && aws_rds_cluster.this.port == 3306
    error_message = "engine = mysql means aurora-mysql on 3306"
  }
}

run "the_default_is_a_writer_and_a_reader" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  assert {
    condition     = length(aws_rds_cluster_instance.this) == 2
    error_message = "with no instances given there are two: the writer and a reader to fail over to"
  }
}

run "serverless_capacity_makes_every_instance_serverless" {
  command = apply
  module {
    source = "../../modules/aurora"
  }
  variables {
    serverless_v2 = { min_capacity = 0.5, max_capacity = 4 }
  }
  assert {
    condition     = alltrue([for instance in aws_rds_cluster_instance.this : instance.instance_class == "db.serverless"])
    error_message = "with serverless_v2 every instance is db.serverless"
  }
}

run "an_unknown_engine_is_rejected" {
  command = plan
  module {
    source = "../../modules/aurora"
  }
  variables {
    engine = "oracle"
  }
  expect_failures = [var.engine]
}

run "an_engine_version_of_the_other_engine_is_rejected" {
  command = plan
  module {
    source = "../../modules/aurora"
  }
  variables {
    engine_version = "8.0.mysql_aurora.3.05.2"
  }
  expect_failures = [aws_rds_cluster.this]
}

run "subnets_in_a_single_zone_are_rejected" {
  command = plan
  module {
    source = "../../modules/aurora"
  }
  variables {
    subnet_ids = ["subnet-1"]
  }
  expect_failures = [var.subnet_ids]
}

run "a_backup_retention_out_of_range_is_rejected" {
  command = plan
  module {
    source = "../../modules/aurora"
  }
  variables {
    backup_retention_days = 90
  }
  expect_failures = [var.backup_retention_days]
}
