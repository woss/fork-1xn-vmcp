"""Configuration schemas using Pydantic for validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_domain_pattern(value: str) -> str:
    """Validate domain pattern (e.g., "example.com", "*.npmjs.org")."""
    # Reject protocols, paths, ports, etc.
    if "://" in value or "/" in value or ":" in value:
        raise ValueError(
            "Invalid domain pattern. Must not include protocols, paths, or ports."
        )

    # Allow localhost
    if value == "localhost":
        return value

    # Allow wildcard domains like *.example.com
    if value.startswith("*."):
        domain = value[2:]
        # After the *. there must be a valid domain with at least one more dot
        # e.g., *.example.com is valid, *.com is not (too broad)
        if (
            "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError(
                "Invalid wildcard domain. Must have at least 2 parts after the wildcard (e.g., *.example.com)."
            )
        # Count dots - must have at least 2 parts after the wildcard (e.g., example.com)
        parts = domain.split(".")
        if len(parts) < 2 or not all(p for p in parts):
            raise ValueError(
                "Invalid wildcard domain. Must have at least 2 parts after the wildcard."
            )
        return value

    # Reject any other use of wildcards (e.g., *, *., etc.)
    if "*" in value:
        raise ValueError("Invalid domain pattern. Wildcards only allowed as *.example.com")

    # Regular domains must have at least one dot and only valid characters
    if "." not in value or value.startswith(".") or value.endswith("."):
        raise ValueError(
            "Invalid domain pattern. Must be a valid domain (e.g., 'example.com') or wildcard (e.g., '*.example.com')."
        )

    return value


class RipgrepConfig(BaseModel):
    """Ripgrep configuration."""

    model_config = ConfigDict(populate_by_name=True)

    command: str = Field(description="The ripgrep command to execute (e.g., 'rg', 'claude')")
    args: Optional[list[str]] = Field(
        default=None,
        description="Additional arguments to pass before ripgrep args (e.g., ['--ripgrep'])",
    )


class NetworkConfig(BaseModel):
    """Network restrictions configuration."""

    allowed_domains: list[str] = Field(
        default_factory=list,
        alias="allowedDomains",
        description="List of allowed domains (e.g., ['github.com', '*.npmjs.org'])",
    )
    denied_domains: list[str] = Field(
        default_factory=list,
        alias="deniedDomains",
        description="List of denied domains",
    )
    allow_unix_sockets: Optional[list[str]] = Field(
        default=None,
        alias="allowUnixSockets",
        description="Unix socket paths that are allowed (macOS only)",
    )
    allow_all_unix_sockets: Optional[bool] = Field(
        default=None,
        alias="allowAllUnixSockets",
        description="Allow ALL Unix sockets (Linux only - disables Unix socket blocking)",
    )
    allow_local_binding: Optional[bool] = Field(
        default=None,
        alias="allowLocalBinding",
        description="Whether to allow binding to local ports (default: false)",
    )
    http_proxy_port: Optional[int] = Field(
        default=None,
        alias="httpProxyPort",
        ge=1,
        le=65535,
        description="Port of an external HTTP proxy to use instead of starting a local one.",
    )
    socks_proxy_port: Optional[int] = Field(
        default=None,
        alias="socksProxyPort",
        ge=1,
        le=65535,
        description="Port of an external SOCKS proxy to use instead of starting a local one.",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=None,
    )

    @field_validator("allowed_domains", "denied_domains", mode="before")
    @classmethod
    def validate_domains(cls, v):
        """Validate domain patterns."""
        if isinstance(v, list):
            validated = []
            for domain in v:
                try:
                    validated.append(validate_domain_pattern(domain))
                except ValueError as e:
                    raise ValueError(f"Invalid domain '{domain}': {e}") from e
            return validated
        return v


class FilesystemConfig(BaseModel):
    """Filesystem restrictions configuration."""

    model_config = ConfigDict(populate_by_name=True)

    deny_read: list[str] = Field(
        default_factory=list,
        alias="denyRead",
        description="Paths denied for reading",
    )
    allow_read: list[str] = Field(
        default_factory=list,
        alias="allowRead",
        description="Paths allowed for reading",
    )
    allow_write: list[str] = Field(
        default_factory=list,
        alias="allowWrite",
        description="Paths allowed for writing",
    )
    deny_write: list[str] = Field(
        default_factory=list,
        alias="denyWrite",
        description="Paths denied for writing (takes precedence over allowWrite)",
    )

    @field_validator("deny_read", "allow_read", "allow_write", "deny_write", mode="before")
    @classmethod
    def validate_paths(cls, v):
        """Validate that paths are not empty."""
        if isinstance(v, list):
            for path in v:
                if not path or not isinstance(path, str) or len(path.strip()) == 0:
                    raise ValueError("Path cannot be empty")
        return v


# IgnoreViolationsConfig is just a dict, no need for a separate model
# We'll use dict[str, list[str]] directly in SandboxRuntimeConfig


class SandboxRuntimeConfig(BaseModel):
    """Main configuration for Sandbox Runtime."""

    network: NetworkConfig = Field(description="Network restrictions configuration")
    filesystem: FilesystemConfig = Field(
        description="Filesystem restrictions configuration"
    )
    model_config = ConfigDict(populate_by_name=True)

    ignore_violations: Optional[dict[str, list[str]]] = Field(
        default=None,
        alias="ignoreViolations",
        description="Optional configuration for ignoring specific violations",
    )
    enable_weaker_nested_sandbox: Optional[bool] = Field(
        default=None,
        alias="enableWeakerNestedSandbox",
        description="Enable weaker nested sandbox mode (for Docker environments)",
    )
    ripgrep: Optional[RipgrepConfig] = Field(
        default=None,
        description="Custom ripgrep configuration (default: { command: 'rg' })",
    )

    @classmethod
    def from_json(cls, json_data: dict) -> "SandboxRuntimeConfig":
        """Create config from JSON dict, handling camelCase to snake_case conversion."""
        # Recursively convert camelCase to snake_case
        def convert_keys(obj):
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    # Convert camelCase to snake_case
                    snake_key = "".join(
                        ["_" + c.lower() if c.isupper() else c for c in key]
                    ).lstrip("_")
                    result[snake_key] = convert_keys(value)
                return result
            elif isinstance(obj, list):
                return [convert_keys(item) for item in obj]
            else:
                return obj

        converted = convert_keys(json_data)
        return cls(**converted)

