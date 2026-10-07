data "aws_region" "current" {}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.tags, { Name = var.name })

  lifecycle {
    precondition {
      condition     = length(var.private_subnet_cidrs) == local.az_count
      error_message = "private_subnet_cidrs must contain exactly one CIDR per availability zone."
    }
    precondition {
      condition     = !local.has_public || length(var.public_subnet_cidrs) == local.az_count
      error_message = "public_subnet_cidrs must be empty or contain exactly one CIDR per availability zone."
    }
    precondition {
      condition     = var.nat_gateway_mode == "none" || local.has_public
      error_message = "nat_gateway_mode other than `none` requires public subnets to host the NAT gateways."
    }
  }
}

resource "aws_internet_gateway" "this" {
  count = local.has_public ? 1 : 0

  vpc_id = aws_vpc.this.id

  tags = merge(local.tags, { Name = var.name })
}

resource "aws_subnet" "public" {
  for_each = local.public_azs

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = each.value
  map_public_ip_on_launch = false

  tags = merge(local.tags, var.public_subnet_tags, {
    Name = "${var.name}-public-${each.key}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  for_each = local.private_azs

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = merge(local.tags, var.private_subnet_tags, {
    Name = "${var.name}-private-${each.key}"
    Tier = "private"
  })
}

resource "aws_route_table" "public" {
  count = local.has_public ? 1 : 0

  vpc_id = aws_vpc.this.id

  tags = merge(local.tags, { Name = "${var.name}-public" })
}

resource "aws_route" "public_internet" {
  count = local.has_public ? 1 : 0

  route_table_id         = aws_route_table.public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this[0].id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_eip" "nat" {
  count = local.nat_count

  domain = "vpc"

  tags = merge(local.tags, { Name = "${var.name}-nat-${local.nat_az_index[count.index]}" })
}

resource "aws_nat_gateway" "this" {
  count = local.nat_count

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[local.nat_az_index[count.index]].id

  tags = merge(local.tags, { Name = "${var.name}-${local.nat_az_index[count.index]}" })

  depends_on = [aws_internet_gateway.this]
}

# One private route table per AZ so `per_az` NAT keeps traffic AZ-local.
resource "aws_route_table" "private" {
  for_each = aws_subnet.private

  vpc_id = aws_vpc.this.id

  tags = merge(local.tags, { Name = "${var.name}-private-${each.key}" })
}

resource "aws_route" "private_nat" {
  for_each = local.nat_enabled ? aws_route_table.private : {}

  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = var.nat_gateway_mode == "single" ? aws_nat_gateway.this[0].id : aws_nat_gateway.this[index(var.availability_zones, each.key)].id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

resource "aws_vpc_endpoint" "s3" {
  count = var.enable_s3_gateway_endpoint ? 1 : 0

  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for rt in aws_route_table.private : rt.id]

  tags = merge(local.tags, { Name = "${var.name}-s3" })
}
