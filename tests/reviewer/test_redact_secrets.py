"""Nothing sensitive may leave the repository or reach the AI: the text is redacted before it goes anywhere."""
from __future__ import annotations

from tools.lib.redact_secrets import REDACTED, sanitize_text, sanitize_tree, sanitize_value

# Built in pieces so that this file never holds a string that looks like a real key.
AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


def test_an_aws_access_key_is_hidden() -> None:
    assert AWS_KEY not in sanitize_text("the key is " + AWS_KEY + " ok")


def test_a_password_assignment_is_hidden_but_its_name_stays() -> None:
    cleaned = sanitize_text('db_password = "hunter2"')
    assert "hunter2" not in cleaned and "db_password" in cleaned


def test_a_terraform_reference_is_not_taken_for_a_secret() -> None:
    assert "var.db_password" in sanitize_text("password = var.db_password")


def test_a_value_under_a_secret_looking_name_is_hidden() -> None:
    assert sanitize_value("anything", key="api_key") == REDACTED


def test_a_value_terraform_marks_sensitive_is_hidden() -> None:
    assert sanitize_value("plain", sensitive_mask=True) == REDACTED


def test_every_string_of_a_nested_structure_is_cleaned() -> None:
    cleaned = sanitize_tree({"a": [{"b": 'token = "abc123"'}], "n": 5})
    assert "abc123" not in str(cleaned) and cleaned["n"] == 5
