# modules/eks/node-group

EKS **managed** node groups, expressed as intent (`groups`). The module creates `aws_eks_node_group`; EKS owns the underlying Auto Scaling Groups, which are never managed directly.
**Non-goals:** cluster, IAM node role, add-ons, Karpenter/self-managed nodes, launch templates.

## Usage

```hcl
module "node_groups" {
  source = "../../modules/eks/node-group"

  cluster_name  = module.eks.cluster_name
  node_role_arn = module.iam.node_role_arn
  subnet_ids    = module.vpc.private_subnet_ids
  tags          = local.tags

  groups = local.config.node_groups   # typed; validated by the module
}
```

```yaml
node_groups:
  system:
    instance_types: [m6i.large]
    capacity_type: ON_DEMAND
    min_size: 2
    desired_size: 2
    max_size: 4
```

## Resources and tags

`aws_eks_node_group` (taggable): `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`, plus `NodeGroup`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `cluster_name` | string | — | Target cluster. |
| `name_prefix` | string | `null` | Defaults to the cluster name; group key is appended. |
| `node_role_arn` | string | — | Node IAM role. |
| `subnet_ids` | list(string) | — | ≥ 2 private subnets. |
| `tags`, `extra_tags` | object, map | — | See module standard. |
| `groups` | map(object) | — | `instance_types`, `capacity_type` (ON_DEMAND/SPOT), `ami_type`, `disk_size_gb`, `min/desired/max_size`, `max_unavailable`, `labels`, `taints`. |

Validations: `min ≤ desired ≤ max`, enum capacity type and taint effect, SPOT needs ≥ 2 instance types, group-key format.

## Outputs

`node_group_arns`, `node_group_names`, `node_group_status` (keyed by group).

## Lifecycle

- `desired_size` is in `ignore_changes`: the autoscaler owns it after creation (change min/max instead).
- Changing `instance_types`, `ami_type`, `capacity_type`, `disk_size` or `subnet_ids` **forces node group replacement**; rely on `max_unavailable` and PodDisruptionBudgets.
- Renaming a group key replaces the node group.

## Cost

Driven by instance type × `desired_size` (up to `max_size`); SPOT lowers price at interruption risk. Never host the `system` group on SPOT.
