"""Unit tests for email formatter utility."""

from app.utils.email_formatter import (
    format_email_address,
    sanitize_domain,
    sanitize_local_part,
)


def test_sanitize_domain() -> None:
    """Test domain URL cleaning and normalization."""
    assert sanitize_domain("  https://www.OpenAI.com/path?arg=1 ") == "openai.com"
    assert sanitize_domain("HTTP://STRIPE.COM") == "stripe.com"
    assert sanitize_domain("google.co.uk") == "google.co.uk"
    assert sanitize_domain("") == ""


def test_sanitize_local_part() -> None:
    """Test local-part username sanitization."""
    assert sanitize_local_part("..sam..altman__") == "sam.altman"
    assert sanitize_local_part(".s.altman.") == "s.altman"
    assert sanitize_local_part("sam--altman") == "sam-altman"
    assert sanitize_local_part("sam!!@#altman") == "samaltman"


def test_format_email_address() -> None:
    """Test full email address formatting."""
    assert format_email_address("sam.altman", "openai.com") == "sam.altman@openai.com"
    assert format_email_address(" .s.altman. ", " https://openai.com ") == "s.altman@openai.com"
    assert format_email_address("", "openai.com") is None
    assert format_email_address("sam", "invalid_domain") is None
