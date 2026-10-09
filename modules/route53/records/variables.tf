variable "zone_id" {
  description = "Hosted zone the records are created in."
  type        = string

  validation {
    condition     = can(regex("^Z[A-Z0-9]{1,31}$", var.zone_id))
    error_message = "zone_id must be a Route 53 hosted zone ID (Z followed by letters and numbers)."
  }
}

variable "records" {
  description = "Records keyed by a stable identifier. Each one has either values (a standard record) or alias (an alias to an AWS resource, type A or AAAA), never both."
  type = map(object({
    name   = string
    type   = string
    ttl    = optional(number, 300)
    values = optional(list(string))
    alias = optional(object({
      name                   = string
      zone_id                = string
      evaluate_target_health = optional(bool, true)
    }))
  }))
  default = {}

  validation {
    condition     = alltrue([for r in values(var.records) : length(trimspace(r.name)) > 0])
    error_message = "Every record needs a name: the full record name (for the apex, the name of the zone)."
  }

  validation {
    condition     = alltrue([for r in values(var.records) : contains(["A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA"], r.type)])
    error_message = "type must be A, AAAA, CNAME, TXT, MX, NS, SRV or CAA."
  }

  validation {
    condition     = alltrue([for r in values(var.records) : (r.values != null) != (r.alias != null)])
    error_message = "Each record needs either values or alias, not both and not neither."
  }

  validation {
    condition     = alltrue([for r in values(var.records) : r.values == null ? true : length(r.values) > 0])
    error_message = "values must not be an empty list."
  }

  validation {
    condition     = alltrue([for r in values(var.records) : r.alias == null ? true : contains(["A", "AAAA"], r.type)])
    error_message = "An alias record must be of type A or AAAA."
  }

  validation {
    condition     = alltrue([for r in values(var.records) : r.ttl > 0])
    error_message = "ttl must be positive."
  }
}

variable "allow_overwrite" {
  description = "Take over records that already exist in the zone instead of failing."
  type        = bool
  default     = false
}
