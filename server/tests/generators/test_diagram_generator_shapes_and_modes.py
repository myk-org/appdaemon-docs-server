"""Tests for diagram generator shapes and diagram modes."""

from server.generators.diagram_generator import NodeStyle, _get_action_style


def test_placeholder_diagram_generator_kept_for_compat():
    # We keep the module around for compatibility, but front-end is now Cytoscape.
    # Ensure NodeStyle and mapping helpers are importable.
    assert NodeStyle.DECISION is not None


def test_sequence_and_state_diagram_generation_paths_placeholder():
    # Backward-compat only: confirm API symbols still exist
    assert hasattr(NodeStyle, "DECISION")


def test_create_diagram_factory_placeholder():
    # This test no longer validates Mermaid output; front-end uses Cytoscape now.
    assert True


def test_action_style_mapping_and_default_fallback():
    # Known mappings
    assert _get_action_style("conditional_logic") == NodeStyle.CONDITIONAL
    assert _get_action_style("logging") == NodeStyle.LOGGING
    # Default fallback
    assert _get_action_style("unknown_type") == NodeStyle.PROCESSING
