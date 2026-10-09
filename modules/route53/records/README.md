# modules/route53/records

DNS **records** in a Route 53 hosted zone that already exists: standard records and alias records.
**Non-goals:** creating the zone (see `route53/zone`), routing policies (weighted, failover, latency, geolocation), health checks. This module creates no taggable resource, so it takes no `tags`.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names.

```yaml
dns:
  records:
    www:
      name: www.example.com
      type: CNAME
      ttl: 300
      values:
        - example.com
    spf:
      name: example.com
      type: TXT
      values:
        - "v=spf1 -all"
```

```hcl
module "records" {
  source = "../../../modules/route53/records"

  zone_id = module.zone.zone_id
  records = local.inputs.dns.records
}
```

An alias to a load balancer takes its name and zone from another module, so it is wired in the `.tf`:

```hcl
records = merge(local.inputs.dns.records, {
  app = {
    name  = local.inputs.dns.app_name
    type  = "A"
    alias = { name = module.alb.dns_name, zone_id = module.alb.zone_id }
  }
})
```

## Resources and tags

`aws_route53_record` (not taggable, so no tags).

## Inputs

`zone_id`, `records` (each with `name`, `type`, `ttl`, and either `values` or `alias`), `allow_overwrite`. See `variables.tf` for types, defaults and validations.

## Outputs

`record_fqdns`.

## Lifecycle

Stateless: changing the `name` or `type` of a record replaces it. Alias records have no TTL (Route 53 uses the one of the target). With `allow_overwrite` true the module takes over records that already exist.

## Cost

Records themselves are free; queries are billed per million, and queries to an alias that points to an AWS resource are free.
