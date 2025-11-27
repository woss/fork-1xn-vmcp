# Test Coverage Status

## Summary

**Original TypeScript Tests:** 6 test files  
**Ported Python Tests:** 6 test files  
**Coverage:** 100% (all tests ported)

## Test Files Status

### ✅ All Tests Ported

1. **`test/config-validation.test.ts`** → **`tests/test_config_validation.py`**
   - Tests configuration validation (domain patterns, filesystem paths, etc.)
   - Status: ✅ Complete (9 tests)

2. **`test/configurable-proxy-ports.test.ts`** → **`tests/test_configurable_proxy_ports.py`**
   - Tests external proxy port configuration
   - Tests HTTP proxy port configuration
   - Tests SOCKS proxy port configuration
   - Tests mixed external/local proxy scenarios
   - Status: ✅ Complete (8 tests)

3. **`test/sandbox/integration.test.ts`** → **`tests/test_integration.py`**
   - Integration tests for sandbox functionality
   - Tests pre-generated BPF files
   - Tests seccomp filter generation
   - Tests network and filesystem restrictions
   - Status: ✅ Complete (20+ tests)

4. **`test/sandbox/macos-seatbelt.test.ts`** → **`tests/test_macos_seatbelt.py`**
   - Tests macOS Seatbelt read bypass prevention
   - Tests file move/rename blocking
   - Tests glob pattern handling
   - Tests ancestor directory protection
   - Status: ✅ Complete (10+ tests, macOS-only)

5. **`test/sandbox/seccomp-filter.test.ts`** → **`tests/test_seccomp_filter.py`**
   - Tests Linux seccomp filter generation
   - Tests pre-generated BPF file detection
   - Tests seccomp binary path resolution
   - Tests architecture detection
   - Status: ✅ Complete (20+ tests, Linux-only)

6. **`test/sandbox/wrap-with-sandbox.test.ts`** → **`tests/test_wrap_with_sandbox.py`**
   - Tests `wrapWithSandbox` with custom config
   - Tests main config vs custom config
   - Tests platform-specific wrapping (Linux/macOS)
   - Tests filesystem and network restrictions
   - Status: ✅ Complete (19 tests)

## Test Statistics

- **Total Test Files:** 6
- **Total Test Cases:** ~90+ individual tests
- **Platform Coverage:**
  - Cross-platform tests: ~40 tests
  - Linux-specific tests: ~30 tests
  - macOS-specific tests: ~20 tests

## Test Categories

### Configuration Tests
- ✅ Config validation (9 tests)
- ✅ Proxy port configuration (8 tests)

### Integration Tests
- ✅ End-to-end sandbox functionality (20+ tests)
- ✅ Network restrictions
- ✅ Filesystem restrictions
- ✅ Command execution
- ✅ Shell selection
- ✅ Security boundaries

### Platform-Specific Tests
- ✅ macOS Seatbelt tests (10+ tests)
- ✅ Linux seccomp filter tests (20+ tests)
- ✅ Platform-specific wrapping tests

## Running Tests

### Run All Tests
```bash
cd sandbox-runtime-py
source .venv/bin/activate
pytest
```

### Run Specific Test File
```bash
pytest tests/test_config_validation.py
pytest tests/test_wrap_with_sandbox.py
pytest tests/test_integration.py
```

### Run Platform-Specific Tests
```bash
# Linux-only tests
pytest tests/test_seccomp_filter.py
pytest tests/test_integration.py

# macOS-only tests
pytest tests/test_macos_seatbelt.py
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Coverage
```bash
pytest --cov=sandbox_runtime --cov-report=html
```

## Test Framework Migration

**Original:** Bun test framework (`bun:test`)  
**Ported:** pytest framework (`pytest`)

### Key Differences

1. **Test Structure:**
   - TypeScript: `describe()` / `it()` blocks
   - Python: `class` with `pytest.mark.asyncio` for async tests

2. **Async Handling:**
   - TypeScript: Native async/await
   - Python: `pytest.mark.asyncio` decorator

3. **Platform Skipping:**
   - TypeScript: `if (skipIfNotLinux()) return`
   - Python: `@pytest.mark.skipif()` decorator or `pytest.skip()`

4. **Fixtures:**
   - TypeScript: `beforeAll()` / `afterAll()`
   - Python: `@pytest.fixture()` with `autouse=True` or scope management

## Notes

- Some tests require platform-specific dependencies (bwrap, socat, ripgrep)
- Some tests require root/admin privileges for full functionality
- Integration tests may need mock servers for network testing
- Tests are designed to skip gracefully on unsupported platforms
- Socket server tests use threading for async handling
- File system tests use temporary directories that are cleaned up automatically

## Success! 🎉

All tests from the original TypeScript project have been successfully ported to Python!
