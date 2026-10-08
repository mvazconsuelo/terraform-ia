variable "function_name" {
  description = "Lambda function name."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,64}$", var.function_name))
    error_message = "function_name must be 1-64 chars of letters, digits, hyphens and underscores."
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

variable "role_arn" {
  description = "Execution role ARN (create with modules/iam; trust `lambda.amazonaws.com`)."
  type        = string
}

variable "handler" {
  description = "Function entrypoint, e.g. `index.handler`."
  type        = string
}

variable "runtime" {
  description = "Lambda runtime identifier, e.g. `python3.12` or `nodejs20.x`. Check the AWS runtime deprecation schedule."
  type        = string

  validation {
    condition     = length(var.runtime) > 0
    error_message = "runtime must not be empty."
  }
}

variable "filename" {
  description = "Path to a local deployment package (.zip). Mutually exclusive with s3_bucket/s3_key."
  type        = string
  default     = null
}

variable "source_code_hash" {
  description = "Base64 SHA256 of the package, e.g. `filebase64sha256(\"app.zip\")`, so code changes trigger updates."
  type        = string
  default     = null
}

variable "s3_bucket" {
  description = "S3 bucket holding the deployment package."
  type        = string
  default     = null
}

variable "s3_key" {
  description = "S3 key of the deployment package."
  type        = string
  default     = null
}

variable "architectures" {
  description = "Instruction set. arm64 (Graviton) is cheaper per GB-second."
  type        = list(string)
  default     = ["arm64"]

  validation {
    condition     = length(var.architectures) == 1 && contains(["arm64", "x86_64"], var.architectures[0])
    error_message = "architectures must be [\"arm64\"] or [\"x86_64\"]."
  }
}

variable "memory_size" {
  description = "Memory in MB."
  type        = number
  default     = 128

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "memory_size must be 128-10240."
  }
}

variable "timeout" {
  description = "Timeout in seconds. Use <= 29 when invoked synchronously through API Gateway."
  type        = number
  default     = 10

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "timeout must be 1-900."
  }
}

variable "environment_variables" {
  description = "Plain environment variables. Never put secrets here; read them from Secrets Manager/SSM at runtime."
  type        = map(string)
  default     = {}
}

variable "vpc_config" {
  description = "Attach the function to a VPC (private subnets). Null runs it outside a VPC."
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a value supported by CloudWatch Logs."
  }
}

variable "tracing_mode" {
  description = "X-Ray tracing mode."
  type        = string
  default     = "PassThrough"

  validation {
    condition     = contains(["PassThrough", "Active"], var.tracing_mode)
    error_message = "tracing_mode must be PassThrough or Active."
  }
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrency; -1 means unreserved."
  type        = number
  default     = -1
}

variable "dead_letter_target_arn" {
  description = "SQS queue or SNS topic ARN for failed asynchronous invocations."
  type        = string
  default     = null
}

variable "layers" {
  description = "Layer version ARNs."
  type        = list(string)
  default     = []
}
