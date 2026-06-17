"""File watcher — monitors project directories for changes and triggers re-indexing.

Uses watchdog if available, falls back to polling.

Dependencies:
    watchdog (optional): Provides efficient filesystem event monitoring via
    OS-native APIs (inotify on Linux, FSEvents on macOS, ReadDirectoryChanges
    on Windows). Install with ``pip install watchdog``.

    When watchdog is not installed, the watcher falls back to a polling loop
    that periodically walks the directory tree and checks modification times.
    The polling interval is configurable via ``POLL_INTERVAL`` (default 30s).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from bitmod.project.language import should_index

logger = logging.getLogger(__name__)

# Debounce: collect changes for this many seconds before re-indexing
DEBOUNCE_SECONDS = 5.0

# Polling interval when watchdog is not available
POLL_INTERVAL = 30.0


class ProjectWatcher:
    """Watches a project directory for file changes and triggers callbacks.

    Uses watchdog (preferred) or polling fallback. Changes are debounced
    to avoid excessive re-indexing during rapid edits.
    """

    def __init__(
        self,
        root_path: str,
        on_change: Callable[[set[str]], None],
        debounce: float = DEBOUNCE_SECONDS,
    ):
        """
        Args:
            root_path: Project directory to watch.
            on_change: Callback receiving set of changed relative paths.
            debounce: Seconds to wait before triggering callback after last change.
        """
        self._root = os.path.abspath(root_path)
        self._on_change = on_change
        self._debounce = debounce
        self._changed: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._running = False
        self._observer: Any = None
        self._poll_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start watching for changes."""
        if self._running:
            return

        self._running = True

        # Try watchdog first
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class _Handler(FileSystemEventHandler):
                def __init__(self, watcher: ProjectWatcher):
                    self._watcher = watcher

                def on_any_event(self, event):
                    if event.is_directory:
                        return
                    path = event.src_path
                    if should_index(path, self._watcher._root):
                        rel = os.path.relpath(path, self._watcher._root)
                        self._watcher._enqueue(rel)

            self._observer = Observer()
            self._observer.schedule(_Handler(self), self._root, recursive=True)
            self._observer.daemon = True
            self._observer.start()
            logger.info("Watching %s with watchdog", self._root)

        except ImportError:
            # Fallback to polling
            logger.info("watchdog not available, using polling for %s", self._root)
            self._poll_thread = threading.Thread(
                target=self._poll_loop,
                daemon=True,
            )
            self._poll_thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        if self._timer:
            self._timer.cancel()
            self._timer = None
        # Flush pending changes
        self._flush()

    def _enqueue(self, rel_path: str) -> None:
        """Add a changed path and reset the debounce timer."""
        with self._lock:
            self._changed.add(rel_path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Send accumulated changes to callback."""
        with self._lock:
            if not self._changed:
                return
            paths = self._changed.copy()
            self._changed.clear()

        try:
            self._on_change(paths)
        except Exception:
            logger.exception("Error in change callback")

    def _poll_loop(self) -> None:
        """Polling fallback: track file modification times."""
        mtimes: dict[str, float] = {}

        # Initial scan
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if should_index(full, self._root):
                    rel = os.path.relpath(full, self._root)
                    try:
                        mtimes[rel] = os.path.getmtime(full)
                    except OSError:
                        pass

        while self._running:
            time.sleep(POLL_INTERVAL)
            if not self._running:
                break

            changed: set[str] = set()

            current_files: set[str] = set()
            for dirpath, dirnames, filenames in os.walk(self._root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
                for fname in filenames:
                    full = os.path.join(dirpath, fname)
                    if should_index(full, self._root):
                        rel = os.path.relpath(full, self._root)
                        current_files.add(rel)
                        try:
                            mtime = os.path.getmtime(full)
                        except OSError:
                            continue
                        if rel not in mtimes or mtimes[rel] != mtime:
                            changed.add(rel)
                            mtimes[rel] = mtime

            # Detect deleted files
            deleted = set(mtimes.keys()) - current_files
            for d in deleted:
                del mtimes[d]
                changed.add(d)

            if changed:
                try:
                    self._on_change(changed)
                except Exception:
                    logger.exception("Error in poll change callback")
