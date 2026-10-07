locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  data_volumes = {
    for pair in flatten([
      for ik, i in var.instances : [
        for vk, v in i.data_volumes : merge(v, { key = "${ik}/${vk}", instance = ik })
      ]
    ]) : pair.key => pair
  }
}
