variable "cluster_name" {
  description = "Name of the EKS cluster the add-ons belong to."
  type        = string
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
    condition     = can(regex("^[a-z][a-z0-9-]{1,19}$", var.tags.environment))
    error_message = "tags.environment must be 2 to 20 characters: lowercase letters, numbers and hyphens, starting with a letter."
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

variable "addons" {
  description = "Managed add-ons keyed by add-on name (`vpc-cni`, `coredns`, `kube-proxy`, `aws-ebs-csi-driver`, `eks-pod-identity-agent`, ...). Only what you list is installed. A null version lets EKS install the default version for the cluster's Kubernetes version."
  type = map(object({
    version                     = optional(string)
    service_account_role_arn    = optional(string)
    configuration_values        = optional(string)
    resolve_conflicts_on_create = optional(string, "OVERWRITE")
    resolve_conflicts_on_update = optional(string, "PRESERVE")
  }))

  validation {
    condition     = length(var.addons) > 0
    error_message = "List at least one add-on."
  }

  validation {
    condition     = alltrue([for a in values(var.addons) : contains(["NONE", "OVERWRITE"], a.resolve_conflicts_on_create)])
    error_message = "resolve_conflicts_on_create must be NONE or OVERWRITE."
  }

  validation {
    condition     = alltrue([for a in values(var.addons) : contains(["NONE", "OVERWRITE", "PRESERVE"], a.resolve_conflicts_on_update)])
    error_message = "resolve_conflicts_on_update must be NONE, OVERWRITE or PRESERVE."
  }

  validation {
    condition     = alltrue([for a in values(var.addons) : a.configuration_values == null ? true : can(jsondecode(a.configuration_values))])
    error_message = "configuration_values must be valid JSON."
  }

  validation {
    condition     = alltrue([for a in values(var.addons) : a.version == null ? true : can(regex("^v[0-9]+\\.[0-9]+\\.[0-9]+-eksbuild\\.[0-9]+$", a.version))])
    error_message = "version must look like `v1.18.5-eksbuild.1`."
  }
}
