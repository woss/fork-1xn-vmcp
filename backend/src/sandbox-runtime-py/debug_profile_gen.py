import asyncio
from sandbox_runtime.sandbox.macos_utils import generate_sandbox_profile

async def main():
    profile = await generate_sandbox_profile(
        read_config=None,
        write_config=None,
        http_proxy_port=None,
        socks_proxy_port=None,
        needs_network_restriction=True, # Simulating restrict network
        allow_unix_sockets=[],
        allow_all_unix_sockets=False,
        allow_local_binding=True, # Often true in dev
        log_tag="DEBUG_TEST",
    )
    with open("debug_prod.sb", "w") as f:
        f.write(profile)
    print("Generated debug_prod.sb")

if __name__ == "__main__":
    asyncio.run(main())
