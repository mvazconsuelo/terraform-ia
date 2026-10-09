# modules/eks/cluster

EKS control plane: private API endpoint by default, access entries (no `aws-auth` ConfigMap), control-plane logging, optional secrets envelope encryption and an IRSA OIDC provider.
**Non-goals:** worker nodes (`eks/node-group`), add-ons (`eks/addons`), the cluster IAM role (`modules/iam`), VPC (`modules/vpc`), Kubernetes resources (Helm/kubectl providers belong to the composition).

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
# ---------- cluster_role ----------
cluster_role:
  name: "${project}-${environment}-eks"
  assume_role_services:
    - eks.amazonaws.com
  managed_policy_arns:
    - arn:aws:iam::aws:policy/AmazonEKSClusterPolicy

# ---------- eks ----------
eks:
  name: "${project}-${environment}"
  kubernetes_version: "1.31"        # choose a version in standard support
  access_entries:
    admins:
      principal_arn: arn:aws:iam::111122223333:role/platform-admins
      policies:
        admin:
          policy_arn: arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy
```

```hcl
module "cluster_role" {
  source = "../../../modules/iam"

  name                 = templatestring(local.inputs.cluster_role.name, local.tags)
  assume_role_services = local.inputs.cluster_role.assume_role_services
  managed_policy_arns  = local.inputs.cluster_role.managed_policy_arns
  tags                 = local.tags
}

module "eks" {
  source = "../../../modules/eks/cluster"

  name               = templatestring(local.inputs.eks.name, local.tags)
  kubernetes_version = local.inputs.eks.kubernetes_version
  access_entries     = local.inputs.eks.access_entries
  tags               = local.tags
  cluster_role_arn   = module.cluster_role.role_arn
  subnet_ids         = module.vpc.private_subnet_ids

  depends_on = [module.cluster_role]
}
```

## Resources and tags

`aws_eks_cluster`, `aws_iam_openid_connect_provider` and `aws_eks_access_entry` (taggable, tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`); `aws_eks_access_policy_association` is not taggable.

## Inputs

| Name | Default | Notes |
|---|---|---|
| `name`, `kubernetes_version`, `cluster_role_arn`, `subnet_ids` | — | No default version on purpose; ≥ 2 subnets. |
| `tags`, `extra_tags` | — / `{}` | See module standard. |
| `endpoint_private_access` / `endpoint_public_access` | `true` / `false` | At least one must be true. Outside `dev`, public needs explicit `public_access_cidrs`, never `0.0.0.0/0` (precondition). |
| `authentication_mode` | `API` | Access entries need `API` or `API_AND_CONFIG_MAP`. |
| `bootstrap_cluster_creator_admin` | `true` | Immutable after creation; keep true unless admin entries already exist. |
| `access_entries` | `{}` | `principal_arn`, `type`, `kubernetes_groups`, `policies` (AWS access policy ARN, `cluster` or `namespace` scope). |
| `enabled_log_types` | api, audit, authenticator | Add `controllerManager`/`scheduler` when debugging (log volume = cost). |
| `secrets_kms_key_arn` | `null` | Envelope encryption of Kubernetes secrets; cannot be removed once enabled. |
| `service_ipv4_cidr`, `support_type`, `enable_irsa`, `additional_security_group_ids` | `null`, `STANDARD`, `true`, `[]` | `EXTENDED` support is paid. |

## Outputs

`cluster_name`, `cluster_arn`, `cluster_endpoint`, `certificate_authority_data`, `cluster_security_group_id`, `kubernetes_version`, `platform_version`, `oidc_issuer_url`, `oidc_provider_arn`.

## Lifecycle

- **Upgrades:** raise `kubernetes_version` one minor at a time, then upgrade node groups and add-ons (in that order: control plane → add-ons → nodes per AWS guidance). The control plane upgrade has no rollback.
- **Replacement (destroys the cluster and its workloads):** changing `name`, `cluster_role_arn`, `subnet_ids` to a different VPC, `service_ipv4_cidr` or enabling/changing encryption. Always read the plan.
- `bootstrap_cluster_creator_admin` is in `ignore_changes`.
- Destroy order: node groups and add-ons first; keep the IAM role's policy attachment alive until the cluster is gone (`depends_on` in the composition).

## Cost

Control plane hourly fee per cluster (extended support costs more) + CloudWatch Logs ingestion for enabled log types. Nodes are billed separately (`eks/node-group`).
