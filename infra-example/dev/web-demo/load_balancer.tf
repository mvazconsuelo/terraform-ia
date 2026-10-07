# Load balancer: application load balancer
module "alb" {
  source = "../../../modules/elb/alb"

  name = local.name
  tags = local.tags

  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = local.inputs.alb.internal ? module.vpc.private_subnet_ids : module.vpc.public_subnet_ids
  security_group_ids         = [module.alb_sg.security_group_id]
  internal                   = local.inputs.alb.internal
  enable_deletion_protection = local.inputs.alb.deletion_protection

  target_groups = {
    for k, t in local.inputs.alb.target_groups : k => {
      port        = try(local.named_ports[tostring(t.port)], tonumber(t.port))
      protocol    = try(t.protocol, "HTTP")
      target_type = try(t.target_type, "instance")
      health_check = {
        path = try(t.health_check_path, "/")
      }
    }
  }

  listeners = local.inputs.alb.listeners
  rules     = try(local.inputs.alb.rules, {})

  depends_on = [terraform_data.config_validation]
}
