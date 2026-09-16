import pytest

from why_red.redact import redact

# (input, marker that must appear, secret substring that must be gone)
# Secrets are assembled at runtime so no literal ever trips push protection.
CASES = [
    ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "<GITHUB_TOKEN>", "ghp_abc"),
    ("github_pat_11ABCDEFG0123456789_abcdefghijklmnop", "<GITHUB_TOKEN>", "11ABCDEFG"),
    ("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "<AWS_ACCESS_KEY>", "AKIAIOSFODNN7EXAMPLE"),
    ("key sk_live_" + "4eC39HqLyjWDarjtT1zd", "<API_KEY>", "4eC39HqLyjWDarjtT1zd"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.x", "<REDACTED>", "eyJhbGci"),
    ("git clone https://user:s3cret@github.com/o/r.git", "<CREDENTIALS>@github.com", "s3cret"),
    ("Author: Jane <jane.doe@example.com>", "<EMAIL>", "jane.doe"),
    ("connecting to gitserver.corp.local:443", "<INTERNAL_HOST>", "gitserver"),
    ("runner at 10.0.12.7 lost", "<PRIVATE_IP>", "10.0.12.7"),
    ("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----", "<PRIVATE_KEY>", "abc"),
]


@pytest.mark.parametrize(("text", "marker", "secret"), CASES)
def test_pattern_fires(text: str, marker: str, secret: str) -> None:
    out = redact(text)
    assert marker in out
    assert secret not in out


def test_literal_replacements_and_line_count_preserved() -> None:
    text = "line1 AcmeCorp\nline2 ghp_abcdefghijklmnopqrstuvwxyz0123456789\nline3\n"
    out = redact(text, {"AcmeCorp": "<ORG>"})
    assert "<ORG>" in out
    assert "AcmeCorp" not in out
    assert out.count("\n") == text.count("\n")


def test_clean_text_is_untouched() -> None:
    text = "2026-09-16T10:00:00.0Z FAILED tests/test_x.py::test_y - assert 1 == 2\n"
    assert redact(text) == text
