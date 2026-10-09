variable "name" {
  description = "Security group name prefix; Terraform appends a unique suffix so replacement can create-before-destroy."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,60}$", var.name))
    error_message = "name must be lowercase alphanumerics and hyphens, starting with a letter."
  }
}

variable "description" {
  description = "Purpose of the security group. Immutable: changing it replaces the group."
  type        = string
}

variable "vpc_id" {
  description = "VPC the security group belongs to."
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

variable "ingress_rules" {
  description = "Ingress rules keyed by a stable name. `port` sets from_port and to_port at once. Exactly one source per rule: cidr_ipv4 (a CIDR, or \"vpc\" for vpc_cidr_block), source_sg (a key of source_security_groups), referenced_security_group_id or prefix_list_id."
  type = map(object({
    description                  = string
    protocol                     = optional(string, "tcp")
    port                         = optional(number)
    from_port                    = optional(number)
    to_port                      = optional(number)
    cidr_ipv4                    = optional(string)
    source_sg                    = optional(string)
    referenced_security_group_id = optional(string)
    prefix_list_id               = optional(string)
  }))
  default = {}

  validation {
    condition = alltrue([
      for r in values(var.ingress_rules) :
      length([for s in [r.cidr_ipv4, r.source_sg, r.referenced_security_group_id, r.prefix_list_id] : s if s != null]) == 1
    ])
    error_message = "Each ingress rule needs exactly one source: cidr_ipv4, source_sg, referenced_security_group_id or prefix_list_id."
  }

  validation {
    condition     = alltrue([for r in values(var.ingress_rules) : contains(["tcp", "udp", "icmp", "-1"], r.protocol)])
    error_message = "protocol must be one of: tcp, udp, icmp, -1."
  }

  validation {
    condition = alltrue([
      for r in values(var.ingress_rules) :
      r.protocol == "-1" || r.port != null || (r.from_port != null && r.to_port != null && r.from_port <= r.to_port)
    ])
    error_message = "port (or from_port <= to_port) is required unless protocol is -1."
  }

  validation {
    condition     = alltrue([for r in values(var.ingress_rules) : r.cidr_ipv4 == null ? true : r.cidr_ipv4 == "vpc" || can(cidrhost(r.cidr_ipv4, 0))])
    error_message = "cidr_ipv4 must be a valid IPv4 CIDR, or \"vpc\"."
  }

  validation {
    condition     = alltrue([for r in values(var.ingress_rules) : r.source_sg == null ? true : contains(keys(var.source_security_groups), r.source_sg)])
    error_message = "source_sg must be a key of source_security_groups."
  }
}

variable "allow_public_ingress" {
  description = "Permit 0.0.0.0/0 as an ingress source. Only for internet-facing load balancers, never nodes or databases."
  type        = bool
  default     = false
}

variable "egress_rules" {
  description = "Egress rules keyed by a stable name; same shape and same ways to name the destination as ingress_rules."
  type = map(object({
    description                  = string
    protocol                     = optional(string, "tcp")
    port                         = optional(number)
    from_port                    = optional(number)
    to_port                      = optional(number)
    cidr_ipv4                    = optional(string)
    source_sg                    = optional(string)
    referenced_security_group_id = optional(string)
    prefix_list_id               = optional(string)
  }))
  default = {}

  validation {
    condition = alltrue([
      for r in values(var.egress_rules) :
      length([for s in [r.cidr_ipv4, r.source_sg, r.referenced_security_group_id, r.prefix_list_id] : s if s != null]) == 1
    ])
    error_message = "Each egress rule needs exactly one destination: cidr_ipv4, source_sg, referenced_security_group_id or prefix_list_id."
  }

  validation {
    condition = alltrue([
      for r in values(var.egress_rules) :
      r.protocol == "-1" || r.port != null || (r.from_port != null && r.to_port != null && r.from_port <= r.to_port)
    ])
    error_message = "port (or from_port <= to_port) is required unless protocol is -1."
  }

  validation {
    condition     = alltrue([for r in values(var.egress_rules) : r.source_sg == null ? true : contains(keys(var.source_security_groups), r.source_sg)])
    error_message = "source_sg must be a key of source_security_groups."
  }
}

variable "allow_all_egress" {
  description = "Add an allow-all egress rule. Default false (least privilege): list required egress in egress_rules."
  type        = bool
  default     = false
}

variable "vpc_cidr_block" {
  description = "CIDR of the VPC. A rule with cidr_ipv4 = \"vpc\" uses it."
  type        = string
  default     = null
}

variable "source_security_groups" {
  description = "Security group IDs a rule can name with source_sg, keyed by the name the rule uses (for example { alb = module.alb_sg.security_group_id })."
  type        = map(string)
  default     = {}
}
