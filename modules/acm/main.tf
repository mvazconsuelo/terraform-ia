resource "aws_acm_certificate" "this" {
  domain_name               = var.domain_name
  subject_alternative_names = var.subject_alternative_names
  validation_method         = "DNS"
  key_algorithm             = var.key_algorithm

  tags = merge(local.tags, { Name = var.name })

  # A certificate in use (by a load balancer, for example) cannot be destroyed first: the new one is created, then the old one goes.
  lifecycle {
    create_before_destroy = true
  }
}

# The apex and its wildcard share one CNAME, so both entries write the same record: allow_overwrite lets the second one pass.
resource "aws_route53_record" "validation" {
  for_each = var.zone_id == null ? {} : local.validation_records

  zone_id         = var.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.value]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  count = var.zone_id == null ? 0 : 1

  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.validation : record.fqdn]

  timeouts {
    create = var.validation_timeout
  }
}
