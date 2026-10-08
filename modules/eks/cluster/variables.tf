variable "name" {
  description = "EKS cluster name."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,98}[a-z0-9]$", var.name))
    error_message = "name must be lowercase alphanumerics and hyphens, starting with a letter."
  }
}

variable "tags" {
  description = "Mandatory tags (environment, owner, cost_center, project) applied to every taggable resource. See docs/module-standard.md."
  type = object({
    environment = string
    owner       = string
    cost_center = string
    project     = string
  })

  validation {
    condition     = contains(["dev", "staging", "prod"], var.tags.environment)
    error_message = "tags.environment must be one of: dev, staging, prod."
  }

  validation {
    condition     = alltrue([for v in values(var.tags) : length(trimspace(v)) > 0])
    error_message = "All mandatory tag values must be non-empty."
  }
}

variable "extra_tags" {
  description = "Extra tags merged with the mandatory tags; the mandatory tags win on key conflicts."
  type        = map(string)
  default     = {}
}

variable "kubernetes_version" {
  description = "Kubernetes minor version, e.g. `1.31`. No default: choose a version currently in standard support. Upgrade one minor at a time."
  type        = string

  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "kubernetes_version must look like `1.31`."
  }
}

variable "cluster_role_arn" {
  description = "Cluster IAM role ARN (modules/iam trusting `eks.amazonaws.com` with AmazonEKSClusterPolicy). Make the caller depend on the policy attachment so it outlives the cluster on destroy."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the control-plane ENIs and nodes."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least 2 subnets in different availability zones."
  }
}

variable "additional_security_group_ids" {
  description = "Extra security groups attached to the control-plane ENIs (EKS also creates its own cluster security group)."
  type        = list(string)
  default     = []
}

variable "endpoint_private_access" {
  description = "Enable the private API endpoint (reachable from inside the VPC)."
  type        = bool
  default     = true
}

variable "endpoint_public_access" {
  description = "Enable the public API endpoint. Outside `dev` it requires explicit public_access_cidrs (never 0.0.0.0/0)."
  type        = bool
  default     = false
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the public endpoint. Empty means AWS default (0.0.0.0/0)."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.public_access_cidrs : can(cidrhost(c, 0))])
    error_message = "public_access_cidrs must be valid IPv4 CIDRs."
  }
}

variable "authentication_mode" {
  description = "`API` (access entries, recommended), `API_AND_CONFIG_MAP` (migration) or `CONFIG_MAP` (legacy aws-auth)."
  type        = string
  default     = "API"

  validation {
    condition     = contains(["API", "API_AND_CONFIG_MAP", "CONFIG_MAP"], var.authentication_mode)
    error_message = "authentication_mode must be API, API_AND_CONFIG_MAP or CONFIG_MAP."
  }
}

variable "bootstrap_cluster_creator_admin" {
  description = "Grant the identity that creates the cluster admin access. Keep true unless an access entry for your admins already exists, to avoid lock-out. Immutable after creation."
  type        = bool
  default     = true
}

variable "access_entries" {
  description = "Access entries keyed by logical name: IAM principals mapped to Kubernetes access via AWS-managed access policies. Requires authentication_mode API or API_AND_CONFIG_MAP."
  type = map(object({
    principal_arn     = string
    type              = optional(string, "STANDARD")
    kubernetes_groups = optional(list(string), [])
    policies = optional(map(object({
      policy_arn = string
      scope      = optional(string, "cluster")
      namespaces = optional(list(string), [])
    })), {})
  }))
  default = {}

  validation {
    condition     = alltrue([for e in values(var.access_entries) : alltrue([for p in values(e.policies) : contains(["cluster", "namespace"], p.scope)])])
    error_message = "policy scope must be `cluster` or `namespace`."
  }

  validation {
    condition     = alltrue([for e in values(var.access_entries) : alltrue([for p in values(e.policies) : p.scope != "namespace" || length(p.namespaces) > 0])])
    error_message = "namespace-scoped policies need at least one namespace."
  }
}

variable "enabled_log_types" {
  description = "Control-plane log types sent to CloudWatch Logs."
  type        = list(string)
  default     = ["api", "audit", "authenticator"]

  validation {
    condition     = alltrue([for t in var.enabled_log_types : contains(["api", "audit", "authenticator", "controllerManager", "scheduler"], t)])
    error_message = "Log types must be api, audit, authenticator, controllerManager or scheduler."
  }
}

variable "secrets_kms_key_arn" {
  description = "KMS key ARN for Kubernetes secrets envelope encryption. Null leaves secrets with the default EKS encryption. Immutable once enabled."
  type        = string
  default     = null
}

variable "service_ipv4_cidr" {
  description = "Kubernetes service CIDR. Null lets EKS choose (10.100.0.0/16 or 172.20.0.0/16). Immutable."
  type        = string
  default     = null

  validation {
    condition     = var.service_ipv4_cidr == null ? true : can(cidrhost(var.service_ipv4_cidr, 0))
    error_message = "service_ipv4_cidr must be a valid IPv4 CIDR."
  }
}

variable "support_type" {
  description = "`STANDARD` or `EXTENDED` (paid) Kubernetes version support."
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "EXTENDED"], var.support_type)
    error_message = "support_type must be STANDARD or EXTENDED."
  }
}

variable "enable_irsa" {
  description = "Create the IAM OIDC provider so pods can assume IAM roles (IRSA)."
  type        = bool
  default     = true
}
