# modules/s3

Private, encrypted, versioned S3 bucket with TLS-only policy and optional lifecycle rules.
**Non-goals:** replication, bucket notifications, website hosting, cross-account policies.

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
artifacts:
  name: "${project}-${environment}-artifacts"
  lifecycle_rules:
    logs:
      prefix: logs/
      expiration_days: 30
```

```hcl
module "artifacts" {
  source = "../../../modules/s3"

  name            = templatestring(local.inputs.artifacts.name, local.tags)
  lifecycle_rules = local.inputs.artifacts.lifecycle_rules
  tags            = local.tags
}
```

## Resources and tags

Only `aws_s3_bucket` is taggable; sub-resources (public access block, ownership, versioning, encryption, lifecycle, policy) are not. The bucket carries all mandatory mandatory tags.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | string | — | Globally unique bucket name. |
| `tags` | object | — | `environment`, `owner`, `cost_center`, `project`. |
| `tags` | map(string) | `{}` | Extra tags. |
| `versioning_enabled` | bool | `true` | Object versioning. |
| `force_destroy` | bool | `false` | Allow deleting a non-empty bucket. |
| `kms_key_arn` | string | `null` | SSE-KMS key; null uses SSE-S3. |
| `lifecycle_rules` | map(object) | `{}` | `prefix`, `expiration_days`, `noncurrent_version_expiration_days`, `abort_incomplete_multipart_days`. |

## Outputs

`bucket_id`, `bucket_arn`, `bucket_regional_domain_name`.

## Lifecycle

Changing `name` replaces the bucket (data loss unless emptied/migrated). `force_destroy = false` protects against accidental destroy of non-empty buckets.

## Cost

Storage and requests only. Versioning without `noncurrent_version_expiration_days` grows unbounded.
