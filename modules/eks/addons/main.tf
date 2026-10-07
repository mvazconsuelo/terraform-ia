# Add-ons such as coredns and aws-ebs-csi-driver need worker nodes to become ACTIVE: call this module with
# `depends_on = [module.node_groups]` from the composition.
resource "aws_eks_addon" "this" {
  for_each = var.addons

  cluster_name                = var.cluster_name
  addon_name                  = each.key
  addon_version               = each.value.version
  service_account_role_arn    = each.value.service_account_role_arn
  configuration_values        = each.value.configuration_values
  resolve_conflicts_on_create = each.value.resolve_conflicts_on_create
  resolve_conflicts_on_update = each.value.resolve_conflicts_on_update

  tags = merge(local.tags, { Name = "${var.cluster_name}-${each.key}" })
}
