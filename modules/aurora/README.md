# modules/aurora

One module for **Aurora PostgreSQL and Aurora MySQL**. The `engine` input selects the engine; port, master username, log exports and parameter group family are derived from it and can be overridden. Encrypted storage, managed master password (Secrets Manager), deletion protection and private-only instances are always on.
**Non-goals:** global clusters, cross-region replicas, RDS Proxy, schema/user management, non-Aurora RDS (`aws_db_instance`).

## Usage

```hcl
# PostgreSQL
module "orders_db" {
  source = "../../modules/aurora"

  name               = "orders-dev"
  engine             = "postgresql"
  engine_version     = "16.4"                       # choose a currently supported version
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.db_sg.security_group_id]
  tags               = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "orders" }

  cluster_parameters = { "rds.force_ssl" = { value = "1" } }
}

# MySQL, Serverless v2, explicit instances
module "catalog_db" {
  source = "../../modules/aurora"

  name               = "catalog-dev"
  engine             = "mysql"
  engine_version     = "8.0.mysql_aurora.3.05.2"
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.db_sg.security_group_id]
  tags               = local.tags

  serverless_v2 = { min_capacity = 0.5, max_capacity = 8 }
  instances = {
    writer   = { promotion_tier = 0 }
    reader-a = { promotion_tier = 1 }
  }
}
```

## Engine defaults

| | `postgresql` | `mysql` |
|---|---|---|
| Aurora engine | `aurora-postgresql` | `aurora-mysql` |
| Port | 5432 | 3306 |
| Master user | `postgres` | `admin` |
| Log exports | `postgresql` | `audit`, `error`, `general`, `slowquery` |
| Version format | `16.4` | `8.0.mysql_aurora.3.05.2` |
| Parameter group family | `aurora-postgresql16` | `aurora-mysql8.0` |

A precondition rejects a version that does not match the chosen engine.

## Resources and tags

`aws_db_subnet_group`, `aws_rds_cluster`, `aws_rds_cluster_instance`, and (only when parameters are given) `aws_rds_cluster_parameter_group` and `aws_db_parameter_group` — all taggable and tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

| Name | Default | Notes |
|---|---|---|
| `name`, `engine`, `engine_version` | — | No default version on purpose. |
| `tags`, `extra_tags` | — / `{}` | See module standard. |
| `subnet_ids`, `security_group_ids` | — | ≥ 2 private subnets. |
| `instances` | writer + 1 reader | Map keyed by logical name: `instance_class`, `promotion_tier` (lowest = preferred writer), `performance_insights_enabled`. Adding/removing keys adds/removes instances. |
| `instance_class` | `db.t4g.medium` | Default class; ignored with `serverless_v2`. |
| `serverless_v2` | `null` | `{ min_capacity, max_capacity }` ACUs; works for both engines. |
| `cluster_parameters`, `instance_parameters` | `{}` | `{ name = { value, apply_method } }`; creates parameter groups with the derived family. |
| `parameter_group_family`, `port`, `master_username`, `enabled_cloudwatch_logs_exports` | `null` | Override engine defaults. |
| `storage_type` | `aurora` | Or `aurora-iopt1` (I/O-Optimized). |
| `kms_key_id` | `null` | AWS-managed `aws/rds` key if null. |
| `backup_retention_days`, `preferred_backup_window`, `preferred_maintenance_window` | 7 / `null` / `null` | |
| `deletion_protection`, `skip_final_snapshot` | `true`, `false` | |
| `performance_insights_enabled`, `iam_database_authentication` | `true`, `true` | |
| `allow_major_version_upgrade`, `apply_immediately` | `false`, `false` | |

## Outputs

`cluster_id`, `cluster_arn`, `engine`, `endpoint`, `reader_endpoint`, `port`, `instance_endpoints` (by instance key), `master_user_secret_arn`, `parameter_group_family`.

## Lifecycle

- **Stateful.** Changing `name`, `engine`, encryption/KMS key or subnet group replaces the cluster and destroys data. Disable `deletion_protection` deliberately before destroy; a final snapshot is taken unless `skip_final_snapshot`.
- `engine_version` is in `ignore_changes` (AWS applies minor upgrades). Major upgrades need `allow_major_version_upgrade = true` plus a parameter group family change, and a maintenance plan; a changed family replaces the parameter groups (created with `create_before_destroy`).
- Static parameters need `apply_method = "pending-reboot"` and a reboot to take effect.
- Instance keys are identities: renaming a key replaces that instance.

## Cost

Instances (class × count) + storage + backups; `aurora-iopt1` removes per-I/O charges for a higher instance/storage price (worth it when I/O exceeds roughly a quarter of spend). Serverless v2 bills ACU-hours; minimum capacity is always billed unless it is 0.
