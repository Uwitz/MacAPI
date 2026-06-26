from unittest.mock import patch

import pytest

from typer import (
    K_ANSI_Q,
    K_CONTROL,
    K_COMMAND,
    K_RETURN,
    lock_screen,
    press_return,
    type_char,
    type_string,
)


@pytest.fixture
def mock_quartz():
    with patch("typer.Quartz") as mock:
        # Real integer values for flag constants so bitwise & works
        # correctly in tests. Source: Carbon/HIToolbox/Events.h
        mock.kCGEventFlagMaskShift = 1 << 17        # 0x20000
        mock.kCGEventFlagMaskControl = 1 << 18      # 0x40000
        mock.kCGEventFlagMaskAlternate = 1 << 19    # 0x80000
        mock.kCGEventFlagMaskCommand = 1 << 20      # 0x100000
        yield mock


def _post_count(mock_quartz) -> int:
    return mock_quartz.CGEventPost.call_count


# ---------------------------------------------------------------------------
# type_char
# ---------------------------------------------------------------------------


def test_type_char_posts_down_and_up_to_hid_tap(mock_quartz):
    type_char("a")
    assert _post_count(mock_quartz) == 2
    for call in mock_quartz.CGEventPost.call_args_list:
        assert call.args[0] == mock_quartz.kCGHIDEventTap


def test_type_char_replaces_flags_not_ors_with_existing(mock_quartz):
    """If the HID source carries stale Cmd/Control in its state, our
    events must not inherit it. A "3" key event with Cmd+Shift would
    be interpreted as Cmd+Shift+3 → full-screen screenshot."""
    # Simulate the HID source having Cmd held (e.g. user just pressed Cmd+Tab).
    mock_quartz.CGEventGetFlags.return_value = mock_quartz.kCGEventFlagMaskCommand
    type_char("!")
    # "!" is shift+1 — we must set the flag to Shift only, not Cmd|Shift.
    set_calls = mock_quartz.CGEventSetFlags.call_args_list
    for call in set_calls:
        flags = call.args[1]
        assert not (flags & mock_quartz.kCGEventFlagMaskCommand)
        assert not (flags & mock_quartz.kCGEventFlagMaskControl)
        assert not (flags & mock_quartz.kCGEventFlagMaskAlternate)


def test_type_char_no_shift_sets_no_flags(mock_quartz):
    mock_quartz.CGEventGetFlags.return_value = 0
    type_char("a")
    for call in mock_quartz.CGEventSetFlags.call_args_list:
        assert call.args[1] == 0


def test_type_char_shift_sets_shift_flag(mock_quartz):
    mock_quartz.CGEventGetFlags.return_value = 0
    type_char("A")
    for call in mock_quartz.CGEventSetFlags.call_args_list:
        assert call.args[1] & mock_quartz.kCGEventFlagMaskShift


def test_type_char_sets_unicode_string(mock_quartz):
    type_char("a")
    created_events = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
    assert len(created_events) == 2  # down + up
    for call in created_events:
        # keycode arg is 0 for unicode-only events
        assert call.args[1] == 0


def test_type_char_handles_emoji(mock_quartz):
    """A 4-byte UTF-8 emoji is a surrogate pair (2 UTF-16 code units)."""
    type_char("\U0001f600")  # 😀
    set_calls = mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list
    assert len(set_calls) == 2  # one for down, one for up
    for call in set_calls:
        n = call.args[1]
        assert n == 2  # surrogate pair


# ---------------------------------------------------------------------------
# type_string
# ---------------------------------------------------------------------------


def test_type_string_posts_each_char(mock_quartz):
    type_string("hi")
    # 2 chars × 2 events (down+up) = 4
    assert _post_count(mock_quartz) == 4
    for call in mock_quartz.CGEventPost.call_args_list:
        assert call.args[0] == mock_quartz.kCGHIDEventTap


def test_type_string_empty_does_nothing(mock_quartz):
    type_string("")
    assert mock_quartz.CGEventCreateKeyboardEvent.call_count == 0
    assert _post_count(mock_quartz) == 0


# ---------------------------------------------------------------------------
# press_return
# ---------------------------------------------------------------------------


def test_press_return_posts_to_hid_tap(mock_quartz):
    press_return()
    assert _post_count(mock_quartz) == 2
    keycodes = [
        c.args[1]
        for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list
    ]
    assert keycodes == [K_RETURN, K_RETURN]
    for call in mock_quartz.CGEventPost.call_args_list:
        assert call.args[0] == mock_quartz.kCGHIDEventTap


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
