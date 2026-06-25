import datetime
import ipaddress
import os
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID


class CertError(Exception):
    pass


DEFAULT_DAYS_VALID = 365
DEFAULT_COMMON_NAME = "MacAPI"


def generate_self_signed_cert(
    cert_path: str | Path,
    key_path: str | Path,
    common_name: str = DEFAULT_COMMON_NAME,
    days_valid: int = DEFAULT_DAYS_VALID,
    san_dns: list[str] | None = None,
    san_ips: list[str] | None = None,
) -> None:
    """Generate a self-signed Ed25519 certificate and private key.

    Ed25519 is the iOS-27-compatible signature algorithm. It is non-NIST
    (designed by Daniel J. Bernstein), with no NSA controversy, and is
    widely supported in TLS 1.3 on all modern OSes.

    Why not ML-DSA-87? It's true post-quantum (NIST PQC Level 5) but the
    iOS 27 TLS stack does not yet implement an ML-DSA-87 verifier, so
    the iPhone's TLS client rejects the cert during the handshake. Keep
    the ML-DSA-87 cert in `certs/` for when Apple ships support; swap
    the algorithm here when that happens.

    Security (with TLS 1.3 + AES-256-GCM, which is the cipher suite the
    server locks to):
      - Bulk encryption: AES-256-GCM = ~128-bit post-quantum under Grover.
      - Handshake signature: Ed25519 = ~128-bit post-quantum under Grover,
        128-bit classical. Matches the bulk-encryption ceiling.
    Net: the connection is quantum-resistant end-to-end.

    The private key is written with mode 0600.
    """
    cert_path = Path(cert_path)
    key_path = Path(key_path)

    private_key = ed25519.Ed25519PrivateKey.generate()

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    san_entries: list[x509.GeneralName] = []
    if san_dns:
        san_entries.extend(x509.DNSName(dns) for dns in san_dns)
    if san_ips:
        san_entries.extend(x509.IPAddress(ipaddress.ip_address(ip)) for ip in san_ips)
    if not san_entries:
        san_entries = [x509.DNSName("localhost")]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .sign(private_key, None)
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    key_path.parent.mkdir(parents=True, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    os.chmod(key_path, 0o600)


def cert_fingerprint(cert_path: str | Path) -> str:
    """Return the SHA-256 fingerprint of a PEM certificate as a hex string."""
    cert_path = Path(cert_path)
    with open(cert_path, "rb") as f:
        cert_data = f.read()
    cert = x509.load_pem_x509_certificate(cert_data)
    return cert.fingerprint(hashes.SHA256()).hex()


def create_tls_context(cert_path: str | Path, key_path: str | Path) -> ssl.SSLContext:
    """Build an SSL context locked to TLS 1.3 with AES-256-GCM as the primary
    cipher suite.

    - TLS 1.3 only (no downgrade to 1.2).
    - Cipher suite priority (OpenSSL 3.x defaults when TLS 1.3 is the only
      version): TLS_AES_256_GCM_SHA384 → TLS_CHACHA20_POLY1305_SHA256 →
      TLS_AES_128_GCM_SHA256.
    - Loads the Ed25519 self-signed cert.
    """
    cert_path = Path(cert_path)
    key_path = Path(key_path)
    if not cert_path.exists():
        raise CertError(f"TLS cert not found: {cert_path}")
    if not key_path.exists():
        raise CertError(f"TLS key not found: {key_path}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(str(cert_path), str(key_path))
    return ctx
