"""Extra tests for utils to cover error branches."""

from unittest.mock import mock_open, patch


from server.utils.utils import count_active_apps


def test_count_active_apps_invalid_yaml(tmp_path, monkeypatch):
    apps_dir = tmp_path / "apps"
    docs_dir = tmp_path / "docs"
    apps_dir.mkdir()
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("x")

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="[not a dict]"), create=True),
    ):
        result = count_active_apps(apps_dir, docs_dir=docs_dir)
        assert result["active"] == 0
        assert result["inactive"] == 1


def test_count_active_apps_io_error(tmp_path):
    apps_dir = tmp_path / "apps"
    docs_dir = tmp_path / "docs"
    apps_dir.mkdir()
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("x")

    # Simulate IOError
    with patch("pathlib.Path.exists", return_value=True), patch("builtins.open", side_effect=OSError("boom")):
        result = count_active_apps(apps_dir, docs_dir=docs_dir)
        assert result["active"] == 0
        assert result["inactive"] == 1
