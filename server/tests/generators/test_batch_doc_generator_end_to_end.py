"""End-to-end tests for BatchDocGenerator to improve coverage."""

from server.generators.batch_doc_generator import BatchDocGenerator


APP_CODE_OK = """
class MyApp:
    def initialize(self):
        self.listen_state(self.on_change, "sensor.temp", new="on", duration=5)
        self.listen_event(self.on_mqtt, topic="home/topic", namespace="mqtt", qos=1, retain=False)
        self.run_every(self.tick, 0, 10)
        self.turn_on("light.kitchen")
        self.call_service("light.toggle", entity_id="light.kitchen")

    def on_change(self, entity, attribute, old, new, kwargs):
        if new == "on":
            self.turn_on("light.kitchen")
"""

APP_CODE_BAD = """
class Broken:
    def initialize(self)
        pass
"""


def test_generate_all_docs_success(tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    (apps / "app1.py").write_text(APP_CODE_OK)

    gen = BatchDocGenerator(apps, docs)
    results = gen.generate_all_docs(force_regenerate=True)

    assert results["successful"] == 1
    assert results["failed"] == 0
    out = docs / "app1.md"
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# App1")


def test_generate_all_docs_skip_when_exists(tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    (apps / "app1.py").write_text(APP_CODE_OK)
    # Pre-create output to trigger skip
    (docs / "app1.md").write_text("existing")

    gen = BatchDocGenerator(apps, docs)
    results = gen.generate_all_docs(force_regenerate=False)
    assert results["skipped"] == 1
    assert str(apps / "app1.py") in results["skipped_files"]


def test_generate_single_file_error(tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    bad = apps / "broken.py"
    bad.write_text(APP_CODE_BAD)

    gen = BatchDocGenerator(apps, docs)
    content, ok = gen.generate_single_file_docs(bad)
    assert ok is False
    assert content.startswith("# Error Generating Documentation")


def test_generate_index_file_contains_sections(tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    (apps / "app1.py").write_text(APP_CODE_OK)

    gen = BatchDocGenerator(apps, docs)
    index = gen.generate_index_file()
    assert "## Statistics" in index
    assert "## Available Documentation" in index
