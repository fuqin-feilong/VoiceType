"""Win32 底层封装：键盘状态、焦点窗口、光标位置、文本注入（SendInput）。

只依赖 ctypes，不引入额外钩子，避免杀软误报。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8
ULONG_PTR = ctypes.c_ulonglong if IS_64 else ctypes.c_ulong

# ---------------------------------------------------------------- 常量
VK = {
    "left_ctrl": 0xA2,
    "right_ctrl": 0xA3,
    "left_alt": 0xA4,
    "right_alt": 0xA5,
    "left_shift": 0xA0,
    "right_shift": 0xA1,
    "right_shift": 0xA1,
    "caps_lock": 0x14,
    "space": 0x20,
    "escape": 0x1B,
    "backspace": 0x08,
    "enter": 0x0D,
    "tab": 0x09,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "mouse4": 0x05,   # XBUTTON1
    "mouse5": 0x06,   # XBUTTON2
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
}

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


# ---------------------------------------------------------------- SendInput 结构
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wt.LONG),
        ("top", wt.LONG),
        ("right", wt.LONG),
        ("bottom", wt.LONG),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("flags", wt.DWORD),
        ("hwndActive", wt.HWND),
        ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND),
        ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND),
        ("hwndCaret", wt.HWND),
        ("rcCaret", RECT),
    ]


# ---------------------------------------------------------------- 键盘状态
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def wait_release(vk: int, timeout: float = 0.5) -> None:
    """等按键松开，避免修饰键卡在按下状态污染注入。"""
    deadline = time.time() + timeout
    while is_key_down(vk) and time.time() < deadline:
        time.sleep(0.005)


# ---------------------------------------------------------------- 窗口信息
user32.GetForegroundWindow.restype = wt.HWND
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetGUIThreadInfo.argtypes = [wt.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wt.BOOL
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(POINT)]
user32.ClientToScreen.restype = wt.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wt.BOOL

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE,
    wt.DWORD,
    wt.LPWSTR,
    ctypes.POINTER(wt.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL


def foreground_window() -> int:
    return int(user32.GetForegroundWindow() or 0)


def window_class(hwnd: int) -> str:
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    n = user32.GetClassNameW(hwnd, buf, 256)
    return buf.value if n else ""


def window_process_name(hwnd: int) -> str:
    """返回小写 exe 名，如 wechat.exe。"""
    if not hwnd:
        return ""
    pid = wt.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def caret_screen_rect() -> tuple[int, int, int, int] | None:
    """取当前输入光标的屏幕坐标 (left, top, right, bottom)。取不到返回 None。"""
    hwnd = foreground_window()
    if not hwnd:
        return None
    pid = wt.DWORD(0)
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not tid:
        return None
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return None
    if not info.hwndCaret:
        return None
    pt = POINT(info.rcCaret.left, info.rcCaret.bottom)
    if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(pt)):
        return None
    return (pt.x, pt.y, pt.x, pt.y)


def cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.IsZoomed.argtypes = [wt.HWND]
user32.IsZoomed.restype = wt.BOOL


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """窗口屏幕坐标 (left, top, right, bottom)。"""
    if not hwnd:
        return None
    r = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    if r.right <= r.left or r.bottom <= r.top:
        return None
    return (r.left, r.top, r.right, r.bottom)


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(hwnd))


def set_foreground(hwnd: int) -> bool:
    """把窗口切到前台（可能被系统限制，返回值仅供参考）。"""
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return int(user32.GetForegroundWindow() or 0) == hwnd


# ---------------------------------------------------------------- 注入
def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return inp


def _send(inputs: list[INPUT]) -> int:
    if not inputs:
        return 0
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    return user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def _char_inputs(ch: str) -> list[INPUT]:
    """把一个字符编码成 UTF-16 code unit 序列（正确处理代理对/emoji）。"""
    out: list[INPUT] = []
    raw = ch.encode("utf-16-le")
    for i in range(0, len(raw), 2):
        scan = int.from_bytes(raw[i : i + 2], "little")
        out.append(_key_input(scan=scan, flags=KEYEVENTF_UNICODE))
        out.append(_key_input(scan=scan, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    return out


def type_text(text: str, interval: float = 0.0) -> None:
    """逐字注入 Unicode 文本（不经过剪贴板）。"""
    if not text:
        return
    # 分批，避免单次 SendInput 事件数过多
    batch: list[INPUT] = []
    for ch in text:
        batch.extend(_char_inputs(ch))
        if len(batch) >= 200:
            _send(batch)
            batch = []
            if interval:
                time.sleep(interval)
    if batch:
        _send(batch)


def tap_key(vk: int, mods: tuple[int, ...] = ()) -> None:
    inputs: list[INPUT] = [_key_input(vk=m) for m in mods]
    inputs.append(_key_input(vk=vk))
    inputs.append(_key_input(vk=vk, flags=KEYEVENTF_KEYUP))
    for m in reversed(mods):
        inputs.append(_key_input(vk=m, flags=KEYEVENTF_KEYUP))
    _send(inputs)


def send_ctrl_v() -> None:
    tap_key(ord("V"), (VK["ctrl"],))


def send_backspaces(count: int) -> None:
    if count <= 0:
        return
    inputs: list[INPUT] = []
    for _ in range(count):
        inputs.append(_key_input(vk=VK["backspace"]))
        inputs.append(_key_input(vk=VK["backspace"], flags=KEYEVENTF_KEYUP))
    _send(inputs)
