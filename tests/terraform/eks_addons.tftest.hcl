# modules/eks/addons: EKS managed add-ons. Only what is listed is installed.

mock_provider "aws" {}

variables {
  cluster_name = "test-eks"
  tags         = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  addons       = { coredns = {} }
}

run "works_with_the_minimum_inputs_and_installs_only_what_is_listed" {
  command = apply
  module {
    source = "../../modules/eks/addons"
  }
  assert {
    condition     = length(aws_eks_addon.this) == 1 && contains(keys(aws_eks_addon.this), "coredns")
    error_message = "one add-on per entry of addons"
  }
}

run "conflicts_are_overwritten_on_create_and_preserved_on_update_by_default" {
  command = apply
  module {
    source = "../../modules/eks/addons"
  }
  assert {
    condition     = aws_eks_addon.this["coredns"].resolve_conflicts_on_create == "OVERWRITE" && aws_eks_addon.this["coredns"].resolve_conflicts_on_update == "PRESERVE"
    error_message = "defaults: OVERWRITE on create, PRESERVE on update"
  }
}

run "several_addons_are_each_installed" {
  command = apply
  module {
    source = "../../modules/eks/addons"
  }
  variables {
    addons = { coredns = {}, vpc-cni = { version = "v1.18.5-eksbuild.1" } }
  }
  assert {
    condition     = length(aws_eks_addon.this) == 2
    error_message = "every listed add-on is installed"
  }
}

run "no_addons_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/addons"
  }
  variables {
    addons = {}
  }
  expect_failures = [var.addons]
}

run "a_version_that_does_not_look_like_one_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/addons"
  }
  variables {
    addons = { coredns = { version = "latest" } }
  }
  expect_failures = [var.addons]
}

run "configuration_values_that_are_not_json_are_rejected" {
  command = plan
  module {
    source = "../../modules/eks/addons"
  }
  variables {
    addons = { coredns = { configuration_values = "not json" } }
  }
  expect_failures = [var.addons]
}

run "an_unknown_conflict_resolution_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/addons"
  }
  variables {
    addons = { coredns = { resolve_conflicts_on_create = "MAYBE" } }
  }
  expect_failures = [var.addons]
}
