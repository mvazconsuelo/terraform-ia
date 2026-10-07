# Network: VPC and the three security groups
# SG-to-SG references go one way (app <- alb, db <- app). The reverse directions (alb -> app, app -> db) use the VPC CIDR
# with explicit ports: referencing the groups in both directions would be a dependency cycle.
module "vpc" {
  source = "../../../modules/vpc"

  name = local.name
  tags = local.tags

  cidr_block           = local.inputs.network.cidr_block
  availability_zones   = local.inputs.network.availability_zones
  public_subnet_cidrs  = local.inputs.network.public_subnet_cidrs
  private_subnet_cidrs = local.inputs.network.private_subnet_cidrs
  nat_gateway_mode     = local.nat_gateway_mode

  depends_on = [terraform_data.config_validation]
}

# One security group per tier.
module "alb_sg" {
  source = "../../../modules/security-group"

  name        = "${local.name}-alb"
  description = local.inputs.security_groups.alb.description
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags

  allow_public_ingress = try(local.inputs.security_groups.alb.allow_public_ingress, false)

  ingress_rules = {
    for k, r in try(local.inputs.security_groups.alb.ingress, {}) : k => {
      description = r.description
      protocol    = try(r.protocol, "tcp")
      from_port   = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      to_port     = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      cidr_ipv4   = try(r.cidr_ipv4 == "vpc" ? module.vpc.vpc_cidr_block : r.cidr_ipv4, null)
    }
  }

  egress_rules = {
    for k, r in try(local.inputs.security_groups.alb.egress, {}) : k => {
      description = r.description
      protocol    = try(r.protocol, "tcp")
      from_port   = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      to_port     = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      cidr_ipv4   = try(r.cidr_ipv4 == "vpc" ? module.vpc.vpc_cidr_block : r.cidr_ipv4, null)
    }
  }
}

module "app_sg" {
  source = "../../../modules/security-group"

  name        = "${local.name}-app"
  description = local.inputs.security_groups.app.description
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags

  ingress_rules = {
    for k, r in try(local.inputs.security_groups.app.ingress, {}) : k => {
      description                  = r.description
      protocol                     = try(r.protocol, "tcp")
      from_port                    = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      to_port                      = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      cidr_ipv4                    = try(r.cidr_ipv4 == "vpc" ? module.vpc.vpc_cidr_block : r.cidr_ipv4, null)
      referenced_security_group_id = try(r.source_sg == "alb" ? module.alb_sg.security_group_id : null, null)
    }
  }

  egress_rules = {
    for k, r in try(local.inputs.security_groups.app.egress, {}) : k => {
      description = r.description
      protocol    = try(r.protocol, "tcp")
      from_port   = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      to_port     = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      cidr_ipv4   = try(r.cidr_ipv4 == "vpc" ? module.vpc.vpc_cidr_block : r.cidr_ipv4, null)
    }
  }
}

module "db_sg" {
  source = "../../../modules/security-group"

  name        = "${local.name}-db"
  description = local.inputs.security_groups.db.description
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags

  ingress_rules = {
    for k, r in try(local.inputs.security_groups.db.ingress, {}) : k => {
      description                  = r.description
      protocol                     = try(r.protocol, "tcp")
      from_port                    = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      to_port                      = try(local.named_ports[tostring(r.port)], tonumber(r.port))
      cidr_ipv4                    = try(r.cidr_ipv4 == "vpc" ? module.vpc.vpc_cidr_block : r.cidr_ipv4, null)
      referenced_security_group_id = try(r.source_sg == "app" ? module.app_sg.security_group_id : null, null)
    }
  }
}
