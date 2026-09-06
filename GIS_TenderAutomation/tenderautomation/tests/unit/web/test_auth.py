"""PBT tests for auth helpers — bcrypt round-trip."""
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from web.auth import hash_password, verify_password


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep production at 12 rounds while making property tests practical."""
    monkeypatch.setattr("web.auth.BCRYPT_ROUNDS", 4)


class TestBcryptRoundTrip:
    @settings(deadline=None, max_examples=20)
    @given(password=st.text(min_size=8, max_size=72, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="!@#$%^&*"
    )))
    def test_verify_own_hash(self, password):
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    @settings(deadline=None, max_examples=20)
    @given(
        password=st.text(min_size=8, max_size=72),
        wrong=st.text(min_size=8, max_size=72),
    )
    def test_wrong_password_fails(self, password, wrong):
        if password != wrong:
            hashed = hash_password(password)
            assert verify_password(wrong, hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same_password_123")
        h2 = hash_password("same_password_123")
        assert h1 != h2  # different salt each time

    def test_verify_still_works_different_hashes(self):
        h1 = hash_password("same_password_123")
        h2 = hash_password("same_password_123")
        assert verify_password("same_password_123", h1)
        assert verify_password("same_password_123", h2)
