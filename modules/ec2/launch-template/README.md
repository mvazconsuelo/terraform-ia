# modules/ec2/launch-template

Hardened EC2 launch template shared by `ec2/instances` and `ec2/asg`: IMDSv2 only, encrypted root volume, tagged instance and volume specs, optional Spot, placement group and instance profile.
**Non-goals:** launching instances (`ec2/instances`), scaling (`ec2/asg`), AMI building, SSH key pairs (use SSM Session Manager).

## Usage

Values live in your project's `inputs.yaml`, in block-style YAML; the keys of a block are this module's variable names. `local.tags` are the mandatory tags: `owner` and `cost_center` from your `inputs.yaml`, plus the `project` and the `environment` that `common.yaml` assigns to the root. What comes from other modules is wired in the `.tf`. The `name` of a block is written with the placeholders `${project}` and `${environment}`, and the call completes it with `local.tags` (`templatestring`), so the environment is written once, in `common.yaml`.

```yaml
web_template:
  name: "${project}-${environment}-web"
  ami_id: ami-0123456789abcdef0     # pin it in production
```

```hcl
module "web_template" {
  source = "../../../modules/ec2/launch-template"

  name                      = templatestring(local.inputs.web_template.name, local.tags)
  ami_id                    = local.inputs.web_template.ami_id
  tags                      = local.tags
  security_group_ids        = [module.web_sg.security_group_id]
  iam_instance_profile_name = module.web_role.instance_profile_name
}
```

## Resources and tags

`aws_launch_template` (taggable, tagged, with `instance` and `volume` tag specifications); optional `aws_ssm_parameter` AMI lookup. Mandatory tags: `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`.

## Inputs

`name`, `tags`, `extra_tags`, `security_group_ids`, `instance_type` (`t3.small`), `ami_id` or `ami_ssm_parameter` (AL2023 x86_64), `iam_instance_profile_name`, `user_data` (no secrets), `root_volume_size_gb`/`root_volume_type`, `kms_key_id`, `use_spot`, `ebs_optimized`, `detailed_monitoring`, `placement_group`. See `variables.tf` for types, defaults and validations.

## Outputs

`launch_template_id`, `launch_template_arn`, `latest_version`, `default_version`.

## Lifecycle

Every change creates a new template version and moves `$Default` (`update_default_version`). `ec2/asg` should receive `latest_version` so a change rolls the group; `ec2/instances` defaults to `$Default` so instances are not replaced by surprise. Without `ami_id`, the SSM lookup follows each new AMI release: pin the AMI in production. Do not set `use_spot` when the ASG uses a mixed instances policy.

## Cost

Free by itself; drives the cost of everything launched from it (instance type, volume size, detailed monitoring).
