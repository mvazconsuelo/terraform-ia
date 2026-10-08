variable "name" {
  description = "Auto Scaling Group name prefix."
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

variable "subnet_ids" {
  description = "Private subnet IDs the instances launch into (one or more AZs)."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 1
    error_message = "Provide at least one subnet."
  }
}

variable "launch_template_id" {
  description = "Launch template ID (modules/ec2/launch-template)."
  type        = string
}

variable "launch_template_version" {
  description = "Launch template version. Pass the launch-template module's `latest_version` output so a template change triggers an instance refresh."
  type        = string
}

variable "min_size" {
  description = "Minimum number of instances."
  type        = number
}

variable "desired_size" {
  description = "Initial desired number of instances. Ignored after creation (scaling policies own it)."
  type        = number
}

variable "max_size" {
  description = "Maximum number of instances."
  type        = number

  validation {
    condition     = var.max_size >= 1 && var.min_size >= 0 && var.min_size <= var.desired_size && var.desired_size <= var.max_size
    error_message = "Sizes must satisfy 0 <= min_size <= desired_size <= max_size and max_size >= 1."
  }
}

variable "target_group_arns" {
  description = "Load balancer target groups to register instances with (e.g. from modules/nlb)."
  type        = list(string)
  default     = []
}

variable "health_check_type" {
  description = "`EC2` or `ELB`. Use ELB behind a load balancer so unhealthy targets are replaced."
  type        = string
  default     = "EC2"

  validation {
    condition     = contains(["EC2", "ELB"], var.health_check_type)
    error_message = "health_check_type must be EC2 or ELB."
  }
}

variable "health_check_grace_period" {
  description = "Seconds before health checks start after launch."
  type        = number
  default     = 300
}

variable "mixed_instances" {
  description = "Mixed instances policy: several instance types and an On-Demand/Spot split. Null uses the template's instance type. Do not combine with `use_spot` on the launch template."
  type = object({
    instance_types                           = list(string)
    on_demand_base_capacity                  = optional(number, 0)
    on_demand_percentage_above_base_capacity = optional(number, 100)
  })
  default = null

  validation {
    condition     = var.mixed_instances == null ? true : length(var.mixed_instances.instance_types) >= 1
    error_message = "mixed_instances needs at least one instance type."
  }

  validation {
    condition     = var.mixed_instances == null ? true : (var.mixed_instances.on_demand_percentage_above_base_capacity >= 0 && var.mixed_instances.on_demand_percentage_above_base_capacity <= 100)
    error_message = "on_demand_percentage_above_base_capacity must be 0-100."
  }
}

variable "scaling_policies" {
  description = "Target-tracking scaling policies keyed by name. `ALBRequestCountPerTarget` needs `resource_label`."
  type = map(object({
    predefined_metric = string
    target_value      = number
    resource_label    = optional(string)
    warmup_seconds    = optional(number, 300)
  }))
  default = {}

  validation {
    condition     = alltrue([for p in values(var.scaling_policies) : contains(["ASGAverageCPUUtilization", "ASGAverageNetworkIn", "ASGAverageNetworkOut", "ALBRequestCountPerTarget"], p.predefined_metric)])
    error_message = "predefined_metric must be ASGAverageCPUUtilization, ASGAverageNetworkIn, ASGAverageNetworkOut or ALBRequestCountPerTarget."
  }

  validation {
    condition     = alltrue([for p in values(var.scaling_policies) : p.predefined_metric != "ALBRequestCountPerTarget" || p.resource_label != null])
    error_message = "ALBRequestCountPerTarget requires resource_label."
  }
}

variable "scheduled_actions" {
  description = "Scheduled capacity changes keyed by name. Omitted sizes stay unchanged."
  type = map(object({
    recurrence   = string
    min_size     = optional(number, -1)
    max_size     = optional(number, -1)
    desired_size = optional(number, -1)
    time_zone    = optional(string, "UTC")
  }))
  default = {}
}

variable "enable_instance_refresh" {
  description = "Roll instances automatically when the launch template version changes."
  type        = bool
  default     = true
}

variable "instance_refresh_min_healthy_percentage" {
  description = "Minimum healthy percentage during instance refresh."
  type        = number
  default     = 90

  validation {
    condition     = var.instance_refresh_min_healthy_percentage >= 0 && var.instance_refresh_min_healthy_percentage <= 100
    error_message = "Must be 0-100."
  }
}
