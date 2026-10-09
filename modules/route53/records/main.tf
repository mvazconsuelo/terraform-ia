resource "aws_route53_record" "this" {
  for_each = var.records

  zone_id         = var.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = each.value.alias == null ? each.value.ttl : null
  records         = each.value.values
  allow_overwrite = var.allow_overwrite

  dynamic "alias" {
    for_each = each.value.alias == null ? [] : [each.value.alias]

    content {
      name                   = alias.value.name
      zone_id                = alias.value.zone_id
      evaluate_target_health = alias.value.evaluate_target_health
    }
  }
}
