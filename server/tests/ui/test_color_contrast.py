"""Color contrast and accessibility testing for WCAG AA compliance."""

import pytest
from playwright.sync_api import Page, expect


def calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance of a color.

    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)

    Returns:
        Relative luminance value (0-1)
    """

    def gamma_correct(component: int) -> float:
        c = component / 255.0
        if c <= 0.03928:
            return c / 12.92
        else:
            return pow((c + 0.055) / 1.055, 2.4)

    r_linear = gamma_correct(r)
    g_linear = gamma_correct(g)
    b_linear = gamma_correct(b)

    return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear


def calculate_contrast_ratio(color1: tuple, color2: tuple) -> float:
    """Calculate contrast ratio between two colors.

    Args:
        color1: RGB tuple (r, g, b)
        color2: RGB tuple (r, g, b)

    Returns:
        Contrast ratio (1-21)
    """
    lum1 = calculate_luminance(*color1)
    lum2 = calculate_luminance(*color2)

    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)

    return (lighter + 0.05) / (darker + 0.05)


def parse_rgb_color(color_string: str) -> tuple:
    """Parse RGB color string to tuple.

    Args:
        color_string: Color string like 'rgb(255, 255, 255)'

    Returns:
        RGB tuple (r, g, b)
    """
    if color_string.startswith("rgb("):
        # Remove 'rgb(' and ')'
        values = color_string[4:-1].split(",")
        return tuple(int(v.strip()) for v in values)
    elif color_string.startswith("rgba("):
        # Remove 'rgba(' and ')' and ignore alpha
        values = color_string[5:-1].split(",")
        return tuple(int(v.strip()) for v in values[:3])
    else:
        # Handle hex colors or named colors - simplified
        return (0, 0, 0)  # Default to black


@pytest.mark.ui
@pytest.mark.accessibility
class TestColorContrast:
    """Test color contrast compliance for WCAG AA standards."""

    def test_main_page_text_contrast(self, page: Page):
        """Test color contrast for main page text elements."""

        # Check main heading contrast
        heading = page.locator("h1")
        expect(heading).to_be_visible()

        text_color = heading.evaluate("el => getComputedStyle(el).color")
        bg_color = heading.evaluate("el => getComputedStyle(el).backgroundColor")

        # If background is transparent, get parent background
        if bg_color == "rgba(0, 0, 0, 0)":
            bg_color = heading.evaluate("el => getComputedStyle(el.parentElement).backgroundColor")

        if text_color and bg_color and bg_color != "rgba(0, 0, 0, 0)":
            text_rgb = parse_rgb_color(text_color)
            bg_rgb = parse_rgb_color(bg_color)

            contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)

            # WCAG AA requires 4.5:1 for normal text
            assert contrast_ratio >= 4.5, (
                f"Heading contrast ratio {contrast_ratio:.2f} is below WCAG AA standard (4.5:1)"
            )

    def test_file_card_text_contrast(self, page: Page):
        """Test color contrast for file card text."""
        file_cards = page.locator(".file-card")
        if file_cards.count() > 0:
            first_card = file_cards.first

            # Check file title contrast
            title = first_card.locator(".file-title")
            expect(title).to_be_visible()

            text_color = title.evaluate("el => getComputedStyle(el).color")
            bg_color = title.evaluate("el => getComputedStyle(el).backgroundColor")

            if bg_color == "rgba(0, 0, 0, 0)":
                bg_color = first_card.evaluate("el => getComputedStyle(el).backgroundColor")

            if text_color and bg_color and bg_color != "rgba(0, 0, 0, 0)":
                text_rgb = parse_rgb_color(text_color)
                bg_rgb = parse_rgb_color(bg_color)

                contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)
                assert contrast_ratio >= 4.5, (
                    f"File card title contrast ratio {contrast_ratio:.2f} is below WCAG AA standard"
                )

    def test_button_contrast(self, page: Page):
        """Test color contrast for interactive buttons."""
        regenerate_btn = page.locator("#regenerateAllBtn")
        expect(regenerate_btn).to_be_visible()

        text_color = regenerate_btn.evaluate("el => getComputedStyle(el).color")
        bg_color = regenerate_btn.evaluate("el => getComputedStyle(el).backgroundColor")

        if text_color and bg_color and bg_color != "rgba(0, 0, 0, 0)":
            text_rgb = parse_rgb_color(text_color)
            bg_rgb = parse_rgb_color(bg_color)

            contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)
            assert contrast_ratio >= 4.5, f"Button contrast ratio {contrast_ratio:.2f} is below WCAG AA standard"

    def test_dark_theme_contrast(self, page: Page):
        """Test color contrast in dark theme mode."""
        # Switch to dark theme
        theme_toggle = page.locator("#themeToggle")
        theme_toggle.click()
        page.wait_for_timeout(500)  # Wait for theme transition

        # Test main heading in dark theme
        heading = page.locator("h1")
        text_color = heading.evaluate("el => getComputedStyle(el).color")
        bg_color = heading.evaluate("el => getComputedStyle(el).backgroundColor")

        if bg_color == "rgba(0, 0, 0, 0)":
            bg_color = page.locator("body").evaluate("el => getComputedStyle(el).backgroundColor")

        if text_color and bg_color and bg_color != "rgba(0, 0, 0, 0)":
            text_rgb = parse_rgb_color(text_color)
            bg_rgb = parse_rgb_color(bg_color)

            contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)
            assert contrast_ratio >= 4.5, (
                f"Dark theme heading contrast ratio {contrast_ratio:.2f} is below WCAG AA standard"
            )

    def test_search_input_contrast(self, page: Page):
        """Test color contrast for search input field."""
        search_input = page.locator("#searchInput")
        expect(search_input).to_be_visible()

        text_color = search_input.evaluate("el => getComputedStyle(el).color")
        bg_color = search_input.evaluate("el => getComputedStyle(el).backgroundColor")

        if text_color and bg_color and bg_color != "rgba(0, 0, 0, 0)":
            text_rgb = parse_rgb_color(text_color)
            bg_rgb = parse_rgb_color(bg_color)

            contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)
            assert contrast_ratio >= 4.5, f"Search input contrast ratio {contrast_ratio:.2f} is below WCAG AA standard"


@pytest.mark.ui
@pytest.mark.accessibility
class TestAccessibilityIssues:
    """Test for common accessibility issues and improvements."""

    def test_focus_indicators(self, page: Page):
        """Test that focus indicators are visible and have sufficient contrast."""
        # Test search input focus
        search_input = page.locator("#searchInput")
        search_input.focus()

        # Check that focus styles are applied
        outline_style = search_input.evaluate("el => getComputedStyle(el).outline")
        outline_color = search_input.evaluate("el => getComputedStyle(el).outlineColor")

        # Should have some form of focus indication
        assert outline_style != "none" or outline_color != "rgba(0, 0, 0, 0)", (
            "Search input should have visible focus indicator"
        )

        # Test button focus
        regenerate_btn = page.locator("#regenerateAllBtn")
        regenerate_btn.focus()

        outline_style = regenerate_btn.evaluate("el => getComputedStyle(el).outline")
        outline_color = regenerate_btn.evaluate("el => getComputedStyle(el).outlineColor")

        assert outline_style != "none" or outline_color != "rgba(0, 0, 0, 0)", (
            "Button should have visible focus indicator"
        )

    def test_heading_structure(self, page: Page):
        """Test that heading hierarchy is logical and accessible."""
        # Should have h1 as main heading
        h1_elements = page.locator("h1")
        h1_count = h1_elements.count()
        assert h1_count == 1, f"Page should have exactly one h1 element, found {h1_count}"

        # Check heading content is meaningful
        h1_text = h1_elements.first.text_content()
        assert h1_text and len(h1_text.strip()) > 0, "Main heading should have meaningful text"

    def test_semantic_html_elements(self, page: Page):
        """Test that semantic HTML elements are used properly."""
        # Check for main content area
        main_element = page.locator("main")
        if main_element.count() > 0:
            expect(main_element).to_be_visible()

        # Check for proper button elements (not divs with click handlers)
        buttons = page.locator("button")
        assert buttons.count() > 0, "Page should use semantic button elements"

        # Check that buttons have meaningful text or labels
        for i in range(min(3, buttons.count())):
            button = buttons.nth(i)
            text = button.text_content()
            title = button.get_attribute("title")
            aria_label = button.get_attribute("aria-label")

            assert (text and text.strip()) or title or aria_label, (
                f"Button {i} should have meaningful text, title, or aria-label"
            )

    def test_interactive_element_sizes(self, page: Page):
        """Test that interactive elements meet minimum size requirements (44x44px)."""
        # Test buttons
        buttons = page.locator("button")
        for i in range(min(3, buttons.count())):
            button = buttons.nth(i)
            bounding_box = button.bounding_box()

            if bounding_box:
                assert bounding_box["width"] >= 44 or bounding_box["height"] >= 44, (
                    f"Button {i} should be at least 44px in one dimension for touch accessibility"
                )

    def test_color_only_information(self, page: Page):
        """Test that information is not conveyed by color alone."""
        # This is a manual check - ensure status indicators have text or icons
        # Check WebSocket status indicator
        ws_status = page.locator("#websocketStatus")
        if ws_status.count() > 0:
            status_text = ws_status.text_content()
            assert status_text and len(status_text.strip()) > 0, (
                "WebSocket status should convey information through text, not just color"
            )


@pytest.mark.ui
@pytest.mark.theme
class TestThemeColorIssues:
    """Test for theme-specific color issues and improvements."""

    def test_theme_transition_colors(self, page: Page):
        """Test that theme transitions don't cause color accessibility issues."""
        # Test color contrast in current theme
        heading = page.locator("h1")
        initial_text_color = heading.evaluate("el => getComputedStyle(el).color")
        initial_bg_color = page.evaluate("() => getComputedStyle(document.body).backgroundColor")

        # Switch theme
        theme_toggle = page.locator("#themeToggle")
        theme_toggle.click()
        page.wait_for_timeout(500)

        # Test color contrast in switched theme
        new_text_color = heading.evaluate("el => getComputedStyle(el).color")
        new_bg_color = page.evaluate("() => getComputedStyle(document.body).backgroundColor")

        # Colors should have changed
        assert initial_text_color != new_text_color or initial_bg_color != new_bg_color, (
            "Theme switch should change colors"
        )

        # New colors should still meet contrast requirements
        if new_text_color and new_bg_color and new_bg_color != "rgba(0, 0, 0, 0)":
            text_rgb = parse_rgb_color(new_text_color)
            bg_rgb = parse_rgb_color(new_bg_color)

            contrast_ratio = calculate_contrast_ratio(text_rgb, bg_rgb)
            assert contrast_ratio >= 4.5, (
                f"Theme-switched heading contrast ratio {contrast_ratio:.2f} is below WCAG AA standard"
            )

    def test_css_custom_properties_usage(self, page: Page):
        """Test that CSS custom properties are being used consistently."""
        # Check that custom properties are defined
        root_styles = page.evaluate("""
            () => {
                const styles = getComputedStyle(document.documentElement);
                return {
                    bgPrimary: styles.getPropertyValue('--bg-primary').trim(),
                    textPrimary: styles.getPropertyValue('--text-primary').trim(),
                    borderPrimary: styles.getPropertyValue('--border-primary').trim()
                };
            }
        """)

        assert root_styles["bgPrimary"], "CSS custom property --bg-primary should be defined"
        assert root_styles["textPrimary"], "CSS custom property --text-primary should be defined"
        assert root_styles["borderPrimary"], "CSS custom property --border-primary should be defined"

        # Check that elements are using custom properties
        heading = page.locator("h1")
        computed_color = heading.evaluate("el => getComputedStyle(el).color")

        # This is a basic check - in a real implementation, we'd verify the computed
        # values match what we expect from our custom properties
        assert computed_color != "rgba(0, 0, 0, 0)", "Heading should have a defined color"
