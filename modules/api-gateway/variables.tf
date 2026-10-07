variable "name" {
  description = "HTTP API name."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,62}$", var.name))
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

variable "description" {
  description = "API description."
  type        = string
  default     = null
}


variable "vpc_link" {
  description = "VPC Link V2 for private integrations (API Gateway -> internal NLB/ALB). Required when any route uses integration_type `vpc_link`. This is NOT a VPC endpoint."
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "routes" {
  description = "Routes keyed by logical name. `lambda` routes need lambda_function_name and lambda_invoke_arn; `vpc_link` routes need listener_arn (NLB/ALB listener ARN)."
  type = map(object({
    route_key            = string
    integration_type     = string
    lambda_function_name = optional(string)
    lambda_invoke_arn    = optional(string)
    listener_arn         = optional(string)
    timeout_ms           = optional(number, 29000)
  }))

  validation {
    condition     = alltrue([for r in values(var.routes) : contains(["lambda", "vpc_link"], r.integration_type)])
    error_message = "integration_type must be `lambda` or `vpc_link`."
  }

  validation {
    condition     = alltrue([for r in values(var.routes) : r.integration_type != "lambda" || (r.lambda_function_name != null && r.lambda_invoke_arn != null)])
    error_message = "lambda routes require lambda_function_name and lambda_invoke_arn."
  }

  validation {
    condition     = alltrue([for r in values(var.routes) : r.integration_type != "vpc_link" || r.listener_arn != null])
    error_message = "vpc_link routes require listener_arn."
  }

  validation {
    condition     = alltrue([for r in values(var.routes) : r.timeout_ms >= 50 && r.timeout_ms <= 30000])
    error_message = "timeout_ms must be between 50 and 30000 for HTTP APIs."
  }

  validation {
    condition     = alltrue([for r in values(var.routes) : can(regex("^(ANY|GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /|^\\$default$", r.route_key))])
    error_message = "route_key must be `METHOD /path` or `$default`."
  }
}

variable "stage_name" {
  description = "Stage name. `$default` serves from the root URL."
  type        = string
  default     = "$default"
}

variable "throttling_burst_limit" {
  description = "Default route burst limit."
  type        = number
  default     = 100
}

variable "throttling_rate_limit" {
  description = "Default route steady-state requests per second."
  type        = number
  default     = 50
}

variable "access_log_retention_days" {
  description = "Retention of the access log group in days."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.access_log_retention_days)
    error_message = "access_log_retention_days must be a value supported by CloudWatch Logs."
  }
}

variable "cors" {
  description = "CORS configuration. Null disables CORS handling at the gateway."
  type = object({
    allow_origins = list(string)
    allow_methods = list(string)
    allow_headers = optional(list(string), [])
    max_age       = optional(number, 300)
  })
  default = null
}
