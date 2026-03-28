import pytest
import hmac
import hashlib
from apps.webhooks.validators import verify_github_signature


class TestWebhookSignature:

    def test_valid_signature(self):
        secret = 'mysecret'
        payload = b'{"action": "opened"}'
        sig = 'sha256=' + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        assert verify_github_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        payload = b'{"action": "opened"}'
        assert verify_github_signature(
            payload,
            'sha256=invalidsignature',
            'mysecret',
        ) is False

    def test_wrong_secret(self):
        payload = b'{"action": "opened"}'
        sig = 'sha256=' + hmac.new(
            b'correctsecret',
            payload,
            hashlib.sha256,
        ).hexdigest()
        assert verify_github_signature(payload, sig, 'wrongsecret') is False

    def test_empty_signature(self):
        payload = b'{"action": "opened"}'
        assert verify_github_signature(payload, '', 'mysecret') is False

    def test_empty_secret(self):
        payload = b'{"action": "opened"}'
        assert verify_github_signature(payload, 'sha256=abc', '') is False

    def test_malformed_signature_no_prefix(self):
        payload = b'{"action": "opened"}'
        assert verify_github_signature(
            payload,
            'invalidsignatureformat',
            'mysecret',
        ) is False

    def test_tampered_payload(self):
        secret = 'mysecret'
        original_payload = b'{"action": "opened"}'
        tampered_payload = b'{"action": "deleted"}'
        sig = 'sha256=' + hmac.new(
            secret.encode(),
            original_payload,
            hashlib.sha256,
        ).hexdigest()
        assert verify_github_signature(tampered_payload, sig, secret) is False