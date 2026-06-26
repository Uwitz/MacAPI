import time

import Quartz


K_ANSI_A = 0x00
K_ANSI_B = 0x0B
K_ANSI_C = 0x08
K_ANSI_D = 0x02
K_ANSI_E = 0x0E
K_ANSI_F = 0x03
K_ANSI_G = 0x05
K_ANSI_H = 0x04
K_ANSI_I = 0x22
K_ANSI_J = 0x26
K_ANSI_K = 0x28
K_ANSI_L = 0x25
K_ANSI_M = 0x2E
K_ANSI_N = 0x2D
K_ANSI_O = 0x1F
K_ANSI_P = 0x23
K_ANSI_Q = 0x0C
K_ANSI_R = 0x0F
K_ANSI_S = 0x01
K_ANSI_T = 0x11
K_ANSI_U = 0x20
K_ANSI_V = 0x09
K_ANSI_W = 0x0D
K_ANSI_X = 0x07
K_ANSI_Y = 0x10
K_ANSI_Z = 0x06

K_ANSI_1 = 0x12
K_ANSI_2 = 0x13
K_ANSI_3 = 0x14
K_ANSI_4 = 0x15
K_ANSI_5 = 0x16
K_ANSI_6 = 0x17
K_ANSI_7 = 0x18
K_ANSI_8 = 0x19
K_ANSI_9 = 0x1A
K_ANSI_0 = 0x1B

K_ANSI_MINUS = 0x1B
K_ANSI_EQUAL = 0x18
K_ANSI_LEFT_BRACKET = 0x21
K_ANSI_RIGHT_BRACKET = 0x1E
K_ANSI_BACKSLASH = 0x2A
K_ANSI_SEMICOLON = 0x29
K_ANSI_QUOTE = 0x27
K_ANSI_COMMA = 0x2B
K_ANSI_PERIOD = 0x2F
K_ANSI_SLASH = 0x2C
K_ANSI_GRAVE = 0x32

K_RETURN = 0x24
K_TAB = 0x30
K_SPACE = 0x31
K_DELETE = 0x33
K_ESCAPE = 0x35
K_COMMAND = 0x37
K_SHIFT = 0x38
K_CAPS_LOCK = 0x39
K_OPTION = 0x3A
K_CONTROL = 0x3B


UNSHIFTED_KEYCODES = {
    "a": K_ANSI_A, "b": K_ANSI_B, "c": K_ANSI_C, "d": K_ANSI_D, "e": K_ANSI_E,
    "f": K_ANSI_F, "g": K_ANSI_G, "h": K_ANSI_H, "i": K_ANSI_I, "j": K_ANSI_J,
    "k": K_ANSI_K, "l": K_ANSI_L, "m": K_ANSI_M, "n": K_ANSI_N, "o": K_ANSI_O,
    "p": K_ANSI_P, "q": K_ANSI_Q, "r": K_ANSI_R, "s": K_ANSI_S, "t": K_ANSI_T,
    "u": K_ANSI_U, "v": K_ANSI_V, "w": K_ANSI_W, "x": K_ANSI_X, "y": K_ANSI_Y,
    "z": K_ANSI_Z,
    "1": K_ANSI_1, "2": K_ANSI_2, "3": K_ANSI_3, "4": K_ANSI_4, "5": K_ANSI_5,
    "6": K_ANSI_6, "7": K_ANSI_7, "8": K_ANSI_8, "9": K_ANSI_9, "0": K_ANSI_0,
    " ": K_SPACE, "-": K_ANSI_MINUS, "=": K_ANSI_EQUAL,
    "[": K_ANSI_LEFT_BRACKET, "]": K_ANSI_RIGHT_BRACKET,
    "\\": K_ANSI_BACKSLASH, ";": K_ANSI_SEMICOLON, "'": K_ANSI_QUOTE,
    ",": K_ANSI_COMMA, ".": K_ANSI_PERIOD, "/": K_ANSI_SLASH, "`": K_ANSI_GRAVE,
    "\t": K_TAB,
}

SHIFTED_CHARS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=",
    "{": "[", "}": "]", "|": "\\",
    ":": ";", "\"": "'",
    "<": ",", ">": ".", "?": "/", "~": "`",
}


def _send_key(keycode: int, down: bool, pid: int | None = None) -> None:
    event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    if event is None:
        return
    if pid is not None:
        # PyObjC's signature is (pid, event) — reversed from the C header.
        Quartz.CGEventPostToPid(pid, event)
    else:
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, event)


