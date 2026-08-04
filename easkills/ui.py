"""Terminal presentation: ANSI styling with honest degradation.

Colour is display, never data. Every helper here returns plain text when the
output is not an interactive terminal (pipes, CI logs, pytest capture), when the
user sets ``NO_COLOR``, or when the console cannot render a symbol -- so scripted
consumers, tests and log files see exactly the bytes they always did, and the
exit-code contracts stay the interface. ``FORCE_COLOR`` overrides detection for
terminals that lie about themselves.
"""

from __future__ import annotations

import os
import sys

RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"


def enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def _wrap(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if enabled() else text


def bold(text: str) -> str:
    return _wrap(_BOLD, text)


def dim(text: str) -> str:
    return _wrap(_DIM, text)


def red(text: str) -> str:
    return _wrap(_RED, text)


def green(text: str) -> str:
    return _wrap(_GREEN, text)


def yellow(text: str) -> str:
    return _wrap(_YELLOW, text)


def cyan(text: str) -> str:
    return _wrap(_CYAN, text)


def magenta(text: str) -> str:
    return _wrap(_MAGENTA, text)


def sym(preferred: str, fallback: str) -> str:
    """The preferred symbol when the console can encode it, else the fallback."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        preferred.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return fallback
    return preferred


def check() -> str:
    return sym("✓", "OK")


def cross() -> str:
    return sym("✗", "X")


def arrow() -> str:
    return sym("→", "->")


def bullet() -> str:
    return sym("●", "*")


def warning_sign() -> str:
    return sym("⚠", "!")


def severity(label: str) -> str:
    """Colour a severity word, preserving the field width it was padded to."""
    key = label.strip().upper()
    if key == "ERROR":
        return red(bold(label))
    if key == "WARNING":
        return yellow(label)
    if key == "INFO":
        return cyan(label)
    return label


def status(label: str) -> str:
    """Colour a checklist status word (PASS/FAIL/GAP), width-preserving."""
    key = label.strip().upper()
    if key == "PASS":
        return green(label)
    if key == "FAIL":
        return red(bold(label))
    if key == "GAP":
        return magenta(label)
    return label


def verdict(ok: bool, errors: int, warnings: int) -> str:
    """The standard closing line of every gate."""
    error_part = red(f"{errors} error(s)") if errors else dim("0 error(s)")
    warning_part = yellow(f"{warnings} warning(s)") if warnings else dim("0 warning(s)")
    if ok:
        return f"{error_part}, {warning_part} {dim('--')} {green(bold(f'{check()} PASS'))}"
    return f"{error_part}, {warning_part} {dim('--')} {red(bold(f'{cross()} FAIL'))}"


def header(title: str, subtitle: str = "") -> list[str]:
    lines = [f"{bullet()} {bold(title)}" if enabled() else title]
    if subtitle:
        lines.append(f"  {dim(subtitle)}" if enabled() else subtitle)
    return lines


def enable_windows_vt() -> None:
    """Switch the Windows console into VT mode so ANSI sequences render.

    Best-effort: on failure (old console, redirected handle) styling degrades to
    plain text via ``enabled()`` anyway.
    """
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:  # noqa: BLE001 - cosmetic capability probe, never fatal
        pass
