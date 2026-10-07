variable "name" {
  description = "Name prefix for the bus and rules."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}$", var.name))
    error_message = "name must be lowercase alphanumerics and hyphens, starting with a letter."
  }
}

variable "tags" {
  description = "Mandatory tags (environment, owner, cost_center, project) applied to every taggable resource. See the module standard in the root README.md."
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

variable "create_bus" {
  description = "Create a custom event bus named `name`. False uses the account's default bus (required for schedule rules)."
  type        = bool
  default     = false
}

variable "rules" {
  description = "Rules keyed by logical name. Each needs a schedule_expression and/or an event_pattern (JSON string), and at least one target."
  type = map(object({
    description         = optional(string)
    schedule_expression = optional(string)
    event_pattern       = optional(string)
    enabled             = optional(bool, true)
    targets = map(object({
      arn                   = string
      role_arn              = optional(string)
      input                 = optional(string)
      dead_letter_arn       = optional(string)
      lambda_function_name  = optional(string)
      retry_attempts        = optional(number, 2)
      max_event_age_seconds = optional(number, 3600)
    }))
  }))

  validation {
    condition     = alltrue([for r in values(var.rules) : r.schedule_expression != null || r.event_pattern != null])
    error_message = "Each rule needs schedule_expression and/or event_pattern."
  }

  validation {
    condition     = alltrue([for r in values(var.rules) : r.event_pattern == null ? true : can(jsondecode(r.event_pattern))])
    error_message = "event_pattern must be valid JSON."
  }

  validation {
    condition     = alltrue([for r in values(var.rules) : r.schedule_expression == null ? true : can(regex("^(rate|cron)\\(.+\\)$", r.schedule_expression))])
    error_message = "schedule_expression must be rate(...) or cron(...)."
  }

  validation {
    condition     = alltrue([for r in values(var.rules) : length(r.targets) > 0])
    error_message = "Each rule needs at least one target."
  }
}
