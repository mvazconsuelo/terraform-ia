# modules/lambda: a function with its log group. It takes its code from a file or from S3, and the defaults are the cheap and safe ones.

mock_provider "aws" {}

variables {
  function_name = "test-function"
  role_arn      = "arn:aws:iam::111122223333:role/test"
  handler       = "index.handler"
  runtime       = "python3.12"
  filename      = "function.zip"
  tags          = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
}

run "works_with_the_minimum_inputs_and_uses_arm_with_small_defaults" {
  command = apply
  module {
    source = "../../modules/lambda"
  }
  assert {
    condition     = one(aws_lambda_function.this.architectures) == "arm64"
    error_message = "by default the function runs on arm64"
  }
  assert {
    condition     = aws_lambda_function.this.memory_size == 128
    error_message = "by default the function has 128 MB"
  }
  assert {
    condition     = aws_lambda_function.this.timeout == 10
    error_message = "by default the timeout is 10 seconds"
  }
}

run "the_log_group_keeps_logs_for_30_days_by_default" {
  command = apply
  module {
    source = "../../modules/lambda"
  }
  assert {
    condition     = aws_cloudwatch_log_group.this.retention_in_days == 30
    error_message = "log_retention_days defaults to 30"
  }
}

run "the_code_can_come_from_s3_instead_of_a_file" {
  command = apply
  module {
    source = "../../modules/lambda"
  }
  variables {
    filename  = null
    s3_bucket = "my-code-bucket"
    s3_key    = "function.zip"
  }
  assert {
    condition     = aws_lambda_function.this.s3_bucket == "my-code-bucket"
    error_message = "with s3_bucket and s3_key the function takes its code from S3"
  }
}

run "code_from_a_file_and_from_s3_at_once_is_rejected" {
  command = plan
  module {
    source = "../../modules/lambda"
  }
  variables {
    s3_bucket = "my-code-bucket"
    s3_key    = "function.zip"
  }
  expect_failures = [aws_lambda_function.this]
}

run "no_code_at_all_is_rejected" {
  command = plan
  module {
    source = "../../modules/lambda"
  }
  variables {
    filename = null
  }
  expect_failures = [aws_lambda_function.this]
}

run "a_memory_size_out_of_range_is_rejected" {
  command = plan
  module {
    source = "../../modules/lambda"
  }
  variables {
    memory_size = 64
  }
  expect_failures = [var.memory_size]
}

run "a_timeout_out_of_range_is_rejected" {
  command = plan
  module {
    source = "../../modules/lambda"
  }
  variables {
    timeout = 1000
  }
  expect_failures = [var.timeout]
}

run "an_unknown_architecture_is_rejected" {
  command = plan
  module {
    source = "../../modules/lambda"
  }
  variables {
    architectures = ["mips"]
  }
  expect_failures = [var.architectures]
}
