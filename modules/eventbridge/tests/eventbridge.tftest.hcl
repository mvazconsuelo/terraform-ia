mock_provider "aws" {}

variables {
  tags = {
    environment = "dev"
    owner       = "platform-team"
    cost_center = "cc-1234"
    project     = "terra-ai"
  }
  name = "orders-dev"
  rules = {
    nightly = {
      schedule_expression = "cron(0 3 * * ? *)"
      targets = {
        job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job", lambda_function_name = "job" }
      }
    }
  }
}

run "schedule_rule_on_default_bus" {
  command = plan

  assert {
    condition     = length(aws_cloudwatch_event_bus.this) == 0 && aws_cloudwatch_event_rule.this["nightly"].event_bus_name == "default"
    error_message = "Default bus expected."
  }

  assert {
    condition     = length(aws_cloudwatch_event_target.this) == 1 && length(aws_lambda_permission.this) == 1
    error_message = "One target and one lambda invoke permission expected."
  }
}

run "mandatory_tags_applied" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["Name", "Environment", "Owner", "CostCenter", "Project", "ManagedBy"] :
      contains(keys(aws_cloudwatch_event_rule.this["nightly"].tags), k)
    ])
    error_message = "Rules need mandatory tags."
  }
}

run "custom_bus_with_pattern" {
  command = plan

  variables {
    create_bus = true
    rules = {
      created = {
        event_pattern = "{\"detail-type\":[\"OrderCreated\"]}"
        targets = {
          queue = { arn = "arn:aws:sqs:us-east-1:111122223333:orders" }
        }
      }
    }
  }

  assert {
    condition     = length(aws_cloudwatch_event_bus.this) == 1 && contains(keys(aws_cloudwatch_event_bus.this[0].tags), "CostCenter")
    error_message = "Tagged custom bus expected."
  }
}

run "schedule_not_allowed_on_custom_bus" {
  command = plan

  variables {
    create_bus = true
  }

  expect_failures = [aws_cloudwatch_event_rule.this]
}

run "rule_needs_trigger" {
  command = plan

  variables {
    rules = { bad = { targets = { t = { arn = "arn:aws:sqs:us-east-1:111122223333:q" } } } }
  }

  expect_failures = [var.rules]
}

run "rejects_invalid_pattern" {
  command = plan

  variables {
    rules = { bad = { event_pattern = "nope", targets = { t = { arn = "arn:aws:sqs:us-east-1:111122223333:q" } } } }
  }

  expect_failures = [var.rules]
}
