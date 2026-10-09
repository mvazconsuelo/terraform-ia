# modules/s3: a private, encrypted, versioned bucket. The defaults are the secure ones.

mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

variables {
  name = "test-bucket-123"
  tags = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_is_versioned_and_not_force_destroyable" {
  command = apply
  module {
    source = "../../modules/s3"
  }
  assert {
    condition     = aws_s3_bucket_versioning.this.versioning_configuration[0].status == "Enabled" && aws_s3_bucket.this.force_destroy == false
    error_message = "by default the bucket is versioned and cannot be destroyed with objects in it"
  }
}

run "it_encrypts_with_the_default_key_unless_a_kms_key_is_given" {
  command = apply
  module {
    source = "../../modules/s3"
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "with no kms_key_arn the bucket uses AES256"
  }
}

run "it_encrypts_with_kms_when_a_key_is_given" {
  command = apply
  module {
    source = "../../modules/s3"
  }
  variables {
    kms_key_arn = "arn:aws:kms:us-east-1:111122223333:key/00000000-0000-0000-0000-000000000000"
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default).sse_algorithm == "aws:kms"
    error_message = "with a kms_key_arn the bucket uses KMS"
  }
}

run "versioning_can_be_suspended" {
  command = apply
  module {
    source = "../../modules/s3"
  }
  variables {
    versioning_enabled = false
  }
  assert {
    condition     = aws_s3_bucket_versioning.this.versioning_configuration[0].status == "Suspended"
    error_message = "versioning_enabled = false must suspend versioning"
  }
}

run "no_lifecycle_configuration_without_rules" {
  command = apply
  module {
    source = "../../modules/s3"
  }
  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.this) == 0
    error_message = "with no lifecycle_rules there is no lifecycle configuration"
  }
}

run "an_invalid_bucket_name_is_rejected" {
  command = plan
  module {
    source = "../../modules/s3"
  }
  variables {
    name = "Not_A_Bucket"
  }
  expect_failures = [var.name]
}

run "a_lifecycle_rule_that_expires_after_zero_days_is_rejected" {
  command = plan
  module {
    source = "../../modules/s3"
  }
  variables {
    lifecycle_rules = { old = { expiration_days = 0 } }
  }
  expect_failures = [var.lifecycle_rules]
}
