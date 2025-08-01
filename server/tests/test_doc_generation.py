#!/usr/bin/env python3
"""
Test Script for AppDaemon Documentation Generation System

This script demonstrates the automated documentation generation system
by parsing sample AppDaemon files and generating markdown documentation.
"""

from pathlib import Path

from server.generators.batch_doc_generator import BatchDocGenerator
from server.generators.diagram_generator import create_diagram, quick_flow
from server.generators.doc_generator import generate_appdaemon_docs
from server.parsers.appdaemon_parser import parse_appdaemon_file


def test_single_file_parsing():
    """Test parsing a single AppDaemon file."""
    print("🔍 Testing single file parsing...")

    # Test files (adjust paths if needed)
    test_files = [
        "../../apps/climate.py",
        "../../apps/entrance.py",
    ]

    for file_path in test_files:
        file_path = Path(__file__).parent / file_path

        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        print(f"\n📄 Parsing: {file_path.name}")

        try:
            parsed_file = parse_appdaemon_file(file_path)

            print(f"  ✅ Classes found: {len(parsed_file.classes)}")
            for class_info in parsed_file.classes:
                print(
                    f"     - {class_info.name} ({len(class_info.methods)} methods, {len(class_info.state_listeners)} listeners)"
                )

            print(f"  📦 Imports: {len(parsed_file.imports)}")
            print(f"  🔗 Constants used: {len(parsed_file.constants_used)}")

        except Exception as e:
            print(f"  ❌ Error: {e}")


def test_documentation_generation():
    """Test generating documentation for a sample file."""
    print("\n📝 Testing documentation generation...")

    test_file = Path(__file__).parent / "../../apps/entrance.py"

    if not test_file.exists():
        print(f"⚠️  Test file not found: {test_file}")
        return

    try:
        # Generate documentation
        docs = generate_appdaemon_docs(test_file)

        print(f"✅ Generated {len(docs)} characters of documentation")
        print("📄 Preview (first 300 characters):")
        print("-" * 50)
        print(docs[:300])
        print("-" * 50)

        # Save to test file
        output_file = Path(__file__).parent / "test_output.md"
        output_file.write_text(docs, encoding="utf-8")
        print(f"💾 Saved test output to: {output_file}")

    except Exception as e:
        print(f"❌ Error generating documentation: {e}")


def test_batch_processing():
    """Test batch processing capabilities."""
    print("\n🔄 Testing batch processing...")

    apps_dir = Path(__file__).parent / "../../apps"
    test_docs_dir = Path(__file__).parent / "test_docs_output"

    if not apps_dir.exists():
        print(f"⚠️  Apps directory not found: {apps_dir}")
        return

    try:
        # Create test batch generator
        batch_gen = BatchDocGenerator(apps_dir, test_docs_dir)

        # Find automation files
        automation_files = batch_gen.find_automation_files()
        print(f"🔍 Found {len(automation_files)} automation files:")
        for file_path in automation_files[:5]:  # Show first 5
            print(f"  - {file_path.name}")
        if len(automation_files) > 5:
            print(f"  ... and {len(automation_files) - 5} more")

        # Generate index file as test
        index_content = batch_gen.generate_index_file()
        index_file = test_docs_dir / "test_index.md"
        test_docs_dir.mkdir(exist_ok=True)
        index_file.write_text(index_content, encoding="utf-8")

        print(f"✅ Generated test index: {index_file}")
        print("📄 Index preview (first 200 characters):")
        print("-" * 50)
        print(index_content[:200])
        print("-" * 50)

    except Exception as e:
        print(f"❌ Error in batch processing: {e}")


def test_diagram_generation():
    """Test diagram generation capabilities."""
    print("\n🎨 Testing diagram generation...")

    try:
        # Test quick flow diagram
        steps = [
            {"label": "Door Opens", "style": "SENSOR"},
            {"label": "Check Motion?", "style": "DECISION", "shape": "diamond"},
            {"label": "Turn Light ON", "style": "ACTION"},
            {"label": "Log Event", "style": "COMMUNICATION"},
        ]

        flow_diagram = quick_flow(steps)
        print("✅ Generated quick flow diagram")
        print("📊 Diagram preview (first 200 characters):")
        print("-" * 50)
        print(flow_diagram[:200])
        print("-" * 50)

        # Test complex diagram
        complex_config = {
            "type": "flowchart",
            "direction": "TD",
            "sections": [
                {
                    "id": "sensors",
                    "title": "Sensors",
                    "nodes": [
                        {"id": "door", "label": "Door Sensor", "style": "SENSOR"},
                        {"id": "motion", "label": "Motion Sensor", "style": "SENSOR"},
                    ],
                },
                {
                    "id": "actions",
                    "title": "Actions",
                    "nodes": [{"id": "light", "label": "Turn Light ON", "style": "ACTION"}],
                },
            ],
            "connections": [
                {"from": "door", "to": "light", "label": "Door Opens"},
                {"from": "motion", "to": "light", "label": "Motion Detected"},
            ],
        }

        create_diagram(complex_config)
        print("\n✅ Generated complex diagram")

    except Exception as e:
        print(f"❌ Error generating diagrams: {e}")


def main():
    """Run all tests."""
    print("🚀 AppDaemon Documentation Generation System Test")
    print("=" * 60)

    # Run all tests
    test_single_file_parsing()
    test_documentation_generation()
    test_batch_processing()
    test_diagram_generation()

    print("\n🎉 All tests completed!")
    print("\nNext steps:")
    print("1. Review the generated test files")
    print("2. Run batch generation: python -m batch_doc_generator")
    print("3. Check the generated documentation in apps/docs/")


if __name__ == "__main__":
    main()
