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


def _send_key(keycode: int, down: bool) -> None:
    event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _send_unicode(text: str) -> None:
    """Type a string using the Unicode string API — layout-independent.

    Sends the actual Unicode characters to the keyboard event tap, so the
    OS's keyboard layout maps them to the right keycodes. Works for any
    character the active layout can produce (including accented letters,
    symbols, etc.) and doesn't suffer from the dropped-character problem
    that hits per-keystroke posting on the macOS lock screen.
    """
    if not text:
        return
    n = len(text.encode("utf-16-le")) // 2
    event = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
    Quartz.CGEventKeyboardSetUnicodeString(event, n, text)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    event_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
    Quartz.CGEventKeyboardSetUnicodeString(event_up, n, text)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)


def type_char(char: str) -> None:
    """Type a single character using the Unicode string API."""
    _send_unicode(char)


def type_string(text: str) -> None:
    """Type a string using Quartz Unicode keyboard events.

    The whole string goes in one event (no per-char dropouts). Minimal
    settle delays before/after for the lock screen to register input.
    """
    time.sleep(0.03)
    _send_unicode(text)
    time.sleep(0.03)


def press_return() -> None:
    """Press the Return key."""
    _send_key(K_RETURN, True)
    _send_key(K_RETURN, False)


def lock_screen() -> None:
    """Lock the Mac by sending Ctrl+Cmd+Q (the standard lock shortcut)."""
    _send_key(K_CONTROL, True)
    _send_key(K_COMMAND, True)
    _send_key(K_ANSI_Q, True)
    _send_key(K_ANSI_Q, False)
    _send_key(K_COMMAND, False)
    _send_key(K_CONTROL, False)
