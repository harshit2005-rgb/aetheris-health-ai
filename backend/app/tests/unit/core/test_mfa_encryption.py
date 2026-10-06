"""MFA secret encryption at rest — the helpers and the key configuration.

No database. ``conftest`` gives the suite a random key for the run; tests that
need a different key configuration swap it on the settings singleton.
"""

from __future__ import annotations

from typing import Any

import pyotp
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.core.security import (
    MfaEncryptionNotConfiguredError,
    MfaSecretDecryptionError,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_totp_secret,
    is_encrypted_mfa_secret,
    mfa_secret_needs_reencryption,
    verify_totp_code,
)


def _key() -> str:
    return Fernet.generate_key().decode()


def _use_keys(
    monkeypatch: pytest.MonkeyPatch, current: str | None, previous: str | None = None
) -> None:
    monkeypatch.setattr(
        settings, "MFA_ENCRYPTION_KEY", SecretStr(current) if current is not None else None
    )
    monkeypatch.setattr(
        settings,
        "MFA_ENCRYPTION_PREVIOUS_KEYS",
        SecretStr(previous) if previous is not None else None,
    )


def _settings(**values: Any) -> Settings:
    """Build settings from explicit values only — no environment, no ``.env``."""
    values.setdefault("MFA_ENCRYPTION_KEY", None)
    values.setdefault("MFA_ENCRYPTION_PREVIOUS_KEYS", None)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class TestEncryptAndDecrypt:
    def test_a_secret_survives_the_round_trip(self) -> None:
        secret = generate_totp_secret()
        assert decrypt_mfa_secret(encrypt_mfa_secret(secret)) == secret

    def test_the_stored_value_is_not_the_secret(self) -> None:
        secret = generate_totp_secret()
        stored = encrypt_mfa_secret(secret)

        assert stored != secret
        assert secret not in stored
        assert is_encrypted_mfa_secret(stored)

    def test_a_plaintext_secret_is_not_mistaken_for_ciphertext(self) -> None:
        for _ in range(50):
            assert not is_encrypted_mfa_secret(generate_totp_secret())

    def test_the_same_secret_encrypts_differently_each_time(self) -> None:
        """Equal secrets must not be recognisable as equal in the database."""
        secret = generate_totp_secret()
        assert encrypt_mfa_secret(secret) != encrypt_mfa_secret(secret)

    def test_a_decrypted_secret_still_verifies_a_code(self) -> None:
        secret = generate_totp_secret()
        stored = encrypt_mfa_secret(secret)

        assert verify_totp_code(decrypt_mfa_secret(stored), pyotp.TOTP(secret).now())


class TestInvalidCiphertext:
    def test_a_value_encrypted_under_another_key_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stored = encrypt_mfa_secret(generate_totp_secret())
        _use_keys(monkeypatch, _key())

        with pytest.raises(MfaSecretDecryptionError):
            decrypt_mfa_secret(stored)

    def test_a_tampered_value_is_refused(self) -> None:
        stored = encrypt_mfa_secret(generate_totp_secret())
        flipped = "A" if stored[-10] != "A" else "B"
        tampered = stored[:-10] + flipped + stored[-9:]

        with pytest.raises(MfaSecretDecryptionError):
            decrypt_mfa_secret(tampered)

    @pytest.mark.parametrize("stored", ["", "not-a-token", "gAAAAAtruncated", "ünïcödé"])
    def test_garbage_is_refused(self, stored: str) -> None:
        with pytest.raises(MfaSecretDecryptionError):
            decrypt_mfa_secret(stored)

    def test_a_plaintext_secret_is_refused_not_accepted(self) -> None:
        """A legacy or planted plaintext value never verifies anything."""
        with pytest.raises(MfaSecretDecryptionError):
            decrypt_mfa_secret(generate_totp_secret())

    def test_the_error_does_not_carry_the_stored_value(self) -> None:
        stored = "gAAAAA-some-stored-value-that-must-not-leak"
        with pytest.raises(MfaSecretDecryptionError) as raised:
            decrypt_mfa_secret(stored)

        assert stored not in str(raised.value)
        assert raised.value.__cause__ is None


class TestMissingKey:
    def test_encrypting_without_a_key_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use_keys(monkeypatch, None)
        with pytest.raises(MfaEncryptionNotConfiguredError):
            encrypt_mfa_secret(generate_totp_secret())

    def test_decrypting_without_a_key_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stored = encrypt_mfa_secret(generate_totp_secret())
        _use_keys(monkeypatch, None)

        with pytest.raises(MfaEncryptionNotConfiguredError):
            decrypt_mfa_secret(stored)
        with pytest.raises(MfaEncryptionNotConfiguredError):
            mfa_secret_needs_reencryption(stored)


