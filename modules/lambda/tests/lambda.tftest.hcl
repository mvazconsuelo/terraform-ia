mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  function_name = "worker-dev"
  role_arn      = "arn:aws:iam::111122223333:role/worker"
  handler       = "index.handler"
  runtime       = "python3.12"
  filename      = "worker.zip"
}

run "defaults_are_cost_conscious" {
  command = plan

  assert {
    condition     = aws_lambda_function.this.architectures[0] == "arm64" && aws_lambda_function.this.memory_size == 128 && aws_cloudwatch_log_group.this.retention_in_days == 30
    error_message = "Expected arm64, 128MB and 30-day log retention."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_lambda_function.this.tags), k) && contains(keys(aws_cloudwatch_log_group.this.tags), k)
    ])
    error_message = "Function and log group need mandatory tags."
  }
}

run "s3_package" {
  command = plan

  variables {
    filename  = null
    s3_bucket = "artifacts"
    s3_key    = "worker.zip"
  }

  assert {
    condition     = aws_lambda_function.this.s3_key == "worker.zip"
    error_message = "S3 package source not honoured."
  }
}

run "package_source_is_exclusive" {
  command = plan

  variables {
    s3_bucket = "artifacts"
    s3_key    = "worker.zip"
  }

  expect_failures = [aws_lambda_function.this]
}

run "vpc_config_optional" {
  command = plan

  variables {
    vpc_config = { subnet_ids = ["subnet-a"], security_group_ids = ["sg-1"] }
  }

  assert {
    condition     = length(aws_lambda_function.this.vpc_config) == 1
    error_message = "vpc_config block expected."
  }
}

run "rejects_bad_memory" {
  command = plan

  variables {
    memory_size = 64
  }

  expect_failures = [var.memory_size]
}
