from unittest.mock import patch

import pytest

from typer import (
    K_ANSI_Q,
    K_COMMAND,
    K_CONTROL,
    K_RETURN,
    lock_screen,
    press_return,
    type_char,
    type_string,
)


@pytest.fixture
def mock_quartz():
    with patch("typer.Quartz") as mock:
        yield mock


def _event_count(mock_quartz) -> int:
    return mock_quartz.CGEventPost.call_count


def _unicode_args(mock_quartz, call_index: int = 0):
    """Return (length, text) passed to CGEventKeyboardSetUnicodeString."""
    call = mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list[call_index]
    return call.args[1], call.args[2]


def test_type_char_sends_two_events(mock_quartz):
    type_char("a")
    assert _event_count(mock_quartz) == 2  # key down + key up


def test_type_char_sends_unicode(mock_quartz):
    type_char("A")
    length, text = _unicode_args(mock_quartz, call_index=0)
    assert text == "A"
    assert length == 1


def test_type_char_lowercase_sends_unicode(mock_quartz):
    type_char("a")
    length, text = _unicode_args(mock_quartz, call_index=0)
    assert text == "a"


def test_type_char_symbol_sends_unicode(mock_quartz):
    type_char("@")
    length, text = _unicode_args(mock_quartz, call_index=0)
    assert text == "@"


def test_type_char_unicode_supports_specials(mock_quartz):
    """The Unicode API handles any character — no more unsupported-char ValueErrors."""
    for char in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\\":
        mock_quartz.reset_mock()
        type_char(char)
        length, text = _unicode_args(mock_quartz, call_index=0)
        assert text == char


def test_type_char_unicode_supports_unicode(mock_quartz):
    """Accented characters and emoji now work too."""
    for char in "éñü🔐":
        mock_quartz.reset_mock()
        type_char(char)
        length, text = _unicode_args(mock_quartz, call_index=0)
        assert text == char


def test_type_string_one_unicode_event_for_whole_string(mock_quartz):
    """The whole string is one event — no per-char dropouts."""
    with patch("typer.time.sleep") as mock_sleep:
        type_string("hunter2!")
    assert _event_count(mock_quartz) == 2  # one down + one up
    length, text = _unicode_args(mock_quartz, call_index=0)
    assert text == "hunter2!"
    # Two settle sleeps: 30ms before, 30ms after
    assert mock_sleep.call_count == 2


def test_type_string_empty(mock_quartz):
    type_string("")
    # No events posted for empty string
    assert _event_count(mock_quartz) == 0


def test_press_return_sends_two_events(mock_quartz):
    press_return()
    assert _event_count(mock_quartz) == 2
    codes = [c.args[1] for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list]
    assert codes == [K_RETURN, K_RETURN]


def test_lock_screen_sends_ctrl_cmd_q_atomically(mock_quartz):
    """The lock must use a single key event with Ctrl+Cmd flags attached,
    not six separate down/up events (which the WindowServer can drop)."""
    lock_screen()
    # Exactly two events: Q down, Q up
    assert _event_count(mock_quartz) == 2
    codes = [c.args[1] for c in mock_quartz.CGEventCreateKeyboardEvent.call_args_list]
    assert codes == [K_ANSI_Q, K_ANSI_Q]
    # Both events have the Ctrl+Cmd flags set
    for call in mock_quartz.CGEventSetFlags.call_args_list:
        flags = call.args[1]
        assert flags & mock_quartz.kCGEventFlagMaskControl
        assert flags & mock_quartz.kCGEventFlagMaskCommand


def test_lock_screen_uses_correct_tap(mock_quartz):
    lock_screen()
    for call in mock_quartz.CGEventPost.call_args_list:
        assert call.args[0] == mock_quartz.kCGHIDEventTap
