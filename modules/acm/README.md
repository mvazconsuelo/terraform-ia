# modules/acm

Public **AWS Certificate Manager** certificate validated by DNS, with the Route 53 validation records.
**Non-goals:** imported or private-CA certificates, email validation, creating hosted zones, CloudFront certificates (they need `us-east-1` and a provider alias, which modules do not configure), attaching the certificate to a load balancer.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
certificate:
  name: "${project}-${environment}-web"
  domain_name: example.com
  subject_alternative_names:
    - "*.example.com"
  zone_id: Z0123456789ABCDEFGHIJ
```

```hcl
module "certificate" {
  source = "../../../modules/acm"

  name                      = templatestring(local.inputs.certificate.name, local.tags)
  domain_name               = local.inputs.certificate.domain_name
  subject_alternative_names = local.inputs.certificate.subject_alternative_names
  zone_id                   = local.inputs.certificate.zone_id
  tags                      = local.tags
}
```

Another module takes the certificate from `module.certificate.certificate_arn`, wired in the `.tf`.

## Resources and tags

`aws_acm_certificate` (taggable, tagged), `aws_route53_record` (the validation CNAMEs, created only with `zone_id`; not taggable) and `aws_acm_certificate_validation` (only with `zone_id`). Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `domain_name`, `subject_alternative_names`, `zone_id`, `key_algorithm`, `validation_timeout`. See `variables.tf` for types, defaults and validations. With `zone_id` null the module creates no records and does not wait: validate the certificate with the `domain_validation_records` output, for example in a zone of another account.

## Outputs

`certificate_arn`, `domain_name`, `domain_validation_records`.

## Lifecycle

Changing `domain_name`, `subject_alternative_names` or `key_algorithm` replaces the certificate; it is created before the old one is destroyed, so a certificate in use is swapped without a gap. The validation records are overwritten if they already exist (the apex and its wildcard share one).

## Cost

Public certificates are free. Only the Route 53 validation records add a negligible cost.
