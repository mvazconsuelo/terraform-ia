# modules/vpc

Reusable VPC with a private tier (always) and an optional public tier, per-AZ private route tables, opt-in NAT, and a free S3 gateway endpoint.
**Non-goals:** interface endpoints, security groups, flow logs, transit gateway (separate modules).

## Usage

```hcl
module "vpc" {
  source = "../../modules/vpc"

  name       = "payments-dev"
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  cidr_block           = "10.0.0.0/16"
  availability_zones   = ["eu-west-1a", "eu-west-1b"]
  public_subnet_cidrs  = ["10.0.0.0/24", "10.0.1.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  nat_gateway_mode     = "single"
}
```

## Resources and tags

VPC, internet gateway, subnets, route tables, EIPs, NAT gateways, VPC endpoint — all taggable and tagged with `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`. Routes and associations are not taggable.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | string | — | Name prefix (3-30 chars). |
| `tags` | object | — | `environment` (dev/staging/prod), `owner`, `cost_center`, `project`. |
| `extra_tags` | map(string) | `{}` | Extra tags; the mandatory tags always win. |
| `cidr_block` | string | — | VPC CIDR. |
| `availability_zones` | list(string) | — | At least 2 distinct AZs. |
| `public_subnet_cidrs` | list(string) | `[]` | One per AZ, or empty for no public tier / no IGW. |
| `private_subnet_cidrs` | list(string) | — | One per AZ. |
| `nat_gateway_mode` | string | `"none"` | `none`, `single`, `per_az`. |
| `enable_s3_gateway_endpoint` | bool | `true` | Free S3 gateway endpoint on private route tables. |
| `public_subnet_tags` / `private_subnet_tags` | map(string) | `{}` | e.g. `kubernetes.io/role/elb`. |

## Outputs

`vpc_id`, `vpc_cidr_block`, `public_subnet_ids`, `private_subnet_ids`, `private_route_table_ids` (by AZ), `nat_gateway_ids`.

## Lifecycle

- Changing `cidr_block`, a subnet CIDR or an AZ **replaces** the VPC/subnet and everything inside it.
- Switching `nat_gateway_mode` between `single` and `per_az` replaces NAT gateways and changes egress IPs.

## Cost

NAT gateways dominate (hourly + per GB): `none` = $0, `single` = 1×, `per_az` = N×. Prefer `none` plus VPC endpoints for AWS-only traffic, `single` for non-prod.

## Testing

`terraform init -backend=false && terraform test` (uses `mock_provider`, no credentials).
