data "aws_iam_policy_document" "assume_role" {
  dynamic "statement" {
    for_each = length(var.assume_role_services) > 0 ? [1] : []

    content {
      effect  = "Allow"
      actions = ["sts:AssumeRole"]

      principals {
        type        = "Service"
        identifiers = var.assume_role_services
      }
    }
  }

  dynamic "statement" {
    for_each = length(var.assume_role_principal_arns) > 0 ? [1] : []

    content {
      effect  = "Allow"
      actions = ["sts:AssumeRole"]

      principals {
        type        = "AWS"
        identifiers = var.assume_role_principal_arns
      }
    }
  }
}

resource "aws_iam_role" "this" {
  name                 = var.name
  path                 = var.path
  assume_role_policy   = data.aws_iam_policy_document.assume_role.json
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = var.max_session_duration

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition     = length(var.assume_role_services) + length(var.assume_role_principal_arns) > 0
      error_message = "Provide at least one assume_role_services or assume_role_principal_arns entry."
    }
  }
}

resource "aws_iam_role_policy_attachment" "this" {
  for_each = toset(var.managed_policy_arns)

  role       = aws_iam_role.this.name
  policy_arn = each.value
}

resource "aws_iam_role_policy" "this" {
  for_each = var.inline_policies

  name   = each.key
  role   = aws_iam_role.this.id
  policy = each.value
}

resource "aws_iam_instance_profile" "this" {
  count = var.create_instance_profile ? 1 : 0

  name = var.name
  path = var.path
  role = aws_iam_role.this.name

  tags = merge(local.tags, { Name = var.name })
}
