"""Additional utils tests for boolean parsing and error branches."""

import os
import pytest

from server.utils.utils import parse_boolean_env, count_active_apps


def test_parse_boolean_env_truthy_and_falsey(monkeypatch):
    truthy = ["true", "1", "yes", "on", "TrUe"]
    falsey = ["false", "0", "no", "off", ""]

    for val in truthy:
        monkeypatch.setenv("FLAG_T", val)
        assert parse_boolean_env("FLAG_T") is True

    for val in falsey:
        monkeypatch.setenv("FLAG_F", val)
        assert parse_boolean_env("FLAG_F", default="false") is False

    # Default applied when missing
    if "MISSING_X" in os.environ:
        del os.environ["MISSING_X"]
    assert parse_boolean_env("MISSING_X", default="true") is True


def test_count_active_apps_requires_docs_or_stems(tmp_path):
    # When neither docs_dir nor doc_stems provided -> ValueError
    with pytest.raises(ValueError):
        count_active_apps(tmp_path)
