variable "name" {
  description = "Load balancer name (max 32 chars). Target group names are `<name>-<key>`."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,22}[a-z0-9]$", var.name))
    error_message = "name must be 2-24 chars: lowercase alphanumerics and hyphens (leaves room for target group suffixes)."
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

variable "vpc_id" {
  description = "VPC for the target groups."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for the load balancer (private subnets when internal)."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least 2 subnets in different availability zones."
  }
}

variable "internal" {
  description = "Internal (private) load balancer. Set false only for deliberate internet-facing exposure."
  type        = bool
  default     = true
}

variable "security_group_ids" {
  description = "Security groups for the NLB (recommended; restricts who can reach listeners)."
  type        = list(string)
  default     = []
}

variable "enable_deletion_protection" {
  description = "Protect the load balancer from deletion."
  type        = bool
  default     = true
}

variable "enable_cross_zone_load_balancing" {
  description = "Cross-zone load balancing. Improves distribution but adds inter-AZ data charges."
  type        = bool
  default     = false
}

variable "target_groups" {
  description = "Target groups keyed by logical name."
  type = map(object({
    port                  = number
    protocol              = optional(string, "TCP")
    target_type           = optional(string, "ip")
    deregistration_delay  = optional(number, 30)
    health_check_protocol = optional(string, "TCP")
    health_check_port     = optional(string, "traffic-port")
    health_check_path     = optional(string)
  }))

  validation {
    condition     = alltrue([for t in values(var.target_groups) : contains(["instance", "ip", "alb"], t.target_type)])
    error_message = "target_type must be instance, ip or alb."
  }

  validation {
    condition     = alltrue([for t in values(var.target_groups) : contains(["TCP", "TLS", "UDP", "TCP_UDP"], t.protocol)])
    error_message = "protocol must be TCP, TLS, UDP or TCP_UDP."
  }

  validation {
    condition     = alltrue([for t in values(var.target_groups) : t.port >= 1 && t.port <= 65535])
    error_message = "port must be 1-65535."
  }

  validation {
    condition     = alltrue([for t in values(var.target_groups) : contains(["TCP", "HTTP", "HTTPS"], t.health_check_protocol)])
    error_message = "health_check_protocol must be TCP, HTTP or HTTPS."
  }
}

variable "listeners" {
  description = "Listeners keyed by logical name, forwarding to a key of target_groups."
  type = map(object({
    port            = number
    protocol        = optional(string, "TCP")
    target_group    = string
    certificate_arn = optional(string)
    ssl_policy      = optional(string, "ELBSecurityPolicy-TLS13-1-2-2021-06")
  }))
  default = {}

  validation {
    condition     = alltrue([for l in values(var.listeners) : contains(["TCP", "TLS", "UDP", "TCP_UDP"], l.protocol)])
    error_message = "Listener protocol must be TCP, TLS, UDP or TCP_UDP."
  }

  validation {
    condition     = alltrue([for l in values(var.listeners) : l.protocol != "TLS" || l.certificate_arn != null])
    error_message = "TLS listeners require certificate_arn."
  }
}
