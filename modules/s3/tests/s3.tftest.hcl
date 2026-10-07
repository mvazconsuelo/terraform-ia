mock_provider "aws" {}

variables {
  name = "terra-ai-test-dev"
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
}

run "secure_defaults" {
  command = plan

  assert {
    condition     = aws_s3_bucket_public_access_block.this.block_public_acls && aws_s3_bucket_public_access_block.this.restrict_public_buckets
    error_message = "Public access must be blocked by default."
  }

  assert {
    condition     = aws_s3_bucket_versioning.this.versioning_configuration[0].status == "Enabled"
    error_message = "Versioning must default to enabled."
  }

  assert {
    condition     = !aws_s3_bucket.this.force_destroy
    error_message = "force_destroy must default to false."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_s3_bucket.this.tags), k)
    ])
    error_message = "Bucket is missing mandatory tags."
  }
}

run "kms_encryption" {
  command = plan

  variables {
    kms_key_arn = "arn:aws:kms:us-east-1:111122223333:key/abc"
  }

  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    error_message = "kms_key_arn must switch encryption to aws:kms."
  }
}

run "lifecycle_rules_created" {
  command = plan

  variables {
    lifecycle_rules = {
      logs = { prefix = "logs/", expiration_days = 30 }
    }
  }

  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.this) == 1
    error_message = "Lifecycle configuration expected."
  }
}

run "invalid_name_rejected" {
  command = plan

  variables {
    name = "Bad_Name"
  }

  expect_failures = [var.name]
}
