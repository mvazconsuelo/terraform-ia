output "certificate_arn" {
  description = "Certificate ARN. With zone_id set it is known only once the certificate is issued, so whatever uses it waits for the validation."
  value       = var.zone_id == null ? aws_acm_certificate.this.arn : aws_acm_certificate_validation.this[0].certificate_arn
}

output "domain_name" {
  description = "Main domain of the certificate."
  value       = aws_acm_certificate.this.domain_name
}

output "domain_validation_records" {
  description = "DNS records (name, type, value) that validate each domain, keyed by domain. Public values, not secrets."
  value       = local.validation_records
}
