variable "name" {
  description = "Value of the Name tag of the certificate."
  type        = string

  validation {
    condition     = length(trimspace(var.name)) > 0
    error_message = "name must not be empty."
  }
}

variable "domain_name" {
  description = "Main domain of the certificate. A wildcard (*.example.com) is allowed."
  type        = string

  validation {
    condition     = can(regex("^(\\*\\.)?([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,63}$", var.domain_name))
    error_message = "domain_name must be a valid domain name, optionally starting with *."
  }
}

variable "subject_alternative_names" {
  description = "Other domains the certificate covers (wildcards allowed)."
  type        = list(string)
  default     = []
  nullable    = false

  validation {
    condition     = alltrue([for san in var.subject_alternative_names : can(regex("^(\\*\\.)?([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,63}$", san))])
    error_message = "Every subject alternative name must be a valid domain name, optionally starting with *."
  }
}

variable "zone_id" {
  description = "Route 53 hosted zone where the DNS validation records are created; the module then waits until the certificate is issued. Null creates no records and does not wait: validate with the domain_validation_records output (a zone in another account, for example)."
  type        = string
  default     = null

  validation {
    condition     = var.zone_id == null ? true : can(regex("^Z[A-Z0-9]{1,31}$", var.zone_id))
    error_message = "zone_id must be a Route 53 hosted zone ID (Z followed by letters and numbers)."
  }
}

variable "key_algorithm" {
  description = "Key algorithm of the certificate."
  type        = string
  default     = "RSA_2048"
  nullable    = false

  validation {
    condition     = contains(["RSA_2048", "RSA_3072", "RSA_4096", "EC_prime256v1", "EC_secp384r1"], var.key_algorithm)
    error_message = "key_algorithm must be RSA_2048, RSA_3072, RSA_4096, EC_prime256v1 or EC_secp384r1."
  }
}

variable "validation_timeout" {
  description = "How long to wait for the certificate to be issued (a number and s, m or h). Only used when zone_id is set."
  type        = string
  default     = "45m"
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]+[smh]$", var.validation_timeout))
    error_message = "validation_timeout must be a number followed by s, m or h, for example 45m."
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
