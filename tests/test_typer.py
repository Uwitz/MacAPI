from unittest.mock import patch

import pytest

from typer import (
    K_ANSI_Q,
    K_COMMAND,
    K_CONTROL,
    K_RETURN,
    K_ANSI_Q,
    lock_screen,
    press_return,
    type_char,
    type_string,
    _secure_input_pid,
)


@pytest.fixture
def mock_quartz():
    with patch("typer.Quartz") as mock:
        yield mock


def _post_count(mock_quartz) -> int:
    return mock_quartz.CGEventPost.call_count


def _to_pid_count(mock_quartz) -> int:
    return mock_quartz.CGEventPostToPid.call_count


# ---------------------------------------------------------------------------
# type_char
# ---------------------------------------------------------------------------


def test_type_char_posts_via_session_tap_when_no_secure_input(mock_quartz):
    with patch("typer._secure_input_pid", return_value=None):
        type_char("a")
    assert _post_count(mock_quartz) == 2
    assert _to_pid_count(mock_quartz) == 0


def test_type_char_routes_to_secure_input_pid_when_active(mock_quartz):
    with patch("typer._secure_input_pid", return_value=611):
        type_char("a")
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 2
    for call in mock_quartz.CGEventPostToPid.call_args_list:
        assert call.args[0] == 611
        assert call.args[1] is not None


# ---------------------------------------------------------------------------
# type_string
# ---------------------------------------------------------------------------


def test_type_string_posts_each_char(mock_quartz):
    """Each char is posted (down+up = 2 events). No wake key."""
    with patch("typer._secure_input_pid", return_value=None):
        type_string("hi")
    # 2 chars × 2 events (down+up) = 4, no PostToPid
    assert _post_count(mock_quartz) == 4
    assert _to_pid_count(mock_quartz) == 0


def test_type_string_empty_does_nothing(mock_quartz):
    with patch("typer._secure_input_pid", return_value=None):
        type_string("")
    assert mock_quartz.CGEventCreateKeyboardEvent.call_count == 0
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 0


def test_type_string_routes_to_secure_input_pid_when_active(mock_quartz):
    with patch("typer._secure_input_pid", return_value=611):
        type_string("abc")
    # 3 chars × 2 events = 6 PostToPid, 0 session-tap
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 6


def test_type_string_re_resolves_secure_input_pid_per_char(mock_quartz):
    """The secure-input PID can change after the first char (the password
    field acquires its own secure input). Re-resolve per char."""
    pids = iter([611, 611, 999, 999, 999, 999])
    with patch("typer._secure_input_pid", side_effect=lambda: next(pids)):
        type_string("abc")
    # 6 events: 2 (a) + 2 (b) + 2 (c) with PID changing from 611 → 999
    assert _to_pid_count(mock_quartz) == 6
    posted_pids = [c.args[0] for c in mock_quartz.CGEventPostToPid.call_args_list]
    assert posted_pids == [611, 611, 999, 999, 999, 999]


# ---------------------------------------------------------------------------
# press_return
# ---------------------------------------------------------------------------


def test_press_return_routes_around_secure_input(mock_quartz):
    with patch("typer._secure_input_pid", return_value=611):
        press_return()
    assert _to_pid_count(mock_quartz) == 2
    assert _post_count(mock_quartz) == 0
    for call in mock_quartz.CGEventPostToPid.call_args_list:
        assert call.args[0] == 611


# ---------------------------------------------------------------------------
# lock_screen
# ---------------------------------------------------------------------------


def test_lock_screen_sends_ctrl_cmd_q_atomically(mock_quartz):
    lock_screen()
    assert _post_count(mock_quartz) == 2
    codes = [c.args[1] for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list]
    assert codes == [K_ANSI_Q, K_ANSI_Q]
    for call in mock_quartz.CGEventSetFlags.call_args_list:
        flags = call.args[1]
        assert flags & mock_quartz.kCGEventFlagMaskControl
        assert flags & mock_quartz.kCGEventFlagMaskCommand


# ---------------------------------------------------------------------------
# _secure_input_pid
# ---------------------------------------------------------------------------


def test_secure_input_pid_reads_session_dict():
    with patch("typer.Quartz") as mock:
        mock.CGSessionCopyCurrentDictionary.return_value = {
            "kCGSSessionSecureInputPID": 12345,
            "CGSSessionScreenIsLocked": True,
        }
        assert _secure_input_pid() == 12345


def test_secure_input_pid_returns_none_when_not_set():
    with patch("typer.Quartz") as mock:
        mock.CGSessionCopyCurrentDictionary.return_value = {
            "CGSSessionScreenIsLocked": False,
        }
        assert _secure_input_pid() is None
