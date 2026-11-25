from __future__ import annotations


def calculate_window_geometry(screen_width: int, screen_height: int) -> str:
    """Return a centered window size that leaves room for Windows chrome and taskbar."""
    width = min(1120, max(820, int(screen_width) - 80))
    height = min(760, max(560, int(screen_height) - 140))
    left = max(0, (int(screen_width) - width) // 2)
    top = max(0, (int(screen_height) - height) // 2)
    return f"{width}x{height}+{left}+{top}"
