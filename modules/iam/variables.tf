variable "name" {
  description = "IAM role name."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9+=,.@_-]{1,64}$", var.name))
    error_message = "name must be 1-64 chars of letters, digits and +=,.@_-."
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

variable "assume_role_services" {
  description = "AWS service principals allowed to assume the role, e.g. `lambda.amazonaws.com`."
  type        = list(string)
  default     = []
}

variable "assume_role_principal_arns" {
  description = "IAM principal ARNs allowed to assume the role (cross-account or role chaining)."
  type        = list(string)
  default     = []
}

variable "managed_policy_arns" {
  description = "Managed policy ARNs to attach."
  type        = list(string)
  default     = []
}

variable "inline_policies" {
  description = "Inline policies keyed by name; values are IAM policy JSON documents (build with aws_iam_policy_document)."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for p in values(var.inline_policies) : can(jsondecode(p))])
    error_message = "Every inline policy must be valid JSON."
  }
}

variable "create_instance_profile" {
  description = "Also create an instance profile for the role (EC2 / Auto Scaling)."
  type        = bool
  default     = false
}

variable "permissions_boundary_arn" {
  description = "Permissions boundary policy ARN."
  type        = string
  default     = null
}

variable "path" {
  description = "IAM path for the role."
  type        = string
  default     = "/"
}

variable "max_session_duration" {
  description = "Maximum session duration in seconds."
  type        = number
  default     = 3600

  validation {
    condition     = var.max_session_duration >= 3600 && var.max_session_duration <= 43200
    error_message = "max_session_duration must be between 3600 and 43200."
  }
}
