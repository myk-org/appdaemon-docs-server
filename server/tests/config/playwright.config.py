"""Playwright configuration for AppDaemon Documentation Server UI testing."""


def pytest_configure(config):
    """Configure pytest for Playwright testing."""
    config.addinivalue_line("markers", "ui: mark test as UI test using Playwright")
    config.addinivalue_line("markers", "theme: mark test as theme-related test")
    config.addinivalue_line("markers", "accessibility: mark test as accessibility test")
    config.addinivalue_line("markers", "performance: mark test as performance test")


# Playwright configuration
PLAYWRIGHT_CONFIG = {
    "base_url": "http://127.0.0.1:8080",
    "browser_timeout": 30000,
    "action_timeout": 10000,
    "navigation_timeout": 30000,
    "headless": True,  # Set to False for debugging
    "slow_mo": 0,  # Milliseconds to slow down operations
    "screenshot": "only-on-failure",
    "video": "retain-on-failure",
    "trace": "retain-on-failure",
}

# Test browsers to run
BROWSERS = ["chromium", "firefox", "webkit"]

# Viewport sizes for responsive testing
VIEWPORTS = {
    "desktop": {"width": 1920, "height": 1080},
    "laptop": {"width": 1366, "height": 768},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 667},
}

# Color contrast thresholds (WCAG AA compliance)
CONTRAST_RATIOS = {
    "normal_text": 4.5,
    "large_text": 3.0,
    "graphical_objects": 3.0,
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "first_contentful_paint": 2000,  # ms
    "largest_contentful_paint": 4000,  # ms
    "cumulative_layout_shift": 0.1,
    "total_blocking_time": 300,  # ms
}
