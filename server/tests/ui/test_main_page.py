"""Test cases for the main documentation page UI and functionality."""

import pytest
import re
from playwright.sync_api import Page, expect


@pytest.mark.ui
class TestMainPageBasics:
    """Test basic functionality of the main documentation page."""

    def test_page_loads_successfully(self, page: Page):
        """Test that the main page loads without errors."""
        # Check that page has loaded
        expect(page).to_have_title("AppDaemon Documentation")

        # Check for main container
        container = page.locator(".container")
        expect(container).to_be_visible()

        # Check for main heading
        heading = page.locator("h1")
        expect(heading).to_be_visible()
        expect(heading).to_contain_text("AppDaemon Documentation")

    def test_documentation_files_displayed(self, page: Page):
        """Test that documentation files are displayed correctly."""
        # Wait for files to load
        file_grid = page.locator(".file-grid")
        expect(file_grid).to_be_visible()

        # Check for file cards
        file_cards = page.locator(".file-card")
        expect(file_cards.first).to_be_visible()

        # Check that file cards have required elements
        first_card = file_cards.first
        expect(first_card.locator(".file-title")).to_be_visible()
        expect(first_card.locator(".file-meta")).to_be_visible()

    def test_stats_section_displays(self, page: Page):
        """Test that the stats section displays correctly."""
        stats_section = page.locator(".stats")
        expect(stats_section).to_be_visible()

        # Verify stats show file count with "documentation files available"
        expect(stats_section).to_contain_text("documentation files available")

        # Verify stats have numbers
        expect(stats_section).to_contain_text(re.compile(r"\d+"))


@pytest.mark.ui
class TestNavigationAndInteraction:
    """Test navigation and interactive elements."""

    def test_file_card_click_navigation(self, page: Page):
        """Test that clicking file cards navigates to document pages."""
        # Wait for file cards to load
        file_cards = page.locator(".file-card")
        expect(file_cards.first).to_be_visible()

        # The file card itself is the link
        first_card = file_cards.first

        # Click and verify navigation
        first_card.click()

        # Should navigate to a document page
        expect(page).to_have_url(re.compile(r"/docs/[^/]+"))

        # Should have document page elements
        expect(page.locator(".content")).to_be_visible()
        expect(page.locator(".breadcrumb")).to_be_visible()

    def test_view_toggle_functionality(self, page: Page):
        """Test view toggle between grid and list views."""
        # Check for view toggle buttons
        grid_btn = page.locator("#gridView")
        list_btn = page.locator("#listView")

        expect(grid_btn).to_be_visible()
        expect(list_btn).to_be_visible()

        # Should start in grid view
        file_grid = page.locator(".file-grid")
        file_list = page.locator(".file-list")
        expect(file_grid).to_be_visible()

        # Switch to list view
        list_btn.click()
        page.wait_for_timeout(200)  # Allow transition

        expect(file_list).to_be_visible()
        expect(file_grid).to_be_hidden()

        # Switch back to grid view
        grid_btn.click()
        page.wait_for_timeout(200)  # Allow transition

        expect(file_grid).to_be_visible()
        expect(file_list).to_be_hidden()

    def test_search_functionality(self, page: Page):
        """Test search functionality."""
        search_input = page.locator("#searchInput")
        expect(search_input).to_be_visible()

        # Type in search
        search_input.fill("test")
        page.wait_for_timeout(500)  # Wait for debounce

        # Search results should appear
        search_results = page.locator("#searchResults")
        expect(search_results).to_be_visible()


@pytest.mark.ui
class TestRegenerateAllButton:
    """Test the regenerate all documentation button."""

    def test_regenerate_button_present(self, page: Page):
        """Test that the regenerate all button is present and visible."""
        regenerate_btn = page.locator("#regenerateAllBtn")
        expect(regenerate_btn).to_be_visible()
        expect(regenerate_btn).to_contain_text("Regenerate All")

    def test_regenerate_button_interaction(self, page: Page):
        """Test regenerate button click interaction."""
        regenerate_btn = page.locator("#regenerateAllBtn")
        expect(regenerate_btn).to_be_visible()

        # Click regenerate button
        regenerate_btn.click()

        # Should show processing state
        expect(regenerate_btn).to_have_class(re.compile(r"(loading|processing)"))

        # Wait for completion (with timeout)
        page.wait_for_timeout(3000)


