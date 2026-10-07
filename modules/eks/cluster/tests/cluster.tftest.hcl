mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name               = "shop-dev"
  kubernetes_version = "1.31"
  cluster_role_arn   = "arn:aws:iam::111122223333:role/shop-dev-eks"
  subnet_ids         = ["subnet-a", "subnet-b"]
}

run "private_secure_defaults" {
  command = plan

  assert {
    condition = (
      aws_eks_cluster.this.vpc_config[0].endpoint_private_access &&
      !aws_eks_cluster.this.vpc_config[0].endpoint_public_access &&
      aws_eks_cluster.this.access_config[0].authentication_mode == "API" &&
      contains(aws_eks_cluster.this.enabled_cluster_log_types, "audit")
    )
    error_message = "Defaults: private endpoint only, API authentication mode, audit logging."
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.this) == 1 && length(aws_eks_access_entry.this) == 0
    error_message = "IRSA on, no access entries by default."
  }
}

run "mandatory_tags_applied" {
  command = plan

  variables {
    access_entries = {
      admins = { principal_arn = "arn:aws:iam::111122223333:role/admins" }
    }
  }

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_eks_cluster.this.tags), k) && contains(keys(aws_iam_openid_connect_provider.this[0].tags), k) && contains(keys(aws_eks_access_entry.this["admins"].tags), k)
    ])
    error_message = "Cluster, OIDC provider and access entries need mandatory tags."
  }
}

run "irsa_can_be_disabled" {
  command = plan

  variables {
    enable_irsa = false
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.this) == 0
    error_message = "No OIDC provider expected."
  }
}

run "access_entries_with_policies" {
  command = plan

  variables {
    access_entries = {
      admins = {
        principal_arn = "arn:aws:iam::111122223333:role/admins"
        policies      = { admin = { policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy" } }
      }
      devs = {
        principal_arn = "arn:aws:iam::111122223333:role/devs"
        policies      = { view = { policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy", scope = "namespace", namespaces = ["apps"] } }
      }
    }
  }

  assert {
    condition     = length(aws_eks_access_entry.this) == 2 && length(aws_eks_access_policy_association.this) == 2
    error_message = "Two entries and two policy associations expected."
  }
}

run "secrets_encryption" {
  command = plan

  variables {
    secrets_kms_key_arn = "arn:aws:kms:us-east-1:111122223333:key/abc"
  }

  assert {
    condition     = length(aws_eks_cluster.this.encryption_config) == 1
    error_message = "Envelope encryption config expected."
  }
}

run "dev_may_use_public_endpoint" {
  command = plan

  variables {
    endpoint_public_access = true
  }

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_public_access
    error_message = "Dev allows a public endpoint."
  }
}

run "prod_public_endpoint_needs_cidrs" {
  command = plan

  variables {
    tags = {
      environment = "prod"
      owner       = "platform-team"
      cost_center = "cc-1234"
      project     = "terra-ai"
    }
    endpoint_public_access = true
  }

  expect_failures = [aws_eks_cluster.this]
}

run "prod_public_endpoint_with_cidrs_ok" {
  command = plan

  variables {
    tags = {
      environment = "prod"
      owner       = "platform-team"
      cost_center = "cc-1234"
      project     = "terra-ai"
    }
    endpoint_public_access = true
    public_access_cidrs    = ["203.0.113.0/24"]
  }

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_public_access
    error_message = "Explicit CIDRs should allow a public endpoint in prod."
  }
}

run "needs_one_endpoint" {
  command = plan

  variables {
    endpoint_private_access = false
  }

  expect_failures = [aws_eks_cluster.this]
}

run "access_entries_need_api_mode" {
  command = plan

  variables {
    authentication_mode = "CONFIG_MAP"
    access_entries = {
      admins = { principal_arn = "arn:aws:iam::111122223333:role/admins" }
    }
  }

  expect_failures = [aws_eks_cluster.this]
}

run "namespace_scope_needs_namespaces" {
  command = plan

  variables {
    access_entries = {
      devs = {
        principal_arn = "arn:aws:iam::111122223333:role/devs"
        policies      = { view = { policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy", scope = "namespace" } }
      }
    }
  }

  expect_failures = [var.access_entries]
}

run "rejects_bad_kubernetes_version" {
  command = plan

  variables {
    kubernetes_version = "latest"
  }

  expect_failures = [var.kubernetes_version]
}

run "rejects_single_subnet" {
  command = plan

  variables {
    subnet_ids = ["subnet-a"]
  }

  expect_failures = [var.subnet_ids]
}
