output "record_fqdns" {
  description = "Fully qualified name of each record, keyed like the records input."
  value       = { for key, record in aws_route53_record.this : key => record.fqdn }
}
