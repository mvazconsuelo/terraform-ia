# Web tier: instance role, launch template and Auto Scaling Group
data "aws_iam_policy_document" "read_db_secret" {
  statement {
    sid       = "ReadDatabaseSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.database.master_user_secret_arn]
  }
}

module "instance_role" {
  source = "../../../modules/iam"

  name = "${local.name}-web"
  tags = local.tags

  assume_role_services    = local.inputs.instance_role.assume_role_services
  managed_policy_arns     = local.inputs.instance_role.managed_policy_arns
  create_instance_profile = local.inputs.instance_role.create_instance_profile

  inline_policies = {
    for k, v in { read-db-secret = data.aws_iam_policy_document.read_db_secret.json } : k => v
    if local.inputs.instance_role.allow_read_db_secret
  }

  depends_on = [terraform_data.config_validation]
}

module "web_template" {
  source = "../../../modules/ec2/launch-template"

  name = "${local.name}-web"
  tags = local.tags

  instance_type             = local.inputs.compute.instance_type
  ami_id                    = try(local.inputs.compute.ami_id, null)
  root_volume_size_gb       = local.inputs.compute.root_volume_size_gb
  security_group_ids        = [module.app_sg.security_group_id]
  iam_instance_profile_name = module.instance_role.instance_profile_name

  user_data = templatefile("${path.module}/web-user-data.sh.tftpl", {
    app_port      = local.app_port
    db_host       = module.database.endpoint
    db_port       = local.db_port
    db_name       = local.inputs.database.database_name
    db_secret_arn = module.database.master_user_secret_arn
  })
}

module "web_asg" {
  source = "../../../modules/ec2/asg"

  name = "${local.name}-web"
  tags = local.tags

  subnet_ids              = module.vpc.private_subnet_ids
  launch_template_id      = module.web_template.launch_template_id
  launch_template_version = module.web_template.latest_version
  min_size                = local.inputs.compute.min_size
  desired_size            = local.inputs.compute.desired_size
  max_size                = local.inputs.compute.max_size
  target_group_arns       = [module.alb.target_group_arns[local.inputs.compute.target_group]]

  health_check_type         = local.inputs.compute.health_check_type
  health_check_grace_period = try(local.inputs.compute.health_check_grace_period, 300)
  enable_instance_refresh   = try(local.inputs.compute.enable_instance_refresh, true)
  scaling_policies          = try(local.inputs.compute.scaling_policies, {})
}
