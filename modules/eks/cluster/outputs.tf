output "cluster_name" {
  description = "Cluster name (pass to eks/node-group and eks/addons)."
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "Cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "certificate_authority_data" {
  description = "Base64-encoded cluster CA certificate (public data, needed to build a kubeconfig)."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Security group EKS creates and attaches to the control plane and managed nodes."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "kubernetes_version" {
  description = "Kubernetes version of the control plane."
  value       = aws_eks_cluster.this.version
}

output "platform_version" {
  description = "EKS platform version."
  value       = aws_eks_cluster.this.platform_version
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL (for IRSA trust policies)."
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN, or null when enable_irsa is false."
  value       = one(aws_iam_openid_connect_provider.this[*].arn)
}
