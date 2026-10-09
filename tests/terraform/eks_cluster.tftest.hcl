# modules/eks/cluster: the EKS control plane. Private endpoint by default, access by API entries, and a public endpoint only with explicit CIDRs.

mock_provider "aws" {
  mock_resource "aws_eks_cluster" {
    defaults = {
      arn                   = "arn:aws:eks:us-east-1:111122223333:cluster/test"
      identity              = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/0123456789ABCDEF" }] }]
      certificate_authority = [{ data = "ZGF0YQ==" }]
    }
  }
}

variables {
  name               = "test-eks"
  kubernetes_version = "1.31"
  cluster_role_arn   = "arn:aws:iam::111122223333:role/eks-cluster"
  subnet_ids         = ["subnet-1", "subnet-2"]
  tags               = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_has_a_private_endpoint" {
  command = apply
  module {
    source = "../../modules/eks/cluster"
  }
  assert {
    condition     = one(aws_eks_cluster.this.vpc_config).endpoint_private_access == true && one(aws_eks_cluster.this.vpc_config).endpoint_public_access == false
    error_message = "by default the API endpoint is private only"
  }
}

run "access_is_given_by_api_entries_by_default" {
  command = apply
  module {
    source = "../../modules/eks/cluster"
  }
  assert {
    condition     = one(aws_eks_cluster.this.access_config).authentication_mode == "API"
    error_message = "the default authentication mode is API"
  }
}

run "irsa_creates_the_oidc_provider_by_default" {
  command = apply
  module {
    source = "../../modules/eks/cluster"
  }
  assert {
    condition     = length(aws_iam_openid_connect_provider.this) == 1
    error_message = "enable_irsa defaults to true, so the OIDC provider is created"
  }
}

run "irsa_can_be_turned_off" {
  command = apply
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    enable_irsa = false
  }
  assert {
    condition     = length(aws_iam_openid_connect_provider.this) == 0
    error_message = "enable_irsa = false creates no OIDC provider"
  }
}

run "an_access_entry_with_a_policy_is_associated" {
  command = apply
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    access_entries = {
      admins = {
        principal_arn = "arn:aws:iam::111122223333:role/admins"
        policies      = { admin = { policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy" } }
      }
    }
  }
  assert {
    condition     = length(aws_eks_access_entry.this) == 1 && length(aws_eks_access_policy_association.this) == 1
    error_message = "an access entry and its policy association"
  }
}

run "an_endpoint_that_is_neither_private_nor_public_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    endpoint_private_access = false
  }
  expect_failures = [aws_eks_cluster.this]
}

run "a_public_endpoint_outside_dev_without_cidrs_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    endpoint_public_access = true
    tags                   = { environment = "prod", owner = "team", cost_center = "cc-1", project = "demo" }
  }
  expect_failures = [aws_eks_cluster.this]
}

run "a_kubernetes_version_that_does_not_look_like_one_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    kubernetes_version = "latest"
  }
  expect_failures = [var.kubernetes_version]
}

run "an_access_policy_with_an_unknown_scope_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/cluster"
  }
  variables {
    access_entries = {
      admins = {
        principal_arn = "arn:aws:iam::111122223333:role/admins"
        policies      = { admin = { policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy", scope = "everywhere" } }
      }
    }
  }
  expect_failures = [var.access_entries]
}
