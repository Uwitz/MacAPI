from unittest.mock import patch

import pytest

from typer import (
    K_ANSI_Q,
    K_COMMAND,
    K_CONTROL,
    K_RETURN,
    K_ANSI_A,
    K_ANSI_Q,
    K_ANSI_Q,
    K_ANSI_Q,
    lock_screen,
    press_return,
    type_char,
    type_string,
    _send_unicode,
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


def _unicode_args(mock_quartz, call_index: int = 0):
    return (
        mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list[call_index].args[1],
        mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list[call_index].args[2],
    )


# ---------------------------------------------------------------------------
# Unicode single-character posting
# ---------------------------------------------------------------------------


def test_type_char_posts_via_session_tap_when_no_secure_input(mock_quartz):
    with patch("typer._secure_input_pid", return_value=None):
        type_char("a")
    # Down + up = 2 session-tap posts
    assert _post_count(mock_quartz) == 2
    assert _to_pid_count(mock_quartz) == 0
    # Both events have the right unicode string
    for call in mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list:
        assert call.args[2] == "a"


def test_type_char_routes_to_secure_input_pid_when_active(mock_quartz):
    """When a process has secure input (e.g., loginwindow with the lock
    screen up), events must go via CGEventPostToPid or they are dropped."""
    with patch("typer._secure_input_pid", return_value=611):
        type_char("a")
    # No session-tap posts; everything goes via PostToPid
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 2
    # PyObjC's signature is (pid, event) — verify PID is first
    for call in mock_quartz.CGEventPostToPid.call_args_list:
        assert call.args[0] == 611
        assert call.args[1] is not None  # the CGEventRef


# ---------------------------------------------------------------------------
# type_string
# ---------------------------------------------------------------------------


def test_type_string_per_character_with_f15_wake(mock_quartz):
    """type_string must:
    - press F15 (keycode 0x40) to wake the lock screen
    - then post each character one at a time via session tap (no secure input)
    """
    with patch("typer._secure_input_pid", return_value=None), \
         patch("typer.time.sleep"):
        type_string("hi")

    # F15 down + up = 2 events via session tap
    f15_calls = [
        c for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        if c.args[1] == 0x40
    ]
    assert len(f15_calls) == 2  # down + up

    # 2 chars × 2 events (down + up) = 4 unicode posts
    # Plus F15's 2 events = 6 total session-tap posts, zero PostToPid
    assert _post_count(mock_quartz) == 6
    assert _to_pid_count(mock_quartz) == 0


def test_type_string_uses_session_tap_when_no_secure_input(mock_quartz):
    with patch("typer._secure_input_pid", return_value=None), \
         patch("typer.time.sleep"):
        type_string("abc")
    # 3 chars × 2 = 6 + F15 × 2 = 8 session-tap posts, zero PostToPid
    assert _post_count(mock_quartz) == 8
    assert _to_pid_count(mock_quartz) == 0


def test_type_string_routes_around_secure_input(mock_quartz):
    with patch("typer._secure_input_pid", return_value=611), \
         patch("typer.time.sleep"):
        type_string("abc")
    # 3 chars × 2 = 6 + F15 × 2 = 8 PostToPid calls, zero session-tap
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 8


def test_type_string_re_resolves_secure_input_pid_per_char(mock_quartz):
    """The secure-input PID can change after the first char (the password
    field acquires its own secure input). Re-resolve per char."""
    # F15 uses the current pid (1 call for pid, 2 for the key down+up).
    # Then each char calls _secure_input_pid() once and posts 2 events.
    # 3 chars × (1 pid + 2 posts) + F15 × (1 pid + 2 posts) = 8 pid calls
    pids = iter([611, 611, 611, 999, 999, 999, 999, 999])
    with patch("typer._secure_input_pid", side_effect=lambda: next(pids)), \
         patch("typer.time.sleep"):
        type_string("abc")
    # Every event goes via PostToPid (secure input active throughout)
    assert _post_count(mock_quartz) == 0
    assert _to_pid_count(mock_quartz) == 8  # 2 (F15) + 2×3 (chars)
    # F15 went to pid 611, then char 1: 611, char 2: 999, char 3: 999
    posted_pids = [c.args[0] for c in mock_quartz.CGEventPostToPid.call_args_list]
    assert posted_pids == [611, 611, 611, 611, 999, 999, 999, 999]


def test_type_string_empty(mock_quartz):
    with patch("typer._secure_input_pid", return_value=None), \
         patch("typer.time.sleep"):
        type_string("")
    # F15 down+up only = 2 session-tap posts, zero PostToPid
    assert _post_count(mock_quartz) == 2
    assert _to_pid_count(mock_quartz) == 0
    f15_calls = [
        c for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        if c.args[1] == 0x40
    ]
    assert len(f15_calls) == 2


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
    """_secure_input_pid returns the kCGSSessionSecureInputPID value
    from the current session dictionary, or None if not set."""
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