@pytest.mark.ui
class TestWebSocketStatus:
    """Test WebSocket status indicator."""

    def test_websocket_indicator_present(self, page: Page):
        """Test that WebSocket status indicator is present."""
        ws_status = page.locator("#websocketStatus")
        expect(ws_status).to_be_visible()

    def test_websocket_connection_status(self, page: Page):
        """Test WebSocket connection status updates."""
        ws_status = page.locator("#websocketStatus")
        expect(ws_status).to_be_visible()

        # Should eventually show connected or connecting status
        page.wait_for_timeout(2000)  # Allow connection time

        # Check for status text (could be "Live Updates", "Connected", "Connecting", etc.)
        expect(ws_status).to_contain_text(re.compile(r"(Live Updates|Connect|Connected|Connecting)"))


@pytest.mark.ui
class TestResponsiveDesign:
    """Test responsive design elements."""

    @pytest.mark.parametrize("viewport", ["desktop", "laptop", "tablet", "mobile"])
    def test_mobile_viewport_layout(self, page: Page, viewport: str):
        """Test layout in different viewport sizes."""
        # Set viewport size
        viewports = {
            "desktop": {"width": 1920, "height": 1080},
            "laptop": {"width": 1366, "height": 768},
            "tablet": {"width": 768, "height": 1024},
            "mobile": {"width": 375, "height": 667},
        }

        page.set_viewport_size(viewports[viewport])
        page.reload()

        # Check that main elements are still visible
        expect(page.locator(".container")).to_be_visible()
        expect(page.locator("h1")).to_be_visible()

    def test_theme_toggle_mobile_positioning(self, page: Page):
        """Test theme toggle positioning on mobile."""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.reload()

        theme_toggle = page.locator("#themeToggle")
        expect(theme_toggle).to_be_visible()


@pytest.mark.ui
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_no_files_state(self, page: Page):
        """Test behavior when no files are available."""
        # This test assumes the server might have no files
        # The page should handle this gracefully
        expect(page.locator(".container")).to_be_visible()

    def test_search_no_results(self, page: Page):
        """Test search with no results."""
        search_input = page.locator("#searchInput")
        search_input.fill("nonexistentterm123")
        page.wait_for_timeout(500)

        # Should show no results message
        search_results = page.locator("#searchResults")
        if search_results.is_visible():
            expect(search_results).to_contain_text("No Results")


@pytest.mark.ui
class TestAccessibility:
    """Test accessibility features."""

    def test_keyboard_navigation(self, page: Page):
        """Test keyboard navigation support."""
        # Focus on first interactive element
        page.keyboard.press("Tab")

        # Should be able to navigate with keyboard
        focused_element = page.evaluate("document.activeElement.tagName")
        assert focused_element in ["BUTTON", "A", "INPUT"]

    def test_aria_labels_and_roles(self, page: Page):
        """Test ARIA labels and roles."""
        # Check for aria-labels on buttons
        theme_toggle = page.locator("#themeToggle")
        expect(theme_toggle).to_have_attribute("title", re.compile(r"Theme"))

        search_input = page.locator("#searchInput")
        expect(search_input).to_have_attribute("placeholder", re.compile(r".*"))

    def test_color_contrast_indicators(self, page: Page):
        """Test that color contrast is adequate."""
        # This is a basic test - the actual contrast is tested in other files
        # Check that text is visible against backgrounds
        heading = page.locator("h1")
        expect(heading).to_be_visible()

        file_cards = page.locator(".file-card")
        if file_cards.count() > 0:
            expect(file_cards.first).to_be_visible()
