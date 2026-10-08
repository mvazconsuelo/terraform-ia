variable "name" {
  description = "Name prefix; each instance is named `<name>-<key>`."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}$", var.name))
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

variable "launch_template_id" {
  description = "Launch template (modules/ec2/launch-template) holding the hardened instance configuration."
  type        = string
}

variable "launch_template_version" {
  description = "Template version. `$Default` avoids replacing instances whenever the template changes; pin a number to control rollouts."
  type        = string
  default     = "$Default"
}

variable "instances" {
  description = "Instances keyed by a stable logical name. Per-instance values override the launch template."
  type = map(object({
    subnet_id          = string
    instance_type      = optional(string)
    private_ip         = optional(string)
    security_group_ids = optional(list(string))
    data_volumes = optional(map(object({
      device_name = string
      size_gb     = number
      type        = optional(string, "gp3")
      iops        = optional(number)
      throughput  = optional(number)
    })), {})
  }))

  validation {
    condition     = length(var.instances) > 0
    error_message = "Provide at least one instance."
  }

  validation {
    condition     = alltrue([for i in values(var.instances) : i.private_ip == null ? true : can(regex("^[0-9]{1,3}(\\.[0-9]{1,3}){3}$", i.private_ip))])
    error_message = "private_ip must be an IPv4 address."
  }

  validation {
    condition     = alltrue([for i in values(var.instances) : alltrue([for v in values(i.data_volumes) : v.size_gb >= 1 && contains(["gp3", "gp2", "io1", "io2", "st1", "sc1"], v.type)])])
    error_message = "Data volumes need size_gb >= 1 and type gp3, gp2, io1, io2, st1 or sc1."
  }

  validation {
    condition     = alltrue([for k in keys(var.instances) : can(regex("^[a-z0-9][a-z0-9-]{0,30}$", k))])
    error_message = "Instance keys must be lowercase alphanumerics/hyphens, max 31 chars."
  }
}

variable "termination_protection" {
  description = "Enable API termination protection on every instance."
  type        = bool
  default     = false
}

variable "kms_key_id" {
  description = "KMS key ARN for data volume encryption. Null uses the AWS-managed aws/ebs key. Data volumes are always encrypted."
  type        = string
  default     = null
}
