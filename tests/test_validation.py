import pytest
from app.security.validation import validate_username, validate_message

def test_bad_username():
    with pytest.raises(Exception):
        validate_username("a b")

def test_empty_message():
    with pytest.raises(Exception):
        validate_message("")

def test_valid_message():
    assert validate_message(" hello ") == "hello"
