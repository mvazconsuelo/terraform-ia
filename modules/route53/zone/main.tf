resource "aws_route53_zone" "this" {
  name          = var.name
  comment       = var.comment
  force_destroy = var.force_destroy

  # A zone with VPCs is private; without them it is public.
  dynamic "vpc" {
    for_each = toset(var.vpc_ids)

    content {
      vpc_id = vpc.value
    }
  }

  tags = merge(local.tags, { Name = var.name })
}
