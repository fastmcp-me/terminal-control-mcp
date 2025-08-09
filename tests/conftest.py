#!/usr/bin/env python3
"""
Centralized pytest configuration and fixtures for the MCP server test suite
"""

import asyncio
import logging
import os
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from types import SimpleNamespace

import pytest

# Add project root to Python path before any project imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Project imports after path modification (ruff: disable E402)
from src.terminal_control_mcp.security import SecurityManager  # noqa: E402
from src.terminal_control_mcp.session_manager import SessionManager  # noqa: E402

# === Core Fixtures ===


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def security_manager() -> SecurityManager:
    """Create a SecurityManager instance for testing"""
    return SecurityManager()


@pytest.fixture
def session_manager() -> SessionManager:
    """Create a SessionManager instance for testing (sync version)"""
    return SessionManager()


@pytest.fixture
async def async_session_manager() -> AsyncGenerator[SessionManager, None]:
    """Create a SessionManager instance for testing (async version with cleanup)"""
    manager = SessionManager()
    yield manager
    # Clean up the manager after the test
    await manager.shutdown()


@pytest.fixture
def app_context(
    security_manager: SecurityManager, session_manager: SessionManager
) -> SimpleNamespace:
    """Create application context with managers for integration tests"""
    return SimpleNamespace(
        security_manager=security_manager,
        session_manager=session_manager,
        web_server=None,  # Mock web server as None for tests
    )


@pytest.fixture
async def async_app_context(
    security_manager: SecurityManager, async_session_manager: SessionManager
) -> SimpleNamespace:
    """Create async application context with managers for integration tests"""
    return SimpleNamespace(
        security_manager=security_manager,
        session_manager=async_session_manager,
        web_server=None,  # Mock web server as None for tests
    )


@pytest.fixture
def mock_context(app_context: SimpleNamespace) -> SimpleNamespace:
    """Create mock MCP context for tool call tests"""
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=app_context)
    )


@pytest.fixture
async def async_mock_context(async_app_context: SimpleNamespace) -> SimpleNamespace:
    """Create async mock MCP context for tool call tests"""
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=async_app_context)
    )


# === File System Fixtures ===


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_audit_log_path(temp_dir: str) -> Generator[str, None, None]:
    """Mock audit log path in environment"""
    audit_path = os.path.join(temp_dir, "audit.log")
    with pytest.MonkeyPatch().context() as m:
        m.setenv("MCP_AUDIT_LOG_PATH", audit_path)
        yield audit_path


# === Test Data Fixtures ===


@pytest.fixture
def dangerous_commands() -> list[str]:
    """Dangerous commands that should be blocked"""
    return [
        "rm -rf /",
        "sudo rm -rf /var",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.ext4 /dev/sda1",
        "chmod 777 /etc/passwd",
        "systemctl stop ssh",
    ]


@pytest.fixture
def safe_commands() -> list[str]:
    """Safe commands that should be allowed"""
    return ["echo 'hello world'", "ls -la", "python3 --version", "pwd", "date"]


@pytest.fixture
def malicious_inputs() -> list[str]:
    """Malicious input patterns for injection testing"""
    return [
        "test; rm something",  # shell injection with rm
        "test`cat /etc/passwd`",  # backtick injection
        "test$(malicious_command)",  # command substitution
        "test\x00malicious",  # null byte
    ]


@pytest.fixture
def safe_inputs() -> list[str]:
    """Safe input patterns"""
    return ["hello world", "user@example.com", "normal text with 123"]


@pytest.fixture
def blocked_paths() -> list[str]:
    """Paths that should be blocked"""
    return ["/etc/passwd", "/etc/shadow", "/boot/grub.cfg", "../../../etc/passwd"]


@pytest.fixture
def safe_paths(temp_dir: str) -> list[str]:
    """Paths that should be allowed"""
    return ["/tmp/test.txt", f"{temp_dir}/safe_file.txt", "/var/tmp/upload.log"]


@pytest.fixture
def sample_environment_vars() -> dict[str, dict[str, str]]:
    """Sample environment variables for testing"""
    return {
        "safe": {"CUSTOM_VAR": "value", "DEBUG": "true"},
        "dangerous": {"PATH": "/malicious/path", "LD_PRELOAD": "/malicious/lib.so"},
    }


# === Test Environment Setup ===


@pytest.fixture(scope="session", autouse=True)
def configure_logging() -> None:
    """Configure logging for tests"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during tests
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "test.log"),
        ],
    )


@pytest.fixture(autouse=True)
def clean_environment() -> Generator[None, None, None]:
    """Clean environment variables before each test"""
    original_env = os.environ.copy()

    # Remove test-related environment variables
    test_vars = [key for key in os.environ if key.startswith("MCP_")]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