class TestKeyRotation:
    def test_a_retired_key_still_decrypts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        old, new = _key(), _key()
        _use_keys(monkeypatch, old)
        secret = generate_totp_secret()
        stored = encrypt_mfa_secret(secret)

        _use_keys(monkeypatch, new, previous=old)

        assert decrypt_mfa_secret(stored) == secret
        assert mfa_secret_needs_reencryption(stored) is True

    def test_a_value_under_the_current_key_needs_no_reencryption(self) -> None:
        assert mfa_secret_needs_reencryption(encrypt_mfa_secret(generate_totp_secret())) is False

    def test_new_values_are_written_under_the_current_key_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old, new = _key(), _key()
        _use_keys(monkeypatch, new, previous=old)
        stored = encrypt_mfa_secret(generate_totp_secret())

        # With the retired key gone, the new value must still decrypt.
        _use_keys(monkeypatch, new)
        assert decrypt_mfa_secret(stored)

    def test_several_retired_keys_are_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        oldest, older, new = _key(), _key(), _key()
        _use_keys(monkeypatch, oldest)
        secret = generate_totp_secret()
        stored = encrypt_mfa_secret(secret)

        _use_keys(monkeypatch, new, previous=f"{older}, {oldest}")

        assert decrypt_mfa_secret(stored) == secret

    def test_once_a_retired_key_is_removed_its_values_no_longer_decrypt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old, new = _key(), _key()
        _use_keys(monkeypatch, old)
        stored = encrypt_mfa_secret(generate_totp_secret())

        _use_keys(monkeypatch, new)

        with pytest.raises(MfaSecretDecryptionError):
            decrypt_mfa_secret(stored)


class TestKeyConfiguration:
    def test_no_key_is_allowed_in_development(self) -> None:
        configured = _settings(APP_ENV="development")
        assert configured.MFA_ENCRYPTION_KEY is None
        assert configured.mfa_encryption_keys() == []

    @pytest.mark.parametrize("environment", ["staging", "production"])
    def test_a_key_is_required_outside_development(self, environment: str) -> None:
        with pytest.raises(ValidationError, match="MFA_ENCRYPTION_KEY is required"):
            _settings(APP_ENV=environment)

    @pytest.mark.parametrize("environment", ["staging", "production"])
    def test_a_valid_key_satisfies_staging_and_production(self, environment: str) -> None:
        key = _key()
        configured = _settings(APP_ENV=environment, MFA_ENCRYPTION_KEY=key)
        assert configured.mfa_encryption_keys() == [key.encode()]

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_key_counts_as_unset(self, blank: str) -> None:
        assert _settings(MFA_ENCRYPTION_KEY=blank).MFA_ENCRYPTION_KEY is None

    @pytest.mark.parametrize(
        "bad_key",
        ["too-short", "x" * 44, Fernet.generate_key().decode()[:-2], "not base64 at all !!"],
    )
    def test_a_malformed_key_is_rejected_at_startup(self, bad_key: str) -> None:
        with pytest.raises(ValidationError, match="MFA_ENCRYPTION_KEY must be a Fernet key"):
            _settings(MFA_ENCRYPTION_KEY=bad_key)

    def test_a_rejected_key_is_not_printed_in_the_error(self) -> None:
        bad_key = "this-is-a-secret-looking-but-malformed-key-value"
        with pytest.raises(ValidationError) as raised:
            _settings(MFA_ENCRYPTION_KEY=bad_key)

        assert bad_key not in str(raised.value)
        assert bad_key not in repr(raised.value)

    def test_a_malformed_retired_key_is_rejected(self) -> None:
        with pytest.raises(
            ValidationError, match="MFA_ENCRYPTION_PREVIOUS_KEYS must be a Fernet key"
        ):
            _settings(MFA_ENCRYPTION_KEY=_key(), MFA_ENCRYPTION_PREVIOUS_KEYS=f"{_key()},nope")

    def test_retired_keys_without_a_current_key_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="MFA_ENCRYPTION_KEY is not"):
            _settings(MFA_ENCRYPTION_PREVIOUS_KEYS=_key())

    def test_retired_keys_are_split_on_commas(self) -> None:
        first, second = _key(), _key()
        configured = _settings(
            MFA_ENCRYPTION_KEY=_key(), MFA_ENCRYPTION_PREVIOUS_KEYS=f" {first} ,{second}, "
        )
        assert configured.mfa_encryption_keys("MFA_ENCRYPTION_PREVIOUS_KEYS") == [
            first.encode(),
            second.encode(),
        ]

    def test_the_key_is_masked_when_settings_are_printed(self) -> None:
        key = _key()
        configured = _settings(MFA_ENCRYPTION_KEY=key, MFA_ENCRYPTION_PREVIOUS_KEYS=key)

        assert key not in repr(configured)
        assert key not in str(configured.model_dump())

    def test_no_key_has_a_default_in_code(self) -> None:
        assert Settings.model_fields["MFA_ENCRYPTION_KEY"].default is None
        assert Settings.model_fields["MFA_ENCRYPTION_PREVIOUS_KEYS"].default is None
