"""Additional coverage for diagram generator."""

from server.generators.diagram_generator import (
    create_diagram,
    create_architecture_diagram,
    create_method_flow_diagram,
    NodeStyle,
)


class DummyMethod:
    def __init__(self):
        # Build a few fake actions to exercise styles
        self.actions = [
            type("A", (), {"action_type": "conditional_logic", "description": "Conditional"})(),
            type("A", (), {"action_type": "device_action", "description": "Device"})(),
            type("A", (), {"action_type": "logging", "description": "Log"})(),
        ]
        self.conditional_count = 1
        self.loop_count = 0
        self.notification_count = 0
        self.device_action_count = 1


class DummyClass:
    def __init__(self):
        self.methods = [
            type(
                "M",
                (),
                {
                    "is_callback": True,
                    "name": "on_event",
                    "conditional_count": 0,
                    "loop_count": 0,
                    "notification_count": 0,
                    "device_action_count": 0,
                    "actions": [],
                },
            )()
        ]


class DummyParsed:
    def __init__(self):
        self.classes = [DummyClass()]


def test_create_diagram_flowchart():
    cfg = {
        "type": "flowchart",
        "direction": "LR",
        "nodes": [
            {"id": "n1", "label": "Start", "style": NodeStyle.PROCESSING.name},
            {"id": "n2", "label": "End", "style": NodeStyle.ACTION.name},
        ],
        "connections": [{"from": "n1", "to": "n2", "label": "go"}],
    }
    md = create_diagram(cfg)
    assert "flowchart LR" in md
    assert "style n2" in md


def test_create_architecture_diagram_with_default_structure():
    d = DummyParsed()
    out = create_architecture_diagram(d)
    assert "flowchart TD" in out


def test_create_method_flow_diagram():
    method = DummyMethod()
    out = create_method_flow_diagram(method)
    assert "flowchart TD" in out
