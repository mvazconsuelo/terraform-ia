# modules/eks/addons

EKS managed add-ons, installed only when listed. Versions default to what EKS recommends for the cluster's Kubernetes version, or can be pinned.
**Non-goals:** self-managed controllers (AWS Load Balancer Controller, Karpenter, cluster-autoscaler: Helm in the composition), IAM roles for add-ons (`modules/iam` + the cluster's OIDC provider), the cluster itself.

## Usage

```hcl
module "addons" {
  source = "../../../modules/eks/addons"

  cluster_name = module.eks.cluster_name
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "shop" }

  addons = {
    vpc-cni                = {}
    kube-proxy             = {}
    coredns                = { version = "v1.11.3-eksbuild.1" }
    eks-pod-identity-agent = {}
    aws-ebs-csi-driver     = { service_account_role_arn = module.ebs_csi_role.role_arn }
  }

  depends_on = [module.node_groups]   # coredns and the CSI driver need nodes to become ACTIVE
}
```

## Resources and tags

`aws_eks_addon` (taggable, tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`).

## Inputs

`cluster_name`, `tags`, `extra_tags`, `addons` keyed by add-on name: `version` (null = EKS default; format `v1.18.5-eksbuild.1`), `service_account_role_arn`, `configuration_values` (JSON), `resolve_conflicts_on_create` (`OVERWRITE`), `resolve_conflicts_on_update` (`PRESERVE`, keeps your manual customisations). At least one add-on is required.

## Outputs

`addon_arns`, `addon_versions` (by add-on name).

## Lifecycle

- Upgrade add-ons after the control plane upgrade; pin `version` in production so a Kubernetes bump does not silently move add-on versions.
- Removing a key uninstalls the add-on (and for `vpc-cni`/`coredns`/`kube-proxy` breaks cluster networking/DNS): review plans.
- `PRESERVE` on update keeps fields you changed outside Terraform; use `OVERWRITE` to force the declared configuration.
- Which add-ons to install is a workload decision: do not add every add-on automatically.

## Cost

Core add-ons are free; some (e.g. certain observability/security add-ons from the AWS Marketplace) bill separately; the pods they run use node capacity.
