variable "cluster_name" {
  description = "Name of the EKS cluster the node groups join."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for physical node group names; the group key is appended."
  type        = string
  default     = null
}

variable "node_role_arn" {
  description = "IAM role ARN assumed by the nodes. Must have the standard worker-node managed policies."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs the nodes are launched into."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least 2 subnets for availability."
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

variable "groups" {
  description = "EKS managed node groups keyed by logical name (e.g. system, workloads)."
  type = map(object({
    instance_types = list(string)
    capacity_type  = optional(string, "ON_DEMAND")
    ami_type       = optional(string, "AL2023_x86_64_STANDARD")
    disk_size_gb   = optional(number, 50)

    min_size     = number
    desired_size = number
    max_size     = number

    max_unavailable = optional(number, 1)
    labels          = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = optional(string)
      effect = string
    })), [])
  }))

  validation {
    condition     = length(var.groups) > 0
    error_message = "At least one node group is required."
  }

  validation {
    condition     = alltrue([for g in values(var.groups) : contains(["ON_DEMAND", "SPOT"], g.capacity_type)])
    error_message = "capacity_type must be ON_DEMAND or SPOT."
  }

  validation {
    condition     = alltrue([for g in values(var.groups) : g.min_size <= g.desired_size && g.desired_size <= g.max_size && g.min_size >= 0 && g.max_size >= 1])
    error_message = "Each group must satisfy 0 <= min_size <= desired_size <= max_size and max_size >= 1."
  }

  validation {
    condition     = alltrue([for g in values(var.groups) : length(g.instance_types) > 0])
    error_message = "Each group needs at least one instance type."
  }

  validation {
    condition     = alltrue([for g in values(var.groups) : g.capacity_type != "SPOT" || length(g.instance_types) >= 2])
    error_message = "SPOT groups should list at least 2 instance types to reduce interruption risk."
  }

  validation {
    condition     = alltrue([for g in values(var.groups) : alltrue([for t in g.taints : contains(["NO_SCHEDULE", "NO_EXECUTE", "PREFER_NO_SCHEDULE"], t.effect)])])
    error_message = "Taint effect must be NO_SCHEDULE, NO_EXECUTE or PREFER_NO_SCHEDULE."
  }

  validation {
    condition     = alltrue([for k in keys(var.groups) : can(regex("^[a-z][a-z0-9-]{0,30}$", k))])
    error_message = "Group keys must be lowercase alphanumerics/hyphens, max 31 chars."
  }
}
