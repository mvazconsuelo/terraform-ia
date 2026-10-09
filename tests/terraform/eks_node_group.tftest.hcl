# modules/eks/node-group: EKS managed node groups, written as intent. Each group is one managed node group.

mock_provider "aws" {}

variables {
  cluster_name  = "test-eks"
  node_role_arn = "arn:aws:iam::111122223333:role/eks-nodes"
  subnet_ids    = ["subnet-1", "subnet-2"]
  tags          = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  groups = {
    system = { instance_types = ["t3.medium"], min_size = 1, desired_size = 2, max_size = 3 }
  }
}

run "works_with_the_minimum_inputs_and_is_on_demand" {
  command = apply
  module {
    source = "../../modules/eks/node-group"
  }
  assert {
    condition     = length(aws_eks_node_group.this) == 1 && aws_eks_node_group.this["system"].capacity_type == "ON_DEMAND"
    error_message = "a group is on demand unless it says spot"
  }
}

run "one_node_group_is_created_for_each_group" {
  command = apply
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    groups = {
      system    = { instance_types = ["t3.medium"], min_size = 1, desired_size = 2, max_size = 3 }
      workloads = { instance_types = ["m6i.large", "m5.large"], capacity_type = "SPOT", min_size = 0, desired_size = 2, max_size = 10 }
    }
  }
  assert {
    condition     = length(aws_eks_node_group.this) == 2 && aws_eks_node_group.this["workloads"].capacity_type == "SPOT"
    error_message = "each key of groups is a node group"
  }
}

run "no_groups_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    groups = {}
  }
  expect_failures = [var.groups]
}

run "sizes_out_of_order_are_rejected" {
  command = plan
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    groups = { system = { instance_types = ["t3.medium"], min_size = 3, desired_size = 1, max_size = 2 } }
  }
  expect_failures = [var.groups]
}

run "a_spot_group_with_one_instance_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    groups = { spot = { instance_types = ["t3.medium"], capacity_type = "SPOT", min_size = 0, desired_size = 1, max_size = 2 } }
  }
  expect_failures = [var.groups]
}

run "an_unknown_capacity_type_is_rejected" {
  command = plan
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    groups = { odd = { instance_types = ["t3.medium"], capacity_type = "RESERVED", min_size = 1, desired_size = 1, max_size = 2 } }
  }
  expect_failures = [var.groups]
}

run "fewer_than_two_subnets_are_rejected" {
  command = plan
  module {
    source = "../../modules/eks/node-group"
  }
  variables {
    subnet_ids = ["subnet-1"]
  }
  expect_failures = [var.subnet_ids]
}
