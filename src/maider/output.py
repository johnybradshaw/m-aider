"""Centralized output handling with quiet mode support."""

from rich.console import Console as RichConsole


class QuietConsole:
    """A console wrapper that respects quiet mode.

    In quiet mode, only errors are printed. Normal output is suppressed.
    """

    def __init__(self):
        self._console = RichConsole()
        self._quiet = False

    @property
    def quiet(self) -> bool:
        return self._quiet

    @quiet.setter
    def quiet(self, value: bool):
        self._quiet = value

    def print(self, *args, **kwargs):
        """Print to console unless in quiet mode."""
        if not self._quiet:
            self._console.print(*args, **kwargs)

    def error(self, *args, **kwargs):
        """Print error messages (always shown, even in quiet mode)."""
        self._console.print(*args, **kwargs)

    def status(self, *args, **kwargs):
        """Create a status context (suppressed in quiet mode)."""
        if self._quiet:
            # Return a no-op context manager
            from contextlib import nullcontext
            return nullcontext()
        return self._console.status(*args, **kwargs)

    def rule(self, *args, **kwargs):
        """Print a rule (suppressed in quiet mode)."""
        if not self._quiet:
            self._console.rule(*args, **kwargs)

    def input(self, *args, **kwargs):
        """Get user input (always available)."""
        return self._console.input(*args, **kwargs)

    @property
    def is_terminal(self) -> bool:
        """Check if output is a terminal."""
        return self._console.is_terminal


# Global console instance
console = QuietConsole()


def set_quiet(quiet: bool):
    """Set global quiet mode."""
    console.quiet = quiet


def is_quiet() -> bool:
    """Check if quiet mode is enabled."""
    return console.quiet
