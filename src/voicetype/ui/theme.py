"""主题系统：深色 / 浅色 / 灰色，可运行时切换。"""
from __future__ import annotations

import ctypes

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#13151A",
        "sidebar": "#171A20",
        "card": "#1A1D24",
        "border": "#262B36",
        "sep": "#232833",
        "text": "#E6E9EF",
        "muted": "#7C8598",
        "value": "#B9C1D0",
        "input": "#22262F",
        "input_border": "#2E3340",
        "input_hover": "#3C4351",
        "hover": "#1E222B",
        "accent": "#4F8CFF",
        "accent_hover": "#659CFF",
        "accent_text": "#FFFFFF",
        "nav_bg": "#202B40",
        "nav_text": "#7FB0FF",
        "scroll": "#343A47",
        "scroll_hover": "#414958",
        "indicator_border": "#3C4351",
        "indicator_bg": "#1A1D24",
        "disabled": "#6B7385",
        "selection": "#4F8CFF",
        "danger": "#E05B5B",
    },
    "light": {
        "bg": "#F3F5F8",
        "sidebar": "#EAEDF2",
        "card": "#FFFFFF",
        "border": "#E1E5EC",
        "sep": "#EDF0F5",
        "text": "#1E2430",
        "muted": "#6B7484",
        "value": "#3A4353",
        "input": "#FFFFFF",
        "input_border": "#D5DAE3",
        "input_hover": "#B6BFCC",
        "hover": "#E4E8EF",
        "accent": "#2F6FED",
        "accent_hover": "#4A85F5",
        "accent_text": "#FFFFFF",
        "nav_bg": "#DCE8FF",
        "nav_text": "#2456C4",
        "scroll": "#C6CDD8",
        "scroll_hover": "#AEB7C5",
        "indicator_border": "#C2C9D4",
        "indicator_bg": "#FFFFFF",
        "disabled": "#9AA3B2",
        "selection": "#2F6FED",
        "danger": "#D64545",
    },
    "gray": {
        "bg": "#2A2D33",
        "sidebar": "#303338",
        "card": "#35383F",
        "border": "#42464E",
        "sep": "#3A3E45",
        "text": "#E7E9ED",
        "muted": "#9AA1AC",
        "value": "#C9CED8",
        "input": "#3C4048",
        "input_border": "#4A4F58",
        "input_hover": "#5C626D",
        "hover": "#3A3E45",
        "accent": "#7FA6FF",
        "accent_hover": "#9AB9FF",
        "accent_text": "#10131A",
        "nav_bg": "#454B57",
        "nav_text": "#D6E2FF",
        "scroll": "#555B66",
        "scroll_hover": "#666D79",
        "indicator_border": "#555B66",
        "indicator_bg": "#35383F",
        "disabled": "#7C838F",
        "selection": "#7FA6FF",
        "danger": "#F07A7A",
    },
}

THEME_LABELS = {
    "dark": "深色",
    "light": "浅色",
    "gray": "灰色",
}

_QSS = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
    color: %(text)s;
}
QDialog { background-color: %(bg)s; }
QWidget#sidebar { background-color: %(sidebar)s; border-right: 1px solid %(border)s; }
QWidget#content { background-color: %(bg)s; }

QLabel#brand { font-size: 16px; font-weight: 600; }
QLabel#brandSub { color: %(muted)s; font-size: 11px; }
QLabel#sectionTitle { font-size: 14px; font-weight: 600; }
QLabel#sectionDesc { color: %(muted)s; font-size: 12px; }
QLabel#hint { color: %(muted)s; font-size: 11px; }
QLabel#footer { color: %(muted)s; font-size: 11px; }
QLabel#value { color: %(value)s; }

QFrame#card {
    background-color: %(card)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
}
QFrame#sep { background-color: %(sep)s; max-height: 1px; border: none; }

QListWidget#nav { background: transparent; border: none; outline: none; }
QListWidget#nav::item {
    height: 38px;
    border-radius: 8px;
    padding-left: 12px;
    color: %(muted)s;
}
QListWidget#nav::item:hover { background-color: %(hover)s; color: %(text)s; }
QListWidget#nav::item:selected { background-color: %(nav_bg)s; color: %(nav_text)s; }

QComboBox, QSpinBox, QLineEdit {
    background-color: %(input)s;
    border: 1px solid %(input_border)s;
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 20px;
    selection-background-color: %(selection)s;
    placeholder-text-color: %(muted)s;
}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover { border-color: %(input_hover)s; }
QComboBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: %(accent)s; }
QComboBox::drop-down { border: none; width: 26px; background: transparent; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox QAbstractItemView {
    background-color: %(card)s;
    border: 1px solid %(input_border)s;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: %(nav_bg)s;
}
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }

