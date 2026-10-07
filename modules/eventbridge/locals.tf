locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  bus_name = var.create_bus ? var.name : "default"

  targets = {
    for pair in flatten([
      for rk, r in var.rules : [
        for tk, t in r.targets : merge(t, { key = "${rk}/${tk}", rule = rk, target = tk })
      ]
    ]) : pair.key => pair
  }
}
