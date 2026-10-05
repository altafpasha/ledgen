import pytest
from app.core.exceptions import SSRFSecurityException
from app.utils.ssrf import validate_url_safety


def test_ssrf_blocks_localhost_and_loopback():
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://localhost:8000/api")

    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://127.0.0.1:8000")

    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://127.0.0.2:9000")


def test_ssrf_blocks_private_networks():
    # 10.0.0.0/8
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://10.0.0.1/admin")

    # 192.168.0.0/16
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://192.168.1.1/router")

    # 172.16.0.0/12
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://172.16.0.5/")


def test_ssrf_blocks_cloud_metadata():
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SSRFSecurityException):
        validate_url_safety("http://metadata.google.internal/computeMetadata/v1/")


def test_ssrf_blocks_unsupported_protocols():
    with pytest.raises(SSRFSecurityException):
        validate_url_safety("ftp://example.com/file")

    with pytest.raises(SSRFSecurityException):
        validate_url_safety("file:///etc/passwd")

    with pytest.raises(SSRFSecurityException):
        validate_url_safety("gopher://example.com")
