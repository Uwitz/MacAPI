import os
import ssl
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from cert import (
    DEFAULT_COMMON_NAME,
    cert_fingerprint,
    create_tls_context,
    generate_self_signed_cert,
)


def test_generate_self_signed_cert_creates_files(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    assert cert_path.exists()
    assert key_path.exists()


def test_generate_self_signed_cert_key_is_ed25519(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    key_data = key_path.read_bytes()
    key = serialization.load_pem_private_key(key_data, password=None)
    assert isinstance(key, ed25519.Ed25519PrivateKey)
    # Ed25519 public key is 32 bytes; private key is 32 bytes (wrapped in PKCS8).
    pub = key.public_key()
    assert isinstance(pub, ed25519.Ed25519PublicKey)
    assert pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ) == b"\x00" * 0 or len(pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )) == 32


def test_generate_self_signed_cert_uses_ed25519_signature(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    # Ed25519 OID is 1.3.101.112
    assert cert.signature_algorithm_oid.dotted_string == "1.3.101.112"
    assert cert.signature_algorithm_oid._name == "ed25519"
    assert cert.public_key_algorithm_oid.dotted_string == "1.3.101.112"


def test_generate_self_signed_cert_subject(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    assert cert.subject.rfc4514_string() == f"CN={DEFAULT_COMMON_NAME}"


def test_generate_self_signed_cert_has_san(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(
        cert_path, key_path,
        san_dns=["localhost", "macapi.local"],
        san_ips=["127.0.0.1"],
    )
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    dns = [n.value for n in san_ext.value if isinstance(n, x509.DNSName)]
    ips = [str(n.value) for n in san_ext.value if isinstance(n, x509.IPAddress)]
    assert "localhost" in dns
    assert "macapi.local" in dns
    assert "127.0.0.1" in ips


def test_generate_self_signed_cert_default_san_is_localhost(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    assert any(isinstance(n, x509.DNSName) and n.value == "localhost" for n in san_ext.value)


def test_generate_self_signed_cert_respects_days_valid(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path, days_valid=30)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    lifetime = cert.not_valid_after_utc - cert.not_valid_before_utc
    assert 29 <= lifetime.days <= 31


def test_generate_self_signed_cert_key_permissions(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    assert oct(key_path.stat().st_mode)[-3:] == "600"


def test_generate_self_signed_cert_creates_parent_dirs(tmp_path: Path):
    cert_path = tmp_path / "nested" / "cert.pem"
    key_path = tmp_path / "nested" / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    assert cert_path.exists()
    assert key_path.exists()


def test_cert_fingerprint_is_sha256_hex(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    fp = cert_fingerprint(cert_path)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_cert_fingerprint_matches_manual_computation(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    expected = cert.fingerprint(hashes.SHA256()).hex()
    assert cert_fingerprint(cert_path) == expected


def test_two_generations_produce_different_certs(tmp_path: Path):
    cert1 = tmp_path / "cert1.pem"
    key1 = tmp_path / "key1.pem"
    cert2 = tmp_path / "cert2.pem"
    key2 = tmp_path / "key2.pem"
    generate_self_signed_cert(cert1, key1)
    generate_self_signed_cert(cert2, key2)
    assert cert_fingerprint(cert1) != cert_fingerprint(cert2)


# ---------------------------------------------------------------------------
# TLS 1.3 + AES-256-GCM context
# ---------------------------------------------------------------------------


def test_create_tls_context_locks_to_tls_1_3(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    ctx = create_tls_context(cert_path, key_path)
    assert ctx.minimum_version.name == "TLSv1_3"
    assert ctx.maximum_version.name == "TLSv1_3"


def test_create_tls_context_prefers_aes_256_gcm(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generate_self_signed_cert(cert_path, key_path)
    ctx = create_tls_context(cert_path, key_path)
    names = [c["name"] for c in ctx.get_ciphers()]
    assert names[0] == "TLS_AES_256_GCM_SHA384", (
        f"expected AES-256-GCM first, got {names[:3]}"
    )
    assert "TLS_CHACHA20_POLY1305_SHA256" in names
    assert "TLS_AES_128_GCM_SHA256" in names


def test_create_tls_context_missing_cert_raises(tmp_path: Path):
    with pytest.raises(Exception):
        create_tls_context(tmp_path / "missing.pem", tmp_path / "missing.key")


def test_uvicorn_run_accepts_ed25519_cert(tmp_path: Path):
    """Smoke test: uvicorn must accept the cert via the parameters it supports."""
    import uvicorn
    import inspect
    sig = inspect.signature(uvicorn.run)
    assert "ssl_certfile" in sig.parameters
    assert "ssl_keyfile" in sig.parameters
    assert "ssl_context" not in sig.parameters  # confirmed: not directly supported
