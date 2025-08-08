"""Test MarkdownProcessor thread-safe cache clear path."""

from server.processors.markdown import MarkdownProcessor


def test_markdown_clear_cache_safe(tmp_path):
    mdp = MarkdownProcessor()

    # Create a temp markdown file
    f = tmp_path / "t.md"
    f.write_text("# Title\n\ncontent")

    # First render populates cache
    html1 = mdp.process_file(str(f), 123)
    assert "Title" in html1

    # Clear cache path
    mdp.clear_cache()

    # Second render repopulates
    html2 = mdp.process_file(str(f), 124)
    assert "Title" in html2
