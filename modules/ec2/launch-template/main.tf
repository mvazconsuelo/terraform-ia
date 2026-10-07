data "aws_ssm_parameter" "ami" {
  count = var.ami_id == null ? 1 : 0

  name = var.ami_ssm_parameter
}

resource "aws_launch_template" "this" {
  name_prefix   = "${var.name}-"
  image_id      = local.image_id
  instance_type = var.instance_type
  user_data     = var.user_data == null ? null : base64encode(var.user_data)
  ebs_optimized = var.ebs_optimized

  vpc_security_group_ids = var.security_group_ids

  # Make new versions the default so consumers pinned to "$Default" pick them up on their next replacement.
  update_default_version = true

  dynamic "iam_instance_profile" {
    for_each = var.iam_instance_profile_name == null ? [] : [var.iam_instance_profile_name]

    content {
      name = iam_instance_profile.value
    }
  }

  dynamic "instance_market_options" {
    for_each = var.use_spot ? [1] : []

    content {
      market_type = "spot"
    }
  }

  dynamic "placement" {
    for_each = var.placement_group == null ? [] : [var.placement_group]

    content {
      group_name = placement.value
    }
  }

  # IMDSv2 only; hop limit 1 keeps containers on the host from reaching instance credentials.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.root_volume_size_gb
      volume_type           = var.root_volume_type
      encrypted             = true
      kms_key_id            = var.kms_key_id
      delete_on_termination = true
    }
  }

  monitoring {
    enabled = var.detailed_monitoring
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Name = var.name })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(local.tags, { Name = var.name })
  }

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    create_before_destroy = true
  }
}
