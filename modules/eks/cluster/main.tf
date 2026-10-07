resource "aws_eks_cluster" "this" {
  name     = var.name
  version  = var.kubernetes_version
  role_arn = var.cluster_role_arn

  enabled_cluster_log_types = var.enabled_log_types

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = var.additional_security_group_ids
    endpoint_private_access = var.endpoint_private_access
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = length(var.public_access_cidrs) == 0 ? null : var.public_access_cidrs
  }

  access_config {
    authentication_mode                         = var.authentication_mode
    bootstrap_cluster_creator_admin_permissions = var.bootstrap_cluster_creator_admin
  }

  upgrade_policy {
    support_type = var.support_type
  }

  dynamic "kubernetes_network_config" {
    for_each = var.service_ipv4_cidr == null ? [] : [var.service_ipv4_cidr]

    content {
      service_ipv4_cidr = kubernetes_network_config.value
    }
  }

  dynamic "encryption_config" {
    for_each = var.secrets_kms_key_arn == null ? [] : [var.secrets_kms_key_arn]

    content {
      resources = ["secrets"]

      provider {
        key_arn = encryption_config.value
      }
    }
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    # Immutable after creation; ignoring avoids a forced replacement if the creator-admin setting is changed later.
    ignore_changes = [access_config[0].bootstrap_cluster_creator_admin_permissions]

    precondition {
      condition     = var.endpoint_private_access || var.endpoint_public_access
      error_message = "At least one of endpoint_private_access or endpoint_public_access must be true."
    }

    precondition {
      condition     = !var.endpoint_public_access || var.tags.environment == "dev" || (length(var.public_access_cidrs) > 0 && !contains(var.public_access_cidrs, "0.0.0.0/0"))
      error_message = "Outside dev, a public endpoint requires explicit public_access_cidrs and never 0.0.0.0/0."
    }

    precondition {
      condition     = length(var.access_entries) == 0 || var.authentication_mode != "CONFIG_MAP"
      error_message = "access_entries require authentication_mode API or API_AND_CONFIG_MAP."
    }
  }
}

# IRSA. AWS validates the EKS OIDC issuer against its own trusted CA library, so the thumbprint is a placeholder required by older providers.
resource "aws_iam_openid_connect_provider" "this" {
  count = var.enable_irsa ? 1 : 0

  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]

  tags = merge(local.tags, { Name = "${var.name}-irsa" })
}

resource "aws_eks_access_entry" "this" {
  for_each = var.access_entries

  cluster_name      = aws_eks_cluster.this.name
  principal_arn     = each.value.principal_arn
  type              = each.value.type
  kubernetes_groups = each.value.kubernetes_groups

  tags = merge(local.tags, { Name = "${var.name}-${each.key}" })
}

resource "aws_eks_access_policy_association" "this" {
  for_each = local.access_policy_associations

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_eks_access_entry.this[each.value.entry].principal_arn
  policy_arn    = each.value.policy_arn

  access_scope {
    type       = each.value.scope
    namespaces = each.value.scope == "namespace" ? each.value.namespaces : null
  }
}
