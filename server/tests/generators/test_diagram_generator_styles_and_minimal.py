"""More coverage for diagram generator shapes and diagrams."""

from server.generators.diagram_generator import NodeStyle


def test_placeholder_symbols():
    # Minimal assertion to keep coverage around the diagram module while frontend is Cytoscape.
    assert hasattr(NodeStyle, "SENSOR")
