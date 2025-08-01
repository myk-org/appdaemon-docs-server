"""
File watching utilities for the AppDaemon documentation server.

This module provides file system monitoring capabilities to automatically
regenerate documentation when Python source files change.
"""

from watchers.file_watcher import FileWatcher, WatchConfig

__all__ = ["FileWatcher", "WatchConfig"]
