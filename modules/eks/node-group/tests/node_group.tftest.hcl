mock_provider "aws" {}

variables {
  cluster_name  = "demo-dev"
  node_role_arn = "arn:aws:iam::111122223333:role/demo-nodes"
  subnet_ids    = ["subnet-aaa", "subnet-bbb"]
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  groups = {
    system = {
      instance_types = ["m6i.large"]
      min_size       = 2
      desired_size   = 2
      max_size       = 4
    }
    workloads = {
      instance_types = ["m6i.large"]
      min_size       = 2
      desired_size   = 3
      max_size       = 10
    }
  }
}

run "creates_one_group_per_key" {
  command = plan

  assert {
    condition     = length(aws_eks_node_group.this) == 2
    error_message = "Expected one managed node group per key."
  }

  assert {
    condition     = aws_eks_node_group.this["system"].node_group_name == "demo-dev-system"
    error_message = "Physical name must be <prefix>-<key>."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for g in values(aws_eks_node_group.this) :
      alltrue([for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] : contains(keys(g.tags), k)])
    ])
    error_message = "Node groups are missing mandatory tags."
  }
}

run "rejects_inverted_scaling" {
  command = plan

  variables {
    groups = {
      bad = {
        instance_types = ["m6i.large"]
        min_size       = 5
        desired_size   = 2
        max_size       = 4
      }
    }
  }

  expect_failures = [var.groups]
}

run "rejects_invalid_capacity_type" {
  command = plan

  variables {
    groups = {
      bad = {
        instance_types = ["m6i.large"]
        capacity_type  = "RESERVED"
        min_size       = 1
        desired_size   = 1
        max_size       = 2
      }
    }
  }

  expect_failures = [var.groups]
}

run "spot_requires_diversification" {
  command = plan

  variables {
    groups = {
      spot = {
        instance_types = ["m6i.large"]
        capacity_type  = "SPOT"
        min_size       = 1
        desired_size   = 1
        max_size       = 2
      }
    }
  }

  expect_failures = [var.groups]
}
