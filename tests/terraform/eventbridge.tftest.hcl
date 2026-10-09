# modules/eventbridge: rules that fire on a schedule or on an event pattern, with their targets.

mock_provider "aws" {
  mock_resource "aws_cloudwatch_event_rule" {
    defaults = { arn = "arn:aws:events:us-east-1:111122223333:rule/test" }
  }
}

variables {
  name = "test-events"
  tags = { environment = "dev", owner = "team", cost_center = "cc-1", project = "demo" }
  rules = {
    nightly = {
      schedule_expression = "cron(0 3 * * ? *)"
      targets             = { job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job" } }
    }
  }
}

run "works_with_the_minimum_inputs_on_the_default_bus" {
  command = apply
  module {
    source = "../../modules/eventbridge"
  }
  assert {
    condition     = length(aws_cloudwatch_event_bus.this) == 0 && length(aws_cloudwatch_event_rule.this) == 1 && length(aws_cloudwatch_event_target.this) == 1
    error_message = "by default the rules go on the default bus: no bus is created"
  }
}

run "a_custom_bus_is_created_when_asked" {
  command = apply
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    create_bus = true
    rules = {
      orders = {
        event_pattern = "{\"source\":[\"orders\"]}"
        targets       = { job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job" } }
      }
    }
  }
  assert {
    condition     = length(aws_cloudwatch_event_bus.this) == 1
    error_message = "create_bus = true must create the bus"
  }
}

run "a_lambda_target_gets_permission_to_be_invoked" {
  command = apply
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    rules = {
      nightly = {
        schedule_expression = "rate(1 day)"
        targets             = { job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job", lambda_function_name = "job" } }
      }
    }
  }
  assert {
    condition     = length(aws_lambda_permission.this) == 1
    error_message = "a target with lambda_function_name needs the invoke permission"
  }
}

run "a_rule_with_neither_schedule_nor_pattern_is_rejected" {
  command = plan
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    rules = { empty = { targets = { job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job" } } } }
  }
  expect_failures = [var.rules]
}

run "an_event_pattern_that_is_not_json_is_rejected" {
  command = plan
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    rules = { bad = { event_pattern = "not json", targets = { job = { arn = "arn:aws:lambda:us-east-1:111122223333:function:job" } } } }
  }
  expect_failures = [var.rules]
}

run "a_rule_without_targets_is_rejected" {
  command = plan
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    rules = { lonely = { schedule_expression = "rate(1 day)", targets = {} } }
  }
  expect_failures = [var.rules]
}

run "a_schedule_on_a_custom_bus_is_rejected" {
  command = plan
  module {
    source = "../../modules/eventbridge"
  }
  variables {
    create_bus = true
  }
  expect_failures = [aws_cloudwatch_event_rule.this]
}
