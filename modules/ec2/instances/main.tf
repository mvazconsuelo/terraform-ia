resource "aws_instance" "this" {
  for_each = var.instances

  subnet_id                   = each.value.subnet_id
  instance_type               = each.value.instance_type
  private_ip                  = each.value.private_ip
  vpc_security_group_ids      = each.value.security_group_ids
  associate_public_ip_address = false
  disable_api_termination     = var.termination_protection

  launch_template {
    id      = var.launch_template_id
    version = var.launch_template_version
  }

  tags        = merge(local.tags, { Name = "${var.name}-${each.key}" })
  volume_tags = merge(local.tags, { Name = "${var.name}-${each.key}" })

}

# Data volumes are stateful: they outlive instance replacement only if you keep the same key.
resource "aws_ebs_volume" "this" {
  for_each = local.data_volumes

  availability_zone = aws_instance.this[each.value.instance].availability_zone
  size              = each.value.size_gb
  type              = each.value.type
  iops              = each.value.iops
  throughput        = each.value.throughput
  encrypted         = true
  kms_key_id        = var.kms_key_id

  tags = merge(local.tags, { Name = "${var.name}-${replace(each.key, "/", "-")}" })
}

resource "aws_volume_attachment" "this" {
  for_each = local.data_volumes

  device_name = each.value.device_name
  volume_id   = aws_ebs_volume.this[each.key].id
  instance_id = aws_instance.this[each.value.instance].id
}
