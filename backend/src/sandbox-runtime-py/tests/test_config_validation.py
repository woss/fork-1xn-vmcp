"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError

from sandbox_runtime.config.schemas import SandboxRuntimeConfig


def test_validate_minimal_config():
    """Test that a valid minimal config passes validation."""
    config = {
        "network": {
            "allowedDomains": [],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
    }

    result = SandboxRuntimeConfig.from_json(config)
    assert result is not None
    assert result.network.allowed_domains == []
    assert result.network.denied_domains == []


def test_validate_config_with_valid_domains():
    """Test that config with valid domains passes validation."""
    config = {
        "network": {
            "allowedDomains": ["example.com", "*.github.com", "localhost"],
            "deniedDomains": ["evil.com"],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
    }

    result = SandboxRuntimeConfig.from_json(config)
    assert result is not None
    assert "example.com" in result.network.allowed_domains
    assert "*.github.com" in result.network.allowed_domains


def test_reject_invalid_domain_patterns():
    """Test that invalid domain patterns are rejected."""
    config = {
        "network": {
            "allowedDomains": ["not-a-domain"],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
    }

    with pytest.raises(ValidationError):
        SandboxRuntimeConfig.from_json(config)


def test_reject_domain_with_protocol():
    """Test that domains with protocols are rejected."""
    config = {
        "network": {
            "allowedDomains": ["https://example.com"],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
    }

    with pytest.raises(ValidationError):
        SandboxRuntimeConfig.from_json(config)


def test_reject_empty_filesystem_paths():
    """Test that empty filesystem paths are rejected."""
    config = {
        "network": {
            "allowedDomains": [],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [""],
            "allowWrite": [],
            "denyWrite": [],
        },
    }

    with pytest.raises(ValidationError):
        SandboxRuntimeConfig.from_json(config)


def test_validate_config_with_optional_fields():
    """Test that config with optional fields passes validation."""
    config = {
        "network": {
            "allowedDomains": ["example.com"],
            "deniedDomains": [],
            "allowUnixSockets": ["/var/run/docker.sock"],
            "allowAllUnixSockets": False,
            "allowLocalBinding": True,
        },
        "filesystem": {
            "denyRead": ["/etc/shadow"],
            "allowWrite": ["/tmp"],
            "denyWrite": ["/etc"],
        },
        "ignoreViolations": {
            "*": ["/usr/bin"],
            "git push": ["/usr/bin/nc"],
        },
        "enableWeakerNestedSandbox": True,
    }

    result = SandboxRuntimeConfig.from_json(config)
    assert result is not None
    assert result.network.allow_unix_sockets == ["/var/run/docker.sock"]
    assert result.enable_weaker_nested_sandbox is True


def test_validate_wildcard_domains():
    """Test that wildcard domains are validated correctly."""
    valid_wildcards = ["*.example.com", "*.github.io", "*.co.uk"]
    invalid_wildcards = ["*example.com", "*.com", "*."]

    for domain in valid_wildcards:
        config = {
            "network": {"allowedDomains": [domain], "deniedDomains": []},
            "filesystem": {"denyRead": [], "allowWrite": [], "denyWrite": []},
        }
        result = SandboxRuntimeConfig.from_json(config)
        assert result is not None

    for domain in invalid_wildcards:
        config = {
            "network": {"allowedDomains": [domain], "deniedDomains": []},
            "filesystem": {"denyRead": [], "allowWrite": [], "denyWrite": []},
        }
        with pytest.raises(ValidationError):
            SandboxRuntimeConfig.from_json(config)


def test_validate_custom_ripgrep_command():
    """Test that config with custom ripgrep command passes validation."""
    config = {
        "network": {
            "allowedDomains": [],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
        "ripgrep": {
            "command": "/usr/local/bin/rg",
        },
    }

    result = SandboxRuntimeConfig.from_json(config)
    assert result is not None
    assert result.ripgrep is not None
    assert result.ripgrep.command == "/usr/local/bin/rg"


def test_validate_custom_ripgrep_with_args():
    """Test that config with custom ripgrep command and args passes validation."""
    config = {
        "network": {
            "allowedDomains": [],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [],
            "denyWrite": [],
        },
        "ripgrep": {
            "command": "claude",
            "args": ["--ripgrep"],
        },
    }

    result = SandboxRuntimeConfig.from_json(config)
    assert result is not None
    assert result.ripgrep is not None
    assert result.ripgrep.command == "claude"
    assert result.ripgrep.args == ["--ripgrep"]

