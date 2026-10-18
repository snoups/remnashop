import pytest
from pydantic import ValidationError

from app.core.config.cabinet import CabinetConfig


def test_url_is_https_on_the_domain() -> None:
    assert CabinetConfig(domain="cabinet.example.com").url == "https://cabinet.example.com"


@pytest.mark.parametrize("domain", [None, "", "  "])
def test_blank_domain_means_no_cabinet(domain: str) -> None:
    config = CabinetConfig(domain=domain)
    assert config.domain is None
    assert config.url == ""


@pytest.mark.parametrize("domain", ["https://cabinet.example.com", "cabinet.example.com/"])
def test_domain_rejects_a_scheme_or_trailing_slash(domain: str) -> None:
    with pytest.raises(ValidationError):
        CabinetConfig(domain=domain)
