# Network: VPC and the three security groups
# SG-to-SG references go one way (app <- alb, db <- app). The reverse directions (alb -> app, app -> db) use the VPC CIDR
# (cidr_ipv4: vpc): referencing the groups in both directions would be a dependency cycle.
module "vpc" {
  source = "../../../modules/vpc"

  name = templatestring(local.inputs.network.name, local.tags)
  tags = local.tags

  cidr_block           = local.inputs.network.cidr_block
  availability_zones   = local.inputs.network.availability_zones
  public_subnet_cidrs  = local.inputs.network.public_subnet_cidrs
  private_subnet_cidrs = local.inputs.network.private_subnet_cidrs
  nat_gateway_mode     = local.inputs.network.nat_gateway_mode
}

# One security group per tier. The rules are written in inputs.yaml and the module resolves them (`port`, `cidr_ipv4: vpc`, `source_sg`).
module "alb_sg" {
  source = "../../../modules/security-group"

  name                 = templatestring(local.inputs.security_groups.alb.name, local.tags)
  description          = local.inputs.security_groups.alb.description
  vpc_id               = module.vpc.vpc_id
  vpc_cidr_block       = module.vpc.vpc_cidr_block
  tags                 = local.tags
  allow_public_ingress = local.inputs.security_groups.alb.allow_public_ingress
  ingress_rules        = local.inputs.security_groups.alb.ingress
  egress_rules         = local.inputs.security_groups.alb.egress
}

module "app_sg" {
  source = "../../../modules/security-group"

  name                   = templatestring(local.inputs.security_groups.app.name, local.tags)
  description            = local.inputs.security_groups.app.description
  vpc_id                 = module.vpc.vpc_id
  vpc_cidr_block         = module.vpc.vpc_cidr_block
  tags                   = local.tags
  source_security_groups = { alb = module.alb_sg.security_group_id }
  ingress_rules          = local.inputs.security_groups.app.ingress
  egress_rules           = local.inputs.security_groups.app.egress
}

module "db_sg" {
  source = "../../../modules/security-group"

  name                   = templatestring(local.inputs.security_groups.db.name, local.tags)
  description            = local.inputs.security_groups.db.description
  vpc_id                 = module.vpc.vpc_id
  tags                   = local.tags
  source_security_groups = { app = module.app_sg.security_group_id }
  ingress_rules          = local.inputs.security_groups.db.ingress
}
