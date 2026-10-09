# modules/route53/zone

Route 53 **hosted zone**, public or private.
**Non-goals:** records (see `route53/records`), DNSSEC, query logging, domain registration, delegation at the registrar.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root.

```yaml
dns:
  name: example.com
```

```hcl
module "zone" {
  source = "../../../modules/route53/zone"

  name = local.inputs.dns.name
  tags = local.tags
}
```

For a private zone, list the VPCs in `vpc_ids`; what comes from other modules (`module.vpc.vpc_id`) is wired in the `.tf`. Other modules take the zone from `module.zone.zone_id`.

## Resources and tags

`aws_route53_zone` (taggable, tagged). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `comment`, `vpc_ids`, `force_destroy`. See `variables.tf` for types, defaults and validations.

## Outputs

`zone_id`, `zone_arn`, `name`, `name_servers`.

## Lifecycle

Stateful. Changing `name` replaces the zone and gives it new name servers, so the delegation at the registrar breaks until it is updated. `force_destroy` is `false`: a zone that still has records cannot be destroyed.

## Cost

A fixed monthly price per hosted zone, plus a price per million queries.
