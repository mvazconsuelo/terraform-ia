output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs ordered by availability zone."
  value       = [for az in var.availability_zones : aws_subnet.public[az].id if contains(keys(aws_subnet.public), az)]
}

output "private_subnet_ids" {
  description = "Private subnet IDs ordered by availability zone."
  value       = [for az in var.availability_zones : aws_subnet.private[az].id]
}

output "private_route_table_ids" {
  description = "Private route table IDs, keyed by availability zone. Use to attach additional gateway endpoints."
  value       = { for az, rt in aws_route_table.private : az => rt.id }
}

output "nat_gateway_ids" {
  description = "NAT gateway IDs (empty when nat_gateway_mode is `none`)."
  value       = aws_nat_gateway.this[*].id
}
