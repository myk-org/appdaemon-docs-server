"""
Batch AppDaemon Documentation Generator

This module provides a command-line interface and batch processing capabilities
for generating documentation for multiple AppDaemon automation files at once.
"""

from pathlib import Path
from typing import Any, Callable

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import parse_appdaemon_file

# NOTE: Shell-like paths (e.g., ~/appdaemon/apps) require expansion via os.path.expanduser()
# or pathlib.Path.expanduser(). The server and dev runner should expand ~ and environment
# variables before passing paths to this generator. Additionally, pointing APPS_DIR to
# large directories or NFS-mounted filesystems may impact performance with file watching.


class BatchDocGenerator:
    """Batch processor for generating AppDaemon documentation."""

    def __init__(self, apps_dir: str | Path, docs_dir: str | Path):
        """
        Initialize the batch generator.

        Args:
            apps_dir: Directory containing AppDaemon Python files
            docs_dir: Directory to output generated documentation
        """
        self.apps_dir = Path(apps_dir)
        self.docs_dir = Path(docs_dir)
        self.doc_generator = AppDaemonDocGenerator(str(self.docs_dir))

        # Ensure docs directory exists
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def apps_yaml_path(self) -> Path | None:
        """
        Get the apps.yaml path if it exists.

        This property provides consistent access to the apps.yaml configuration file
        and caches the result to avoid repeated file existence checks.

        Returns:
            Path to apps.yaml if it exists, None otherwise
        """
        if not hasattr(self, "_apps_yaml_path"):
            apps_yaml_candidate = self.apps_dir / "apps.yaml"
            self._apps_yaml_path = apps_yaml_candidate if apps_yaml_candidate.exists() else None
        return self._apps_yaml_path

    def find_automation_files(self) -> list[Path]:
        """
        Find all AppDaemon automation Python files.

        Returns:
            List of Python file paths in the apps directory
        """
        python_files = list(self.apps_dir.glob("*.py"))

        # Filter out common non-automation files
        excluded_files = {
            "const.py",
            "infra.py",
            "utils.py",
            "__init__.py",
            "apps.py",
            "configuration.py",
            "secrets.py",
        }

        automation_files = [f for f in python_files if f.name not in excluded_files]

        return sorted(automation_files)

    def generate_single_file_docs(self, file_path: Path) -> tuple[str, bool]:
        """
        Generate documentation for a single automation file.

        Args:
            file_path: Path to the Python automation file

        Returns:
            Tuple of (documentation_content, success_flag)
        """
        try:
            # Parse the file with apps.yaml context
            parsed_file = parse_appdaemon_file(file_path, apps_yaml_path=self.apps_yaml_path)

            # Generate documentation
            docs = self.doc_generator.generate_documentation(parsed_file)

            return docs, True

        except Exception as e:
            error_msg = "# Error Generating Documentation\n\n"
            error_msg += f"**File**: {file_path}\n"
            error_msg += f"**Error**: {str(e)}\n\n"
            error_msg += "Please check the Python file for syntax errors or parsing issues.\n"

            return error_msg, False

    def generate_all_docs(
        self, force_regenerate: bool = False, progress_callback: Callable[[int, int, str, str], None] | None = None
    ) -> dict[str, Any]:
        """
        Generate documentation for all automation files.

        Args:
            force_regenerate: If True, regenerate even if docs already exist
            progress_callback: Optional callback function(current, total, current_file, stage)

        Returns:
            Dictionary with generation results and statistics
        """
        automation_files = self.find_automation_files()
        results: dict[str, Any] = {
            "total_files": len(automation_files),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "generated_files": [],
            "failed_files": [],
            "skipped_files": [],
        }

        print(f"Found {len(automation_files)} automation files to process...")

        for idx, file_path in enumerate(automation_files, 1):
            output_file = self.docs_dir / f"{file_path.stem}.md"

            # Call progress callback
            if progress_callback:
                progress_callback(idx, len(automation_files), file_path.name, "checking")

            # Check if we should skip existing files
            if not force_regenerate and output_file.exists():
                print(f"⏭️  Skipping {file_path.name} (docs already exist)")
                results["skipped"] += 1
                results["skipped_files"].append(str(file_path))

                if progress_callback:
                    progress_callback(idx, len(automation_files), file_path.name, "skipped")
                continue

            print(f"📝 Generating docs for {file_path.name}...")

            if progress_callback:
                progress_callback(idx, len(automation_files), file_path.name, "generating")

            # Generate documentation
            docs, success = self.generate_single_file_docs(file_path)

            # Write to output file
            output_file.write_text(docs, encoding="utf-8")

            if success:
                print(f"✅ Generated: {output_file.name}")
                results["successful"] += 1
                results["generated_files"].append(str(output_file))

                if progress_callback:
                    progress_callback(idx, len(automation_files), file_path.name, "completed")
            else:
                print(f"❌ Failed: {file_path.name}")
                results["failed"] += 1
                results["failed_files"].append(str(file_path))

                if progress_callback:
                    progress_callback(idx, len(automation_files), file_path.name, "failed")

        return results

    def generate_index_file(self) -> str:
        """
        Generate an index file listing all available documentation.

        Returns:
            Content of the index file
        """
        automation_files = self.find_automation_files()

        index_content = "# AppDaemon Automation Documentation Index\n\n"
        index_content += (
            "This directory contains automatically generated documentation for AppDaemon automation modules.\n\n"
        )

        # Statistics
        index_content += "## Statistics\n\n"
        index_content += f"- **Total Automation Files**: {len(automation_files)}\n"

        # Parse files to get statistics
        total_classes = 0
        total_listeners = 0
        total_methods = 0

        for file_path in automation_files:
            try:
                parsed_file = parse_appdaemon_file(file_path, apps_yaml_path=self.apps_yaml_path)
                total_classes += len(parsed_file.classes)
                for class_info in parsed_file.classes:
                    total_listeners += len(class_info.state_listeners)
                    total_methods += len([m for m in class_info.methods if m.name != "initialize"])
            except Exception:
                continue

        index_content += f"- **Total Classes**: {total_classes}\n"
        index_content += f"- **Total State Listeners**: {total_listeners}\n"
        index_content += f"- **Total Methods**: {total_methods}\n\n"

        # File listing
        index_content += "## Available Documentation\n\n"

        # Group by category based on filename patterns
        categories = {
            "Climate & Environment": ["climate", "temperature", "boiler", "ac"],
            "Security & Access": ["entrance", "lock", "alarm", "door", "security"],
            "Lighting & Motion": ["light", "motion", "sensor", "lux"],
            "Entertainment & Media": ["tv", "media", "receiver", "android", "remote"],
            "Appliances & Monitoring": ["kettle", "washer", "dryer", "printer", "server"],
            "Communication & Notifications": ["telegram", "notify", "message", "alert"],
            "Presence & Tracking": ["presence", "person", "battery", "phone"],
            "General & Utilities": [],
        }

        categorized_files: dict[str, list[Path]] = {cat: [] for cat in categories.keys()}
        uncategorized: list[Path] = []

        for file_path in automation_files:
            file_stem = file_path.stem.lower()
            categorized = False

            for category, keywords in categories.items():
                if category == "General & Utilities":
                    continue
                if any(keyword in file_stem for keyword in keywords):
                    categorized_files[category].append(file_path)
                    categorized = True
                    break

            if not categorized:
                uncategorized.append(file_path)

        # Add uncategorized to General & Utilities
        categorized_files["General & Utilities"] = uncategorized

        # Generate category sections
        for category, files in categorized_files.items():
            if not files:
                continue

            index_content += f"### {category}\n\n"

            for file_path in sorted(files):
                doc_file = f"{file_path.stem}.md"
                title = self._format_title(file_path.stem)

                # Try to get a brief description
                try:
                    parsed_file = parse_appdaemon_file(file_path, apps_yaml_path=self.apps_yaml_path)
                    if parsed_file.classes and parsed_file.classes[0].docstring:
                        description = parsed_file.classes[0].docstring.split("\n")[0]
                    else:
                        description = f"Automation for {title.lower()}"
                except Exception:
                    description = "Automation module"

                index_content += f"- **[{title}]({doc_file})**: {description}\n"

            index_content += "\n"

        # Generation info
        index_content += "## Documentation Generation\n\n"
        index_content += "This documentation is automatically generated from Python source code using:\n\n"
        index_content += "- **Parser**: AST-based Python code analysis\n"
        index_content += "- **Diagrams**: Mermaid flowcharts and architecture diagrams\n"
        index_content += "- **Templates**: Standardized markdown structure\n\n"
        index_content += "To regenerate documentation:\n\n"
        index_content += "### Local Development\n"
        index_content += "```bash\n"
        index_content += "# Run the development server with file watching enabled\n"
        index_content += "uv run server/run-dev.py\n"
        index_content += "\n"
        index_content += "# Or manually trigger regeneration via API\n"
        index_content += "curl -X POST http://localhost:8080/api/generate/all?force=true\n"
        index_content += "```\n\n"
        index_content += "### Container Environment\n"
        index_content += "```bash\n"
        index_content += "# Inside the container, use the API endpoint\n"
        index_content += "curl -X POST http://localhost:8080/api/generate/all?force=true\n"
        index_content += "\n"
        index_content += "# Or connect to the running container and run Python directly\n"
        index_content += 'docker exec -it <container_name> python -c "\n'
        index_content += "from server.generators.batch_doc_generator import BatchDocGenerator;\n"
        index_content += "generator = BatchDocGenerator('/app/apps', '/app/docs');\n"
        index_content += 'generator.generate_all_docs(force_regenerate=True)"\n'
        index_content += "```\n"

        return index_content

    def _format_title(self, file_name: str) -> str:
        """Convert filename to readable title."""
        title = file_name.replace("_", " ").title()

        # Handle common abbreviations
        replacements = {
            "Ac": "AC",
            "Ir": "IR",
            "Tv": "TV",
            "Api": "API",
            "Mqtt": "MQTT",
            "Http": "HTTP",
            "Ssl": "SSL",
            "Dnd": "DND",
            "Ble": "BLE",
            "Wifi": "WiFi",
        }

        for old, new in replacements.items():
            title = title.replace(old, new)

        return title
