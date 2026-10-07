# modules/ec2/instances

One or more standalone EC2 instances (bastions, single servers) launched from a launch template, private by default, with optional encrypted data volumes.
**Non-goals:** scaling or self-healing (`ec2/asg`), public IPs/Elastic IPs, load balancer registration.

## Usage

```hcl
module "bastion" {
  source = "../../../modules/ec2/instances"

  name                    = "payments-dev-bastion"
  launch_template_id      = module.web_template.launch_template_id
  termination_protection  = true
  tags = { environment = "dev", owner = "platform-team", cost_center = "cc-1234", project = "payments" }

  instances = {
    a = { subnet_id = module.vpc.private_subnet_ids[0] }
    b = {
      subnet_id    = module.vpc.private_subnet_ids[1]
      data_volumes = { data = { device_name = "/dev/sdf", size_gb = 100 } }
    }
  }
}
```

## Resources and tags

`aws_instance` (taggable; `volume_tags` also set), `aws_ebs_volume` (taggable, always encrypted) and `aws_volume_attachment`. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `launch_template_id`, `launch_template_version` (`$Default`), `instances` (per instance: `subnet_id`, `instance_type`, `private_ip`, `security_group_ids`, `data_volumes`), `termination_protection` (false), `kms_key_id`. See `variables.tf` for types, defaults and validations.

## Outputs

`instance_ids`, `private_ips`, `availability_zones`, `data_volume_ids` (keyed by `<instance>/<volume>`).

## Lifecycle

Instance keys are identities: renaming a key replaces the instance. Changing `subnet_id`, `private_ip` or a pinned template version replaces the instance; data volumes are keyed by `<instance>/<volume>`, so a replacement re-attaches a new, empty volume unless you restore from a snapshot. Instances have no self-healing: use `ec2/asg` (min=max=1) when you need replacement on failure.

## Cost

Instance type x hours + EBS (root and data volumes) + data transfer.

## Testing

`terraform init -backend=false && terraform test` (mock provider, no credentials).
