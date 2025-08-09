"""Extra coverage for BatchDocGenerator recursive scan."""

from server.generators.batch_doc_generator import BatchDocGenerator


def test_find_automation_files_recursive(tmp_path, monkeypatch):
    # Create nested structure
    apps = tmp_path / "apps"
    apps.mkdir()
    nested = apps / "nested"
    nested.mkdir()

    # Files
    (apps / "a.py").write_text("# a")
    (nested / "b.py").write_text("# b")
    (apps / "const.py").write_text("# excluded")

    monkeypatch.setenv("RECURSIVE_SCAN", "true")

    gen = BatchDocGenerator(apps, tmp_path / "docs")
    files = gen.find_automation_files()

    names = {f.name for f in files}
    assert "a.py" in names
    assert "b.py" in names
    assert "const.py" not in names
