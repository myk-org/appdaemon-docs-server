"""Additional tests for MarkdownProcessor cache eviction and clear."""

import tempfile
from server.processors.markdown import MarkdownProcessor


def test_clear_cache_empties_cache():
    p = MarkdownProcessor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# A")
        path = f.name
    try:
        p.process_file(path, 1)
        assert len(p._cache) == 1
        p.clear_cache()
        assert len(p._cache) == 0
    finally:
        pass
