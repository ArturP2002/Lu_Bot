"""Флаг: reply-меню уже отправлено в текущем handler."""

from contextvars import ContextVar

_menu_kb_attached: ContextVar[bool] = ContextVar("_menu_kb_attached", default=False)


def mark_menu_kb_attached() -> None:
    """Handler уже отправил ReplyKeyboardMarkup — не дублировать pin."""
    _menu_kb_attached.set(True)


def consume_menu_kb_attached() -> bool:
    if _menu_kb_attached.get():
        _menu_kb_attached.set(False)
        return True
    return False