QPlainTextEdit {
    background-color: %(input)s;
    border: 1px solid %(input_border)s;
    border-radius: 10px;
    padding: 10px;
    font-family: Consolas, "Microsoft YaHei UI";
    selection-background-color: %(selection)s;
    placeholder-text-color: %(muted)s;
}
QPlainTextEdit:focus { border-color: %(accent)s; }

QCheckBox { spacing: 9px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 8px;
    border: 1px solid %(indicator_border)s;
    background-color: %(indicator_bg)s;
}
QCheckBox::indicator:hover { border-color: %(input_hover)s; }
QCheckBox::indicator:checked { background-color: %(accent)s; border: 1px solid %(accent)s; }

QPushButton {
    background-color: %(input)s;
    border: 1px solid %(input_border)s;
    border-radius: 8px;
    padding: 7px 18px;
    color: %(text)s;
}
QPushButton:hover { background-color: %(hover)s; }
QPushButton:pressed { background-color: %(sep)s; }
QPushButton#primary {
    background-color: %(accent)s;
    border: 1px solid %(accent)s;
    color: %(accent_text)s;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: %(accent_hover)s; border-color: %(accent_hover)s; }
QPushButton#ghost { background: transparent; border: none; color: %(muted)s; }
QPushButton#ghost:hover { color: %(text)s; }

QPushButton#seg {
    background-color: %(input)s;
    border: 1px solid %(input_border)s;
    border-radius: 8px;
    padding: 6px 12px;
    color: %(muted)s;
}
QPushButton#seg:hover { border-color: %(input_hover)s; }
QPushButton#seg:checked {
    background-color: %(nav_bg)s;
    border: 1px solid %(accent)s;
    color: %(text)s;
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: %(scroll)s; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: %(scroll_hover)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QToolTip {
    background-color: %(card)s;
    color: %(text)s;
    border: 1px solid %(input_border)s;
    padding: 5px 8px;
}
"""

_MENU_QSS = """
QMenu {
    background-color: %(card)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 30px 7px 12px;
    border-radius: 6px;
    color: %(text)s;
}
QMenu::item:selected { background-color: %(nav_bg)s; }
QMenu::item:disabled { color: %(disabled)s; }
QMenu::separator { height: 1px; background: %(sep)s; margin: 5px 8px; }
QMenu::indicator {
    width: 14px; height: 14px; border-radius: 7px;
    border: 1px solid %(indicator_border)s; background: transparent;
    margin-left: 6px;
}
QMenu::indicator:checked { background: %(accent)s; border: 1px solid %(accent)s; }
"""


def palette(name: str | None = None) -> dict[str, str]:
    return THEMES.get(name or "dark", THEMES["dark"])


# HUD 浮层配色：浅色主题需要接近不透明的浅底，否则压在浅色应用上会糊
HUD_THEMES: dict[str, dict] = {
    "dark": {
        "bg": (19, 21, 27, 242),
        "border": (255, 255, 255, 24),
        "text": "#E8EAF0",
        "preview": "#DCE2EE",
        "preview_done": "#AEB6C6",
        "muted": "#9AA3B2",
        "states": {
            "listening": "#4F8CFF",
            "working": "#F0A030",
            "done": "#35C07A",
            "error": "#E05B5B",
            "loading": "#8A8F98",
            "idle": "#8A8F98",
        },
    },
    "light": {
        "bg": (250, 251, 253, 248),
        "border": (0, 0, 0, 38),
        "text": "#1B2230",
        "preview": "#2C3546",
        "preview_done": "#6B7484",
        "muted": "#6B7484",
        "states": {
            "listening": "#2F6FED",
            "working": "#C97A05",
            "done": "#1B9C63",
            "error": "#D64545",
            "loading": "#6B7484",
            "idle": "#6B7484",
        },
    },
    "gray": {
        "bg": (46, 49, 55, 245),
        "border": (255, 255, 255, 22),
        "text": "#E9EBEF",
        "preview": "#D6DBE3",
        "preview_done": "#A0A6B0",
        "muted": "#9AA1AC",
        "states": {
            "listening": "#7FA6FF",
            "working": "#F0A030",
            "done": "#3FD08A",
            "error": "#F07A7A",
            "loading": "#9AA1AC",
            "idle": "#9AA1AC",
        },
    },
}


def hud_palette(name: str | None = None) -> dict:
    return HUD_THEMES.get(name or "dark", HUD_THEMES["dark"])


def build_qss(name: str | None = None) -> str:
    return _QSS % palette(name)


def build_menu_qss(name: str | None = None) -> str:
    return _MENU_QSS % palette(name)


def apply_dark_title_bar(widget, dark: bool = True) -> None:
    """Win10 1809+ 标题栏明暗。"""
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.WinDLL("dwmapi")
        value = ctypes.c_int(1 if dark else 0)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
