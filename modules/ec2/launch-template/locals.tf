locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  image_id = var.ami_id != null ? var.ami_id : nonsensitive(data.aws_ssm_parameter.ami[0].value)
}
