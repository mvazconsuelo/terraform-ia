# Certificate: public ACM certificate, validated by DNS
module "certificate" {
  source = "../../../modules/acm"

  name                      = templatestring(local.inputs.certificate.name, local.tags)
  domain_name               = local.inputs.certificate.domain_name
  subject_alternative_names = local.inputs.certificate.subject_alternative_names
  zone_id                   = local.inputs.certificate.zone_id
  tags                      = local.tags
}

# Load balancer: application load balancer
module "alb" {
  source = "../../../modules/elb/alb"

  name = templatestring(local.inputs.alb.name, local.tags)
  tags = local.tags

  vpc_id                     = module.vpc.vpc_id
  public_subnet_ids          = module.vpc.public_subnet_ids
  private_subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids         = [module.alb_sg.security_group_id]
  internal                   = local.inputs.alb.internal
  enable_deletion_protection = local.inputs.alb.deletion_protection

  target_groups = local.inputs.alb.target_groups
  listeners     = local.inputs.alb.listeners
  rules         = local.inputs.alb.rules
  certificates  = { web = module.certificate.certificate_arn }
}
