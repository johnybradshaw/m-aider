"""Tests for check command helpers."""

from unittest.mock import Mock, patch

import pytest

from src.maider.commands import check as check_cmd


class TestCheckHelpers:
    @patch("src.maider.commands.check.SessionManager")
    def test_get_session_or_exit_missing_session(self, mock_sm):
        mock_sm_instance = Mock()
        mock_sm_instance.get_session.return_value = None
        mock_sm.return_value = mock_sm_instance

        with pytest.raises(SystemExit):
            check_cmd._get_session_or_exit(mock_sm_instance, "missing")

    def test_print_gpu_memory_usage_empty(self):
        gpu_monitor = Mock()
        gpu_monitor.get_gpu_info.return_value = []

        with pytest.raises(SystemExit):
            check_cmd._print_gpu_memory_usage(gpu_monitor)

    @patch("src.maider.commands.check.requests.post")
    def test_run_throughput_test_http_error(self, mock_post):
        mock_post.return_value = Mock(status_code=500, json=Mock(return_value={}))
        session = Mock(served_model_name="coder")

        check_cmd._run_throughput_test(session)

    @patch("src.maider.commands.check.requests.post")
    def test_run_throughput_test_request_exception(self, mock_post):
        from requests.exceptions import RequestException

        mock_post.side_effect = RequestException("network down")
        session = Mock(served_model_name="coder")

        check_cmd._run_throughput_test(session)
