mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  cluster_name = "shop-dev"
  addons = {
    vpc-cni = {}
    coredns = { version = "v1.11.3-eksbuild.1" }
    aws-ebs-csi-driver = {
      service_account_role_arn = "arn:aws:iam::111122223333:role/ebs-csi"
      configuration_values     = "{\"controller\":{\"replicaCount\":1}}"
    }
  }
}

run "installs_only_listed_addons" {
  command = plan

  assert {
    condition     = length(aws_eks_addon.this) == 3 && aws_eks_addon.this["coredns"].addon_version == "v1.11.3-eksbuild.1"
    error_message = "Exactly the three listed add-ons expected."
  }

  assert {
    condition     = aws_eks_addon.this["vpc-cni"].resolve_conflicts_on_update == "PRESERVE"
    error_message = "Updates must preserve existing customisations by default."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      alltrue([for a in values(aws_eks_addon.this) : contains(keys(a.tags), k)])
    ])
    error_message = "Add-ons need mandatory tags."
  }
}

run "rejects_empty_addons" {
  command = plan

  variables {
    addons = {}
  }

  expect_failures = [var.addons]
}

run "rejects_invalid_configuration_json" {
  command = plan

  variables {
    addons = { coredns = { configuration_values = "not json" } }
  }

  expect_failures = [var.addons]
}

run "rejects_bad_version_format" {
  command = plan

  variables {
    addons = { coredns = { version = "1.11" } }
  }

  expect_failures = [var.addons]
}

run "rejects_bad_conflict_resolution" {
  command = plan

  variables {
    addons = { coredns = { resolve_conflicts_on_create = "PRESERVE" } }
  }

  expect_failures = [var.addons]
}
