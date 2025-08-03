"""Pytest configuration and fixtures for AppDaemon Documentation Server tests."""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest
import requests
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Playwright configuration
PLAYWRIGHT_CONFIG = {
    "base_url": "http://127.0.0.1:8080",
    "browser_timeout": 30000,
    "action_timeout": 10000,
    "navigation_timeout": 30000,
    "headless": True,  # Always run headless for CI compatibility
    "slow_mo": 0,
}

# Viewport sizes for responsive testing
VIEWPORTS = {
    "desktop": {"width": 1920, "height": 1080},
    "laptop": {"width": 1366, "height": 768},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 667},
}


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the documentation server."""
    return PLAYWRIGHT_CONFIG["base_url"]


@pytest.fixture(scope="session")
def temp_apps_dir(tmp_path_factory) -> Path:
    """Create a temporary apps directory with sample Python files for testing."""
    apps_dir = tmp_path_factory.mktemp("test_apps")

    # Create sample Python automation files
    sample_files = {
        "test_automation.py": '''"""Test automation module for documentation testing."""

import appdaemon.plugins.hass.hassapi as hass


class TestAutomation(hass.Hass):
    """A test automation class for documentation generation testing.

    This automation demonstrates various features:
    - Class inheritance from Hass
    - Multiple methods with different purposes
    - Proper documentation strings
    - Type hints and error handling
    """

    def initialize(self):
        """Initialize the automation with listeners and schedules."""
        self.log("Initializing test automation")

        # Listen for state changes
        self.listen_state(self.on_light_change, "light.living_room")

        # Schedule daily actions
        self.run_daily(self.daily_routine, "07:00:00")

    def on_light_change(self, entity: str, attribute: str, old: str, new: str, kwargs: dict):
        """Handle light state changes.

        Args:
            entity: The entity that changed
            attribute: The attribute that changed
            old: Previous state
            new: New state
            kwargs: Additional keyword arguments
        """
        if new == "on":
            self.log(f"Light {entity} turned on")
            self.handle_light_on(entity)
        elif new == "off":
            self.log(f"Light {entity} turned off")

    def daily_routine(self, kwargs: dict):
        """Execute daily routine tasks.

        Args:
            kwargs: Scheduler keyword arguments
        """
        self.log("Running daily routine")
        self.check_all_lights()
        self.send_status_notification()

    def handle_light_on(self, entity: str) -> None:
        """Handle when a light is turned on.

        Args:
            entity: The light entity that was turned on
        """
        # Example logic for handling light activation
        if self.get_state("sun.sun") == "below_horizon":
            self.log(f"Light {entity} turned on after sunset")

    def check_all_lights(self) -> list[str]:
        """Check status of all lights and return active ones.

        Returns:
            List of currently active light entities
        """
        active_lights = []
        all_lights = self.get_state("light")

        for light, state in all_lights.items():
            if state == "on":
                active_lights.append(light)

        return active_lights

    def send_status_notification(self) -> None:
        """Send a status notification via the notification system."""
        active_lights = self.check_all_lights()
        message = f"Daily status: {len(active_lights)} lights currently active"

        self.call_service("notify/mobile_app",
                         title="Daily Status",
                         message=message)
'''
    }

    # Write sample files
    for filename, content in sample_files.items():
        (apps_dir / filename).write_text(content)

    return apps_dir


@pytest.fixture(scope="session")
def start_test_server(temp_apps_dir) -> Generator[str, None, None]:
    """Start the documentation server for testing."""
    # Create temporary docs directory
    docs_dir = Path(tempfile.mkdtemp(prefix="test_docs_"))

    # Set environment variables
    env = os.environ.copy()
    env.update({
        "APPS_DIR": str(temp_apps_dir),
        "DOCS_DIR": str(docs_dir),
        "HOST": "127.0.0.1",
        "PORT": "8080",
        "LOG_LEVEL": "warning",
        "FORCE_REGENERATE": "true",
        "ENABLE_FILE_WATCHER": "false",  # Disable for testing
    })

    # Start server process
    server_process = subprocess.Popen(
        ["uv", "run", "python", "server/run-dev.py"],
        cwd="/home/myakove/git/appdaemon-docs-server",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    base_url = "http://127.0.0.1:8080"
    max_retries = 30
    for _ in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        time.sleep(1)
    else:
        server_process.terminate()
        raise RuntimeError("Server failed to start within timeout period")

    try:
        yield base_url
    finally:
        # Clean up
        server_process.terminate()
        server_process.wait(timeout=10)

        # Clean up temporary directories
        import shutil

        shutil.rmtree(docs_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def playwright():
    """Create playwright instance."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    """Launch browser for testing."""
    browser = playwright.chromium.launch(headless=PLAYWRIGHT_CONFIG["headless"], slow_mo=PLAYWRIGHT_CONFIG["slow_mo"])
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture
def browser_context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create a browser context with common settings."""
    context = browser.new_context(
        viewport=VIEWPORTS["desktop"],
        ignore_https_errors=True,
    )

    try:
        yield context
    finally:
        context.close()


@pytest.fixture
def page(browser_context: BrowserContext, start_test_server: str) -> Generator[Page, None, None]:
    """Create a page with the documentation server loaded."""
    page = browser_context.new_page()

    # Set timeouts
    page.set_default_timeout(PLAYWRIGHT_CONFIG["action_timeout"])
    page.set_default_navigation_timeout(PLAYWRIGHT_CONFIG["navigation_timeout"])

    # Navigate to the documentation server
    page.goto(start_test_server)

    # Wait for page to be fully loaded
    page.wait_for_load_state("networkidle")

    try:
        yield page
    finally:
        page.close()


@pytest.fixture(params=["light", "dark"])
def theme_mode(request) -> str:
    """Parametrize tests to run in both light and dark themes."""
    return request.param


@pytest.fixture(params=list(VIEWPORTS.keys()))
def viewport_size(request) -> dict:
    """Parametrize tests to run in different viewport sizes."""
    return VIEWPORTS[request.param]
