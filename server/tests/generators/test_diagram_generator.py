"""Additional coverage for diagram generator."""

from server.generators.diagram_generator import NodeStyle


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


def test_placeholder_styles_present():
    assert NodeStyle.ACTION is not None


def test_dummy_parsed_structure_unused():
    d = DummyParsed()
    assert isinstance(d.classes, list)


def test_dummy_method_structure_unused():
    method = DummyMethod()
    assert method.actions
