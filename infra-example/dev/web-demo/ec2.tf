# Web tier: instance role, launch template and Auto Scaling Group
module "instance_role" {
  source = "../../../modules/iam"

  name = templatestring(local.inputs.instance_role.name, local.tags)
  tags = local.tags

  assume_role_services    = local.inputs.instance_role.assume_role_services
  managed_policy_arns     = local.inputs.instance_role.managed_policy_arns
  create_instance_profile = local.inputs.instance_role.create_instance_profile

  inline_policies = { read-db-secret = data.aws_iam_policy_document.read_db_secret.json }
}

module "web_template" {
  source = "../../../modules/ec2/launch-template"

  name = templatestring(local.inputs.compute.name, local.tags)
  tags = local.tags

  instance_type             = local.inputs.compute.instance_type
  ami_id                    = local.inputs.compute.ami_id
  root_volume_size_gb       = local.inputs.compute.root_volume_size_gb
  security_group_ids        = [module.app_sg.security_group_id]
  iam_instance_profile_name = module.instance_role.instance_profile_name

  user_data = templatefile("${path.module}/web-user-data.sh.tftpl", {
    app_port      = local.inputs.compute.port
    db_host       = module.database.endpoint
    db_port       = local.inputs.database.port
    db_name       = local.inputs.database.database_name
    db_secret_arn = module.database.master_user_secret_arn
  })
}

module "web_asg" {
  source = "../../../modules/ec2/asg"

  name = templatestring(local.inputs.compute.name, local.tags)
  tags = local.tags

  subnet_ids              = module.vpc.private_subnet_ids
  launch_template_id      = module.web_template.launch_template_id
  launch_template_version = module.web_template.latest_version
  min_size                = local.inputs.compute.min_size
  desired_size            = local.inputs.compute.desired_size
  max_size                = local.inputs.compute.max_size
  target_group_arns       = [module.alb.target_group_arns[local.inputs.compute.target_group]]

  health_check_type         = local.inputs.compute.health_check_type
  health_check_grace_period = local.inputs.compute.health_check_grace_period
  enable_instance_refresh   = local.inputs.compute.enable_instance_refresh
  scaling_policies          = local.inputs.compute.scaling_policies
}
