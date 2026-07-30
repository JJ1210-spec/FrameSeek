"""
Per-thread stdout capture.

The core package reports progress with ``print()``.  The job worker runs the
pipeline on its own thread, so we install a stdout proxy that routes writes
from *registered* threads to a per-job sink (line by line) and everything else
to the real stdout unchanged.  Captured lines are also echoed to the server
console so ``uvicorn`` output still shows pipeline progress.
"""

import io
import sys
import threading
from contextlib import contextmanager
from typing import Callable

LineSink = Callable[[str], None]

_install_lock = threading.Lock()


class ThreadRoutedStream(io.TextIOBase):
    def __init__(self, original):
        self.original = original
        self._sinks: dict[int, LineSink] = {}
        self._partial: dict[int, str] = {}

    # --- registration ---

    def register(self, sink: LineSink) -> None:
        tid = threading.get_ident()
        self._sinks[tid] = sink
        self._partial[tid] = ""

    def unregister(self) -> None:
        tid = threading.get_ident()
        leftover = self._partial.pop(tid, "")
        sink = self._sinks.pop(tid, None)
        if sink is not None and leftover.strip():
            sink(leftover.rstrip("\r"))

    @property
    def has_sinks(self) -> bool:
        return bool(self._sinks)

    # --- TextIOBase ---

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        tid = threading.get_ident()
        sink = self._sinks.get(tid)
        try:
            self.original.write(text)
        except Exception:
            pass
        if sink is None:
            return len(text)
        data = self._partial.get(tid, "") + text
        *lines, rest = data.split("\n")
        self._partial[tid] = rest
        for line in lines:
            sink(line.rstrip("\r"))
        return len(text)

    def flush(self) -> None:
        try:
            self.original.flush()
        except Exception:
            pass


@contextmanager
def capture_thread_output(sink: LineSink):
    """Route this thread's ``print`` output to *sink*, one line per call."""
    with _install_lock:
        router = sys.stdout if isinstance(sys.stdout, ThreadRoutedStream) else None
        if router is None:
            router = ThreadRoutedStream(sys.stdout)
            sys.stdout = router
        router.register(sink)
    try:
        yield
    finally:
        with _install_lock:
            router.unregister()
            if not router.has_sinks and sys.stdout is router:
                sys.stdout = router.original
