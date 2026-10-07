variable "name" {
  description = "Name prefix for all VPC resources, e.g. `payments-dev`."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,28}[a-z0-9]$", var.name))
    error_message = "name must be 3-30 chars, lowercase alphanumerics and hyphens, starting with a letter."
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

variable "cidr_block" {
  description = "IPv4 CIDR of the VPC."
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr_block, 0))
    error_message = "cidr_block must be a valid IPv4 CIDR."
  }
}

variable "availability_zones" {
  description = "Availability zones to spread subnets across. Order defines subnet index."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 2 && length(distinct(var.availability_zones)) == length(var.availability_zones)
    error_message = "Provide at least 2 distinct availability zones."
  }
}

variable "public_subnet_cidrs" {
  description = "One public subnet CIDR per availability zone. Empty list creates no public tier and no internet gateway."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.public_subnet_cidrs : can(cidrhost(c, 0))])
    error_message = "All public_subnet_cidrs must be valid CIDRs."
  }
}

variable "private_subnet_cidrs" {
  description = "One private subnet CIDR per availability zone."
  type        = list(string)

  validation {
    condition     = alltrue([for c in var.private_subnet_cidrs : can(cidrhost(c, 0))])
    error_message = "All private_subnet_cidrs must be valid CIDRs."
  }
}

variable "nat_gateway_mode" {
  description = "NAT strategy: `none` (no egress, rely on VPC endpoints), `single` (one NAT, cheapest, AZ SPOF), `per_az` (one NAT per AZ, highest availability)."
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "single", "per_az"], var.nat_gateway_mode)
    error_message = "nat_gateway_mode must be one of: none, single, per_az."
  }
}

variable "enable_s3_gateway_endpoint" {
  description = "Create a free S3 gateway endpoint attached to the private route tables."
  type        = bool
  default     = true
}

variable "public_subnet_tags" {
  description = "Extra tags for public subnets, e.g. `kubernetes.io/role/elb`."
  type        = map(string)
  default     = {}
}

variable "private_subnet_tags" {
  description = "Extra tags for private subnets, e.g. `kubernetes.io/role/internal-elb`."
  type        = map(string)
  default     = {}
}
