output "zone_id" {
  description = "Hosted zone ID."
  value       = aws_route53_zone.this.zone_id
}

output "zone_arn" {
  description = "Hosted zone ARN."
  value       = aws_route53_zone.this.arn
}

output "name" {
  description = "Domain name of the zone."
  value       = aws_route53_zone.this.name
}

output "name_servers" {
  description = "Name servers of the zone. Set them at the domain registrar to delegate the domain."
  value       = aws_route53_zone.this.name_servers
}
