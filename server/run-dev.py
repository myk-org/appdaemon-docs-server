#!/usr/bin/env python3
"""
Development server runner for AppDaemon Documentation Server

This script sets up the proper environment and runs the server locally for development.
Supports both native Python execution and Docker container deployment.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def validate_env_file() -> Path:
    """Validate that .dev_env file exists and return its path."""
    project_root = Path(__file__).parent.parent.resolve()
    env_file = project_root / ".dev_env"

    if not env_file.exists():
        print("❌ Error: .dev_env file not found!")
        print("💡 Create a .dev_env file with required environment variables")
        print(f"   Expected location: {env_file}")
        sys.exit(1)

    return env_file


def run_container() -> None:
    """Run the development server in a container."""
    env_file = validate_env_file()
    project_root = env_file.parent

    # Load environment to get APPS_DIR for mounting
    load_dotenv(env_file)

    apps_dir = os.environ.get("APPS_DIR")
    if not apps_dir:
        print("❌ Error: APPS_DIR not found in .dev_env file!")
        print("💡 APPS_DIR is required for container to access AppDaemon apps")
        sys.exit(1)

    apps_path = Path(os.path.expandvars(os.path.expanduser(apps_dir))).resolve()

    # Note: Apps directory can be anywhere on the system for flexibility
    # No path restrictions enforced - allows documentation of external AppDaemon installations

    if not apps_path.exists():
        print(f"⚠️  Warning: Apps directory does not exist: {apps_path}")

    print("📦 Starting AppDaemon Documentation Server in Docker container")
    print(f"📄 Using environment file: {env_file}")
    print(f"📂 Mounting apps directory: {apps_path} → /apps")
    print("📁 Building container from current directory...")

    # Build the container
    try:
        subprocess.run(
            ["docker", "build", "-t", "appdaemon-docs-server:dev", str(project_root)],
            check=True,
            cwd=project_root,
        )
        print("✅ Container built successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to build Docker container")
        sys.exit(1)

    # Run the container with both project and apps directory mounted
    print("🚀 Starting container...")
    print("🌐 Server will be available at: http://127.0.0.1:8080")
    print("💡 Press Ctrl+C to stop the container")
    print()

    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-p",
                "8080:8080",
                "--env-file",
                ".dev_env",
                "-v",
                f"{apps_path}:/apps:ro",
                "appdaemon-docs-server:dev",
            ],
            check=True,
            cwd=project_root,
        )
    except subprocess.CalledProcessError:
        print("❌ Failed to run Docker container")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping container...")


def run_local_python() -> None:
    """Run the development server with local Python (with auto-reload)."""
    env_file = validate_env_file()

    # Load environment variables from .dev_env
    load_dotenv(env_file)

    print("🚀 Starting AppDaemon Documentation Server (Local Python Mode)")
    print(f"📄 Using environment file: {env_file}")

    # Validate required environment variables
    required_vars = ["APPS_DIR", "HOST", "PORT"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        print("❌ Error: Missing required environment variables in .dev_env:")
        for var in missing_vars:
            print(f"   - {var}")
        sys.exit(1)

    # Get apps directory path (can be anywhere on the system)
    apps_dir = os.environ["APPS_DIR"]
    apps_path = Path(os.path.expandvars(os.path.expanduser(apps_dir))).resolve()

    # Note: No path restrictions - allows documentation of external AppDaemon installations

    print(f"📂 Apps directory: {apps_path}")
    host = os.environ["HOST"]
    # Validate PORT is an integer and within valid range
    raw_port = os.environ["PORT"]
    try:
        port = int(raw_port)
    except ValueError:
        print(f"❌ Error: Invalid PORT value '{raw_port}'. PORT must be an integer between 1 and 65535.")
        print("💡 Update the PORT value in your .dev_env file and try again.")
        sys.exit(1)

    if not (0 < port < 65536):
        print(f"❌ Error: PORT {port} is out of range. PORT must be between 1 and 65535.")
        print("💡 Update the PORT value in your .dev_env file and try again.")
        sys.exit(1)
    print(f"🌐 Server will be available at: http://{host}:{port}")
    print()

    if apps_path.exists():
        print("✅ Apps directory found - documentation will be generated")
    else:
        print("⚠️  Apps directory not found - create it and add AppDaemon files")
    print()

    # Prefer invoking uvicorn via subprocess with --reload; this uses the
    # reloader supervisor which is more reliable than in-process reload.
    project_root = env_file.parent
    reload_dirs = [
        str(project_root / "server"),
        str(project_root / "server" / "templates"),
        str(project_root / "server" / "static"),
    ]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "server.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--reload",
    ]
    for d in reload_dirs:
        cmd.extend(["--reload-dir", d])

    # Exclude tests from triggering reloads during development
    cmd.extend([
        "--reload-exclude",
        str(project_root / "server" / "tests"),
    ])

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("❌ Failed to start dev server (uvicorn).")
        print(f"   Exit code: {e.returncode}")
        print("💡 Check your .dev_env settings, port availability, and app imports.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping dev server...")


def main() -> None:
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run AppDaemon Documentation Server in development mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run server/run-dev.py # Run with `uv`
  uv run server/run-dev.py --container # Run in Docker container

Note: Both modes require a .dev_env file with environment variables
        """,
    )

    parser.add_argument(
        "--container",
        help="Run in container using Docker",
        action="store_true",
    )

    args = parser.parse_args()

    if args.container:
        run_container()
    else:
        run_local_python()


if __name__ == "__main__":
    main()
