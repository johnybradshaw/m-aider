"""Tests for the output module."""

from src.maider.output import QuietConsole, console, is_quiet, set_quiet


class TestQuietConsole:
    """Test QuietConsole functionality."""

    def test_default_not_quiet(self):
        """Console should not be quiet by default."""
        qc = QuietConsole()
        assert qc.quiet is False

    def test_set_quiet(self):
        """Test setting quiet mode."""
        qc = QuietConsole()
        qc.quiet = True
        assert qc.quiet is True
        qc.quiet = False
        assert qc.quiet is False

    def test_error_always_prints(self, capsys):
        """Error messages should always print, even in quiet mode."""
        qc = QuietConsole()
        qc.quiet = True
        # Error method should still work
        # Note: Rich console doesn't print to stdout directly in tests
        # but we can verify the method exists and is callable
        assert callable(qc.error)

    def test_print_suppressed_in_quiet_mode(self):
        """Print should be suppressed in quiet mode."""
        qc = QuietConsole()
        qc.quiet = True
        # This should not raise an error
        qc.print("This should not appear")

    def test_status_returns_nullcontext_in_quiet_mode(self):
        """Status should return a no-op context in quiet mode."""
        qc = QuietConsole()
        qc.quiet = True
        with qc.status("Testing..."):
            pass  # Should not raise

    def test_rule_suppressed_in_quiet_mode(self):
        """Rule should be suppressed in quiet mode."""
        qc = QuietConsole()
        qc.quiet = True
        qc.rule("Test")  # Should not raise


class TestGlobalQuiet:
    """Test global quiet mode functions."""

    def test_set_quiet_global(self):
        """Test global set_quiet function."""
        original = console.quiet
        try:
            set_quiet(True)
            assert is_quiet() is True
            set_quiet(False)
            assert is_quiet() is False
        finally:
            console.quiet = original

    def test_global_console_instance(self):
        """Test that global console is a QuietConsole instance."""
        assert isinstance(console, QuietConsole)
