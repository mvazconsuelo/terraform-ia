locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)


  lambda_routes   = { for k, r in var.routes : k => r if r.integration_type == "lambda" }
  vpc_link_routes = { for k, r in var.routes : k => r if r.integration_type == "vpc_link" }
}
