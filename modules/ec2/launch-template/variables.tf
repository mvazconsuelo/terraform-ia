variable "name" {
  description = "Launch template name prefix."
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

variable "instance_type" {
  description = "Default EC2 instance type (consumers such as ec2/instances or ec2/asg can override it)."
  type        = string
  default     = "t3.small"

  validation {
    condition     = can(regex("^[a-z0-9]+\\.[a-z0-9]+$", var.instance_type))
    error_message = "instance_type must look like `t3.small`."
  }
}

variable "ami_id" {
  description = "AMI ID. Null resolves the AMI from `ami_ssm_parameter` at plan time (moves with every AMI release: pin in production)."
  type        = string
  default     = null
}

variable "ami_ssm_parameter" {
  description = "Public SSM parameter used when ami_id is null. Use the arm64 parameter for Graviton instance types."
  type        = string
  default     = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

variable "security_group_ids" {
  description = "Default security groups (create with modules/security-group)."
  type        = list(string)
}

variable "iam_instance_profile_name" {
  description = "Instance profile name (modules/iam with create_instance_profile). Attach AmazonSSMManagedInstanceCore for shell access instead of SSH keys."
  type        = string
  default     = null
}

variable "user_data" {
  description = "Plain-text user data script (the module base64-encodes it). Never include secrets."
  type        = string
  default     = null
}

variable "root_volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.root_volume_size_gb >= 8 && var.root_volume_size_gb <= 16384
    error_message = "root_volume_size_gb must be 8-16384."
  }
}

variable "root_volume_type" {
  description = "Root EBS volume type."
  type        = string
  default     = "gp3"

  validation {
    condition     = contains(["gp3", "gp2", "io1", "io2"], var.root_volume_type)
    error_message = "root_volume_type must be gp3, gp2, io1 or io2."
  }
}

variable "kms_key_id" {
  description = "KMS key ARN for EBS encryption. Null uses the AWS-managed aws/ebs key. Volumes are always encrypted."
  type        = string
  default     = null
}

variable "use_spot" {
  description = "Request Spot capacity through the template. Do not set when the ASG uses a mixed instances policy (the ASG controls market options)."
  type        = bool
  default     = false
}

variable "ebs_optimized" {
  description = "Dedicated EBS bandwidth (default on for most current-generation types)."
  type        = bool
  default     = true
}

variable "detailed_monitoring" {
  description = "Enable 1-minute CloudWatch detailed monitoring (extra cost)."
  type        = bool
  default     = false
}

variable "placement_group" {
  description = "Placement group name (cluster, partition or spread)."
  type        = string
  default     = null
}
