variable "name" {
  description = "Domain name of the hosted zone, for example example.com. It is also the value of the Name tag."
  type        = string

  validation {
    condition     = can(regex("^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,63}$", var.name))
    error_message = "name must be a valid domain name, for example example.com."
  }
}

variable "comment" {
  description = "Free-text comment of the hosted zone."
  type        = string
  default     = "Managed by Terraform"
  nullable    = false
}

variable "vpc_ids" {
  description = "VPCs the zone is attached to. Empty makes a public zone; one or more make a private zone resolved only inside those VPCs."
  type        = list(string)
  default     = []
  nullable    = false

  validation {
    condition     = alltrue([for id in var.vpc_ids : can(regex("^vpc-[0-9a-f]+$", id))])
    error_message = "Every vpc_ids entry must be a VPC ID (vpc-...)."
  }
}

variable "force_destroy" {
  description = "Allow destroying a zone that still has records. Keep false outside of dev."
  type        = bool
  default     = false
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
