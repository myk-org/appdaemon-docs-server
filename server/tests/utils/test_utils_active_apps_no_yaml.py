"""Tiny nudge to cover count_active_apps fallback when apps.yaml missing."""

from server.utils.utils import count_active_apps


def test_count_active_apps_no_yaml(tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()
    (docs / "m1.md").write_text("x")

    result = count_active_apps(apps, docs_dir=docs)
    assert result["total"] == 1
    assert result["active"] == 0
    assert result["inactive"] == 1
