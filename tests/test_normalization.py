import pytest
from app.utils.phone import normalize_phone
from app.utils.email import normalize_email, extract_emails_from_text
from app.utils.domains import extract_domain, normalize_website_url
from app.utils.normalization import normalize_business_name, normalize_address


def test_phone_normalization():
    # Valid Indian formats
    assert normalize_phone("+91 98450 12345") == "+919845012345"
    assert normalize_phone("09845012345") == "+919845012345"
    assert normalize_phone("9845012345") == "+919845012345"
    assert normalize_phone("+91-8153-255678") == "+918153255678"

    # Empty / Invalid
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("invalid-phone") is None


def test_email_normalization():
    assert normalize_email("Contact@KolarGoldTech.IN  ") == "contact@kolargoldtech.in"
    assert normalize_email("user.name+tag@domain.co.in") == "user.name+tag@domain.co.in"

    assert normalize_email(None) is None
    assert normalize_email("") is None
    assert normalize_email("not-an-email") is None


def test_email_extraction_from_html():
    raw_html = """
    <html>
        <body>
            <p>Write to us at <a href="mailto:info@myshop.in">info@myshop.in</a> or support@myshop.in</p>
            <p>Do not contact test.png or noreply@myshop.in</p>
        </body>
    </html>
    """
    emails = extract_emails_from_text(raw_html)
    assert "info@myshop.in" in emails
    assert "support@myshop.in" in emails
    assert "noreply@myshop.in" not in emails
    assert "test.png" not in emails


def test_domain_extraction():
    assert extract_domain("https://www.kolargoldtech.in/about-us") == "kolargoldtech.in"
    assert extract_domain("http://kolarsilks.com:8080/products?page=1") == "kolarsilks.com"
    assert extract_domain("https://cloudlogisticslab.co/") == "cloudlogisticslab.co"

    assert extract_domain(None) is None
    assert extract_domain("") is None
    assert extract_domain("not a url") is None


def test_website_url_normalization():
    assert normalize_website_url("kolargoldtech.in") == "https://kolargoldtech.in"
    assert normalize_website_url("http://example.com") == "http://example.com"
    assert normalize_website_url(None) is None
    assert normalize_website_url("") is None


def test_business_name_normalization():
    assert normalize_business_name("Kolar Gold Tech Solutions Pvt Ltd") == "kolar gold tech"
    assert normalize_business_name("Indiranagar Cloud Logistics Lab LLC") == "indiranagar cloud logistics lab"
    assert normalize_business_name("Sri Krishna Grand Hotel & Restaurant") == "sri krishna grand hotel restaurant"
    assert normalize_business_name(None) is None
    assert normalize_business_name("") is None
