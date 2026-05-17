"""Security utility tests."""
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_password_hash_and_verify():
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token = create_access_token(
        subject="user-id-123",
        org_id="org-id-456",
        role="agent",
    )
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["org_id"] == "org-id-456"
    assert payload["role"] == "agent"
    assert payload["type"] == "access"


def test_refresh_token_type():
    token = create_refresh_token(subject="user-id-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == "user-id-123"


def test_invalid_token_raises():
    try:
        decode_token("not.a.valid.token")
        assert False, "Should have raised"
    except ValueError:
        pass
