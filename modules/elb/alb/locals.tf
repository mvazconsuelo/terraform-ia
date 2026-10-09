locals {
  mandatory_tags = {
    Environment = var.tags.environment
    Owner       = var.tags.owner
    CostCenter  = var.tags.cost_center
    Project     = var.tags.project
    ManagedBy   = "terraform"
  }

  tags = merge(var.extra_tags, local.mandatory_tags)

  # The certificate each listener uses: the one it names in `certificates`, else its own certificate_arn.
  listener_certificate_arns = {
    for key, listener in var.listeners : key => listener.certificate != null ? var.certificates[listener.certificate] : listener.certificate_arn
  }
}
