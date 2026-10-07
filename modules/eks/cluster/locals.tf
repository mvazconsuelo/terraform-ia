locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  access_policy_associations = {
    for pair in flatten([
      for ek, e in var.access_entries : [
        for pk, p in e.policies : merge(p, { key = "${ek}/${pk}", entry = ek })
      ]
    ]) : pair.key => pair
  }
}
