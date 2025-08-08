"""More coverage for diagram generator shapes and diagrams."""

from server.generators.diagram_generator import MermaidDiagramGenerator, create_diagram


def test_format_node_shapes_and_sequence_state():
    gen = MermaidDiagramGenerator()
    gen.add_node("d1", "Decision", shape="diamond")
    gen.add_node("c1", "Circle", shape="circle")
    gen.add_node("r1", "Round", shape="round")
    gen.add_edge("d1", "c1", label="L1")
    fc = gen.generate_flowchart("LR")
    assert "d1{Decision}" in fc
    assert "c1((Circle))" in fc
    assert "r1(Round)" in fc
    assert "LR" in fc

    # Sequence diagram
    cfg_seq = {
        "type": "sequence",
        "participants": ["A", "B"],
        "connections": [{"from": "A", "to": "B", "label": "hello"}],
    }
    sd = create_diagram(cfg_seq)
    assert "sequenceDiagram" in sd
    assert "A->>B: hello" in sd

    # State diagram
    cfg_state = {
        "type": "state",
        "nodes": [{"id": "S1", "label": "Start"}, {"id": "S2", "label": "End"}],
        "connections": [{"from": "S1", "to": "S2", "label": "go"}],
    }
    st = create_diagram(cfg_state)
    assert "stateDiagram-v2" in st
    assert "S1 --> S2 : go" in st