def _post_unicode(text: str, down: bool, pid: int | None = None) -> None:
    """Post a single Unicode-string keyboard event (down or up)."""
    if not text:
        return
    n = len(text.encode("utf-16-le")) // 2
    event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
    if event is None:
        return
    Quartz.CGEventKeyboardSetUnicodeString(event, n, text)
    if pid is not None:
        # PyObjC's signature is (pid, event) — reversed from the C header.
        Quartz.CGEventPostToPid(pid, event)
    else:
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, event)


def _send_unicode(text: str, pid: int | None = None) -> None:
    if not text:
        return
    _post_unicode(text, True, pid)
    time.sleep(0.02)
    _post_unicode(text, False, pid)


def _secure_input_pid() -> int | None:
    """Return the PID of the process that currently has secure input
    (typically loginwindow when the lock screen is showing the password
    field), or None if no process has secure input.

    We post events directly to this PID because events going through the
    normal event tap are silently dropped by processes with secure input
    — which is exactly the case for the lock screen's password field.
    """
    session = Quartz.CGSessionCopyCurrentDictionary() or {}
    return session.get("kCGSSessionSecureInputPID")


def type_char(char: str) -> None:
    """Type a single character, routed around secure input if active."""
    _send_unicode(char, pid=_secure_input_pid())


def _press_key(keycode: int) -> None:
    """Press and release a key (used for non-character keys like Return,
    F-keys, etc.). Routed around secure input if active."""
    pid = _secure_input_pid()
    _send_key(keycode, True, pid=pid)
    time.sleep(0.02)
    _send_key(keycode, False, pid=pid)


def type_string(text: str) -> None:
    """Type a string into the current focus (typically the macOS lock screen).

    Posts directly to the process with secure input (the loginwindow
    when the screen is locked), bypassing the normal event tap that
    would otherwise be blocked.

    Sequence:
    1. 200ms settle
    2. Press F15 (no-op key, but wakes the screen if in "press a key
       to wake" state)
    3. 1 second wait for the password field to become active
    4. Type each character with 50ms between them, routed around
       secure input
    5. 150ms settle
    """
    import sys
    print(f"[typer] type_string starting ({len(text)} chars)", file=sys.stderr, flush=True)
    time.sleep(0.2)

    print("[typer] sending F15 to wake lock screen", file=sys.stderr, flush=True)
    _press_key(0x40)
    time.sleep(1.0)

    pid = _secure_input_pid()
    print(f"[typer] secure input pid (pre-type): {pid}", file=sys.stderr, flush=True)

    print("[typer] typing password chars", file=sys.stderr, flush=True)
    last_pid = pid
    for i, char in enumerate(text):
        # Re-resolve every char — the secure-input PID can change
        # (typically from loginwindow → the field's own owner) after
        # the first keypress activates the password field.
        pid = _secure_input_pid()
        if pid != last_pid:
            print(f"[typer]   secure input pid changed: {last_pid} -> {pid}", file=sys.stderr, flush=True)
            last_pid = pid
        _send_unicode(char, pid=pid)
        if i % 4 == 0:
            print(f"[typer]   posted char {i+1}/{len(text)}: {char!r} -> pid {pid}", file=sys.stderr, flush=True)
        time.sleep(0.05)
    time.sleep(0.15)
    print("[typer] type_string done", file=sys.stderr, flush=True)


def press_return() -> None:
    """Press the Return key, routed around secure input if active."""
    _press_key(K_RETURN)


def lock_screen() -> None:
    """Lock the Mac by sending Ctrl+Cmd+Q (the standard lock shortcut).

    Attaches the Control + Command modifier flags directly to the Q key
    event via CGEventSetFlags, rather than posting six separate down/up
    events. This is dramatically more reliable because the OS can't drop
    any of the events — the key + its modifiers are a single atomic
    event from the WindowServer's perspective.
    """
    import sys
    print("[lock] sending Ctrl+Cmd+Q (atomic modifier+key event)", file=sys.stderr, flush=True)
    flags = (
        Quartz.kCGEventFlagMaskControl
        | Quartz.kCGEventFlagMaskCommand
    )
    event_down = Quartz.CGEventCreateKeyboardEvent(None, K_ANSI_Q, True)
    Quartz.CGEventSetFlags(event_down, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
    time.sleep(0.05)
    event_up = Quartz.CGEventCreateKeyboardEvent(None, K_ANSI_Q, False)
    Quartz.CGEventSetFlags(event_up, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)
