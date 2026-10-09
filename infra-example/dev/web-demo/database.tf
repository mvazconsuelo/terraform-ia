# Database: Aurora (PostgreSQL or MySQL, chosen in inputs.yaml)
module "database" {
  source = "../../../modules/aurora"

  name = templatestring(local.inputs.database.name, local.tags)
  tags = local.tags

  engine             = local.inputs.database.engine
  engine_version     = local.inputs.database.engine_version
  database_name      = local.inputs.database.database_name
  port               = local.inputs.database.port
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.db_sg.security_group_id]

  instances             = local.inputs.database.instances
  instance_class        = local.inputs.database.instance_class
  serverless_v2         = local.inputs.database.serverless_v2
  backup_retention_days = local.inputs.database.backup_retention_days
  deletion_protection   = local.inputs.database.deletion_protection
  skip_final_snapshot   = local.inputs.database.skip_final_snapshot
  cluster_parameters    = local.inputs.database.cluster_parameters
}
