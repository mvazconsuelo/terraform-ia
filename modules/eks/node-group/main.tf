resource "aws_eks_node_group" "this" {
  for_each = var.groups

  cluster_name    = var.cluster_name
  node_group_name = "${local.name_prefix}-${each.key}"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids

  instance_types = each.value.instance_types
  capacity_type  = each.value.capacity_type
  ami_type       = each.value.ami_type
  disk_size      = each.value.disk_size_gb

  labels = merge(each.value.labels, { "node-group" = each.key })

  scaling_config {
    min_size     = each.value.min_size
    desired_size = each.value.desired_size
    max_size     = each.value.max_size
  }

  update_config {
    max_unavailable = each.value.max_unavailable
  }

  dynamic "taint" {
    for_each = each.value.taints

    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-${each.key}", NodeGroup = each.key })

  lifecycle {
    # The cluster autoscaler / Karpenter owns desired_size after creation.
    ignore_changes = [scaling_config[0].desired_size]
  }
}
