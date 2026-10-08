variable "name" {
  description = "Load balancer name (max 32 chars). Target group names are `<name>-<key>`."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,22}[a-z0-9]$", var.name))
    error_message = "name must be 2-24 chars: lowercase alphanumerics and hyphens (leaves room for target group suffixes)."
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

variable "security_group_ids" {
  description = "Security groups for the ALB (required; create with modules/security-group)."
  type        = list(string)

  validation {
    condition     = length(var.security_group_ids) >= 1
    error_message = "An ALB needs at least one security group."
  }
}

variable "internal" {
  description = "Internal (private) load balancer. Set false only for deliberate internet-facing exposure."
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Protect the load balancer from deletion."
  type        = bool
  default     = true
}

variable "idle_timeout" {
  description = "Idle timeout in seconds."
  type        = number
  default     = 60

  validation {
    condition     = var.idle_timeout >= 1 && var.idle_timeout <= 4000
    error_message = "idle_timeout must be 1-4000."
  }
}

variable "access_logs_bucket" {
  description = "S3 bucket name for access logs (modules/s3; the bucket needs the ELB log-delivery policy). Null disables access logs."
  type        = string
  default     = null
}

variable "web_acl_arn" {
  description = "WAFv2 web ACL ARN to associate with the ALB. Null for none."
  type        = string
  default     = null
}

variable "target_groups" {
  description = "Target groups keyed by logical name."
  type = map(object({
    port                 = number
    protocol             = optional(string, "HTTP")
    target_type          = optional(string, "ip")
    deregistration_delay = optional(number, 30)
    health_check = optional(object({
      path                = optional(string, "/")
      matcher             = optional(string, "200-399")
      interval            = optional(number, 30)
      healthy_threshold   = optional(number, 3)
      unhealthy_threshold = optional(number, 3)
    }), {})
  }))

  validation {
    condition     = alltrue([for t in values(var.target_groups) : contains(["instance", "ip", "lambda"], t.target_type)])
    error_message = "target_type must be instance, ip or lambda."
  }

  validation {
    condition     = alltrue([for t in values(var.target_groups) : contains(["HTTP", "HTTPS"], t.protocol)])
    error_message = "protocol must be HTTP or HTTPS."
  }

  validation {
    condition     = alltrue([for t in values(var.target_groups) : t.port >= 1 && t.port <= 65535])
    error_message = "port must be 1-65535."
  }
}

variable "listeners" {
  description = "Listeners keyed by logical name. default_action.type is `forward` (needs target_group), `redirect` or `fixed_response`."
  type = map(object({
    port            = number
    protocol        = optional(string, "HTTPS")
    certificate_arn = optional(string)
    ssl_policy      = optional(string, "ELBSecurityPolicy-TLS13-1-2-2021-06")
    default_action = object({
      type         = string
      target_group = optional(string)
      redirect = optional(object({
        port        = optional(string, "443")
        protocol    = optional(string, "HTTPS")
        status_code = optional(string, "HTTP_301")
      }))
      fixed_response = optional(object({
        status_code  = string
        content_type = optional(string, "text/plain")
        message_body = optional(string, "")
      }))
    })
  }))
  default = {}

  validation {
    condition     = alltrue([for l in values(var.listeners) : contains(["HTTP", "HTTPS"], l.protocol)])
    error_message = "Listener protocol must be HTTP or HTTPS."
  }

  validation {
    condition     = alltrue([for l in values(var.listeners) : l.protocol != "HTTPS" || l.certificate_arn != null])
    error_message = "HTTPS listeners require certificate_arn."
  }

  validation {
    condition = alltrue([for l in values(var.listeners) : (
      (l.default_action.type == "forward" && l.default_action.target_group != null) ||
      (l.default_action.type == "redirect" && l.default_action.redirect != null) ||
      (l.default_action.type == "fixed_response" && l.default_action.fixed_response != null)
    )])
    error_message = "default_action must be forward (with target_group), redirect (with redirect) or fixed_response (with fixed_response)."
  }
}

variable "rules" {
  description = "Forwarding rules keyed by logical name, attached to a key of listeners. Priorities must be unique per listener."
  type = map(object({
    listener      = string
    priority      = number
    target_group  = string
    path_patterns = optional(list(string), [])
    host_headers  = optional(list(string), [])
  }))
  default = {}

  validation {
    condition     = alltrue([for r in values(var.rules) : r.priority >= 1 && r.priority <= 50000])
    error_message = "priority must be 1-50000."
  }

  validation {
    condition     = alltrue([for r in values(var.rules) : length(r.path_patterns) + length(r.host_headers) > 0])
    error_message = "Each rule needs at least one path pattern or host header."
  }
}
