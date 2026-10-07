locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  az_count     = length(var.availability_zones)
  has_public   = length(var.public_subnet_cidrs) > 0
  nat_enabled  = var.nat_gateway_mode != "none" && local.has_public
  nat_count    = !local.nat_enabled ? 0 : (var.nat_gateway_mode == "single" ? 1 : local.az_count)
  public_azs   = { for i, cidr in var.public_subnet_cidrs : var.availability_zones[i] => cidr }
  private_azs  = { for i, cidr in var.private_subnet_cidrs : var.availability_zones[i] => cidr }
  nat_az_index = local.nat_enabled ? slice(var.availability_zones, 0, local.nat_count) : []
}
