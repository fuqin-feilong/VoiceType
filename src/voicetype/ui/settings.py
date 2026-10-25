"""设置窗口（深色卡片式布局）。"""
from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, paths
from ..audio import list_input_devices
from ..config import Config
from .icons import make_icon
from .theme import THEME_LABELS, apply_dark_title_bar, build_qss

KEY_LABELS = {
    "right_ctrl": "右 Ctrl",
    "right_alt": "右 Alt",
    "right_shift": "右 Shift",
    "left_ctrl": "左 Ctrl",
    "left_alt": "左 Alt",
    "f8": "F8",
    "f9": "F9",
    "mouse4": "鼠标侧键 4",
    "mouse5": "鼠标侧键 5",
    "caps_lock": "CapsLock",
    "space": "空格",
}

MODELS = [
    ("large-v3-turbo", "large-v3-turbo · 推荐"),
    ("medium", "medium · 更快"),
    ("small", "small · 轻量"),
    ("tiny", "tiny · 仅测试"),
]

CTRL_W = 232


class ChevronComboBox(QComboBox):
    """自带 chevron 箭头的下拉框：QSS 在深色主题下画不出箭头。"""

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#8B93A3"), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        w, h = 8.0, 4.0
        x = self.width() - 18.0
        y = self.height() / 2 - h / 2 + 1
        p.drawLine(QPointF(x, y), QPointF(x + w / 2, y + h))
        p.drawLine(QPointF(x + w / 2, y + h), QPointF(x + w, y))
        p.end()


def _combo(items: list[tuple[object, str]], current: object) -> QComboBox:
    c = ChevronComboBox()
    for value, label in items:
        c.addItem(label, value)
    c.setFixedWidth(CTRL_W)
    idx = c.findData(current)
    c.setCurrentIndex(idx if idx >= 0 else 0)
    return c


def _spin(minimum: int, maximum: int, value: int, suffix: str = "", step: int = 1) -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setValue(value)
    s.setSingleStep(step)
    if suffix:
        s.setSuffix(suffix)
    s.setFixedWidth(CTRL_W)
    s.setAlignment(Qt.AlignmentFlag.AlignRight)
    return s


def _dot_icon(fill: str, border: str) -> QIcon:
    pm = QPixmap(20, 20)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(border), 1.2))
    p.setBrush(QColor(fill))
    p.drawEllipse(QRectF(3, 3, 14, 14))
    p.end()
    return QIcon(pm)


class ThemePicker(QWidget):
    """深色 / 浅色 / 灰色 三选一。"""

    changed = Signal(str)

    def __init__(self, current: str = "dark"):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        swatches = {
            "dark": ("#1A1D24", "#3C4351"),
            "light": ("#FFFFFF", "#C2C9D4"),
            "gray": ("#35383F", "#555B66"),
        }
        for key in ("dark", "light", "gray"):
            btn = QPushButton(THEME_LABELS[key])
            btn.setObjectName("seg")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(_dot_icon(*swatches[key]))
            btn.setIconSize(QSize(12, 12))
            btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            h.addWidget(btn)
        self.set_current(current)

    def _pick(self, key: str) -> None:
        self.changed.emit(key)

    def set_current(self, key: str) -> None:
        btn = self._buttons.get(key) or self._buttons["dark"]
        btn.setChecked(True)

    def current(self) -> str:
        for k, b in self._buttons.items():
            if b.isChecked():
                return k
        return "dark"


class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 6, 16, 6)
        self._lay.setSpacing(0)
        self._first = True

    def _sep(self) -> None:
        if not self._first:
            line = QFrame()
            line.setObjectName("sep")
            line.setFixedHeight(1)
            self._lay.addWidget(line)
        self._first = False

    def add_row(self, label: str, widget: QWidget, hint: str = "") -> None:
        self._sep()
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 9, 0, 9)
        h.setSpacing(16)

        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(QLabel(label))
        if hint:
            lab = QLabel(hint)
            lab.setObjectName("hint")
            lab.setWordWrap(True)
            col.addWidget(lab)
        h.addLayout(col, 1)
        h.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lay.addWidget(row)

    def add_check(self, text: str, checkbox: QCheckBox, hint: str = "") -> None:
        self._sep()
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 9, 0, 9)
        v.setSpacing(2)
        checkbox.setText(text)
        v.addWidget(checkbox)
        if hint:
            lab = QLabel(hint)
            lab.setObjectName("hint")
            lab.setWordWrap(True)
            v.addWidget(lab)
            lab.setContentsMargins(25, 0, 0, 0)
        self._lay.addWidget(row)

    def add_block(self, widget: QWidget, hint: str = "") -> None:
        self._sep()
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 10, 0, 10)
        v.setSpacing(6)
        if hint:
            lab = QLabel(hint)
            lab.setObjectName("hint")
            lab.setWordWrap(True)
            v.addWidget(lab)
        v.addWidget(widget)
        self._lay.addWidget(wrap)


class Page(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setAutoFillBackground(False)
        self._v = QVBoxLayout(inner)
        self._v.setContentsMargins(30, 26, 30, 26)
        self._v.setSpacing(6)
        self.setWidget(inner)
        self._v.addStretch(1)
        self._sections = 0

    def section(self, title: str, desc: str = "") -> Card:
        if self._sections:
            self._v.insertSpacing(self._v.count() - 1, 14)
        self._sections += 1
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        self._v.insertWidget(self._v.count() - 1, t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("sectionDesc")
            d.setWordWrap(True)
            self._v.insertWidget(self._v.count() - 1, d)
        card = Card()
        self._v.insertWidget(self._v.count() - 1, card)
        self._v.insertSpacing(self._v.count() - 1, 4)
        return card

    def widget_row(self, widget: QWidget) -> None:
        self._v.insertWidget(self._v.count() - 1, widget)

    def stretch(self) -> None:
        self._v.insertSpacing(self._v.count() - 1, 12)


class SettingsDialog(QDialog):
    def __init__(
        self,
        cfg: Config,
        status: list[tuple[str, str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.cfg = cfg
        self._status = status or []
        self._theme = str(cfg.get("ui.theme", "dark"))
        if self._theme not in THEME_LABELS:
            self._theme = "dark"
        self._original_theme = self._theme
        self.setWindowTitle("VoiceType 设置")
        self.setWindowIcon(make_icon())
        self.resize(880, 650)
        self.setMinimumSize(820, 580)
        self.setStyleSheet(build_qss(self._theme))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), 1)

    # ---------------------------------------------------------------- 外框
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(200)
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 22, 16, 16)
        v.setSpacing(10)

        brand = QWidget()
        h = QHBoxLayout(brand)
        h.setContentsMargins(2, 0, 0, 0)
        h.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(make_icon().pixmap(30, 30))
        h.addWidget(icon)
        names = QVBoxLayout()
        names.setSpacing(0)
        name = QLabel("VoiceType")
        name.setObjectName("brand")
        sub = QLabel(f"v{__version__}")
        sub.setObjectName("brandSub")
        names.addWidget(name)
        names.addWidget(sub)
        h.addLayout(names)
        h.addStretch(1)
        v.addWidget(brand)
        v.addSpacing(10)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for text in ("通用", "识别", "输入", "词典", "关于"):
            self.nav.addItem(text)
        self.nav.setCurrentRow(0)
        v.addWidget(self.nav, 1)

        foot = QLabel("纯本地运行 · 不联网")
        foot.setObjectName("footer")
        foot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(foot)
        return side

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("content")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_general())
        self.stack.addWidget(self._page_asr())
        self.stack.addWidget(self._page_input())
        self.stack.addWidget(self._page_dict())
        self.stack.addWidget(self._page_about())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        v.addWidget(self.stack, 1)
        v.addWidget(self._footer())
        return content

    def _footer(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        line = QFrame()
        line.setObjectName("sep")
        line.setFixedHeight(1)
        v.addWidget(line)

        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 12, 24, 14)
        h.setSpacing(10)
        hint = QLabel("模型 / 设备修改后会自动重新加载")
        hint.setObjectName("footer")
        h.addWidget(hint)
        h.addStretch(1)

        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        h.addWidget(cancel)

        save = QPushButton("保存")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        h.addWidget(save)
        v.addWidget(bar)
        return wrap

    # ---------------------------------------------------------------- 通用
    def _page_general(self) -> Page:
        p = Page()

        c0 = p.section("外观", "切换后立即预览；点「保存」后托盘菜单也会同步。")
        self.theme_picker = ThemePicker(self._theme)
        self.theme_picker.changed.connect(self._apply_theme)
        c0.add_row("主题", self.theme_picker)

        c1 = p.section("提示与反馈", "说话时在光标旁显示浮层，浮层不会抢走焦点。")
        self.hud_cb = QCheckBox()
        self.hud_cb.setChecked(bool(self.cfg.get("ui.hud", True)))
        c1.add_check("显示屏幕浮层", self.hud_cb, "关掉后完全静默，只靠提示音判断状态")

        self.preview_cb = QCheckBox()
        self.preview_cb.setChecked(bool(self.cfg.get("ui.live_preview", True)))
        c1.add_check(
            "实时显示转写文字",
            self.preview_cb,
            "边说边显示识别到的文字，约每 0.8 秒刷新一次",
        )

        self.sound_cb = QCheckBox()
        self.sound_cb.setChecked(bool(self.cfg.get("ui.sounds", True)))
        c1.add_check("提示音", self.sound_cb, "开始 / 完成 / 失败三种短音")

        self.autostart_cb = QCheckBox()
        self.autostart_cb.setChecked(bool(self.cfg.get("ui.start_with_windows", False)))
        c1.add_check("开机自动启动", self.autostart_cb)

        c2 = p.section("热键", "按住说话，松开立即上屏。单独按 Alt 会让部分程序进入菜单模式，所以默认用 F8。")
        self.ptt_auto = _combo(
            [(k, v) for k, v in KEY_LABELS.items()],
            self.cfg.get("hotkeys.ptt_auto", "right_ctrl"),
        )
        c2.add_row("中英自动", self.ptt_auto)

        self.ptt_en = _combo(
            [(k, v) for k, v in KEY_LABELS.items()],
            self.cfg.get("hotkeys.ptt_en", "f8"),
        )
        c2.add_row("强制英文", self.ptt_en)

        self.ptt_extra = _combo(
            [("", "不启用")] + [(k, v) for k, v in KEY_LABELS.items()],
            self.cfg.get("hotkeys.ptt_extra", ""),
        )
        c2.add_row("额外快捷键", self.ptt_extra, "鼠标侧键在浏览器里是前进/后退，谨慎启用")

        self.min_hold = _spin(100, 2000, int(self.cfg.get("advanced.min_hold_ms", 250)), " ms", 50)
        c2.add_row("最短按住时长", self.min_hold, "低于这个时长当作误触丢弃")

        self.max_utt = _spin(5, 120, int(self.cfg.get("advanced.max_utterance_sec", 20)), " 秒")
        c2.add_row("单次最长录音", self.max_utt, "超时后自动切段提交，避免识别质量下降")
        return p

    # ---------------------------------------------------------------- 识别
    def _page_asr(self) -> Page:
        p = Page()

        c1 = p.section("模型", "large-v3-turbo 在中英混合和代码术语上表现最好，4GB 显存足够。")
        self.model = _combo(MODELS, self.cfg.get("asr.model", "large-v3-turbo"))
        c1.add_row("识别模型", self.model, "切换后若本地没有会自动下载")

        self.device = _combo(
            [("auto", "自动（GPU 优先）"), ("cuda", "CUDA"), ("cpu", "CPU")],
            self.cfg.get("asr.device", "auto"),
        )
        c1.add_row("推理设备", self.device, "没有可用 GPU 时自动降级到 CPU")

        self.language = _combo(
            [("auto", "自动检测"), ("zh", "中文"), ("en", "English")],
            self.cfg.get("asr.language", "auto"),
        )
        c1.add_row("默认语言", self.language, "只影响「中英自动」热键；英文热键始终锁定英文")

        self.beam = _spin(1, 10, int(self.cfg.get("asr.beam_size", 5)))
        c1.add_row("Beam size", self.beam, "5 质量优先；1 最快，适合低配机器")

        c2 = p.section("提示词与热词", "提示词会影响标点和用词风格；热词能显著提升专有名词准确率。")
        self.prompt = QLineEdit(self.cfg.get("asr.initial_prompt", "") or "")
        self.prompt.setPlaceholderText("留空则按语言自动使用内置标点提示词")
        self.prompt.setFixedWidth(CTRL_W)
        c2.add_row("初始提示词", self.prompt)

        self.hotwords = QLineEdit(self.cfg.get("asr.hotwords", "") or "")
        self.hotwords.setPlaceholderText("Tailscale, 飞书, 毛坯房")
        self.hotwords.setFixedWidth(CTRL_W)
        c2.add_row("热词", self.hotwords, "逗号分隔，最多几十个")

        c3 = p.section("麦克风", "常开音频流可以把按下到出声的延迟降到最低。")
        self.mic = ChevronComboBox()
        self.mic.setFixedWidth(CTRL_W)
        self.mic.addItem("系统默认", None)
        try:
            for idx, name in list_input_devices():
                self.mic.addItem(name, idx)
        except Exception:
            pass
        cur = self.cfg.get("audio.device", None)
        i = self.mic.findData(cur)
        self.mic.setCurrentIndex(i if i >= 0 else 0)
        c3.add_row("输入设备", self.mic, "改完立刻重新打开设备")
        return p

    # ---------------------------------------------------------------- 输入
    def _page_input(self) -> Page:
        p = Page()

        c1 = p.section("文字注入", "默认自动判断：终端类窗口逐字输入，其它应用用剪贴板粘贴。")
        self.method = _combo(
            [
                ("auto", "自动判断"),
                ("paste", "始终粘贴"),
                ("type", "始终逐字输入"),
            ],
            self.cfg.get("inject.method", "auto"),
        )
        c1.add_row("注入方式", self.method, "某些游戏/远程桌面只认逐字输入")

        self.restore_cb = QCheckBox()
        self.restore_cb.setChecked(bool(self.cfg.get("inject.restore_clipboard", True)))
        c1.add_check("粘贴后恢复原剪贴板", self.restore_cb, "文本、HTML、图片等常见格式都会还原")

        self.delay = _spin(
            100, 2000, int(self.cfg.get("inject.restore_delay_ms", 350)), " ms", 50
        )
        c1.add_row("剪贴板恢复延迟", self.delay, "目标程序卡顿时可以调大")

        c2 = p.section("文本处理", "针对「聊天 + 写代码」两类场景的默认规则。")
        self.code_cb = QCheckBox()
        self.code_cb.setChecked(bool(self.cfg.get("text.code_mode", False)))
        c2.add_check(
            "代码模式",
            self.code_cb,
            "半角标点、句末不加句号，并支持「下划线 / 小驼峰」等符号口令",
        )

        self.cn_punct_cb = QCheckBox()
        self.cn_punct_cb.setChecked(bool(self.cfg.get("text.chinese_punctuation", True)))
        c2.add_check("中文全角标点", self.cn_punct_cb)

        self.simplified_cb = QCheckBox()
        self.simplified_cb.setChecked(bool(self.cfg.get("text.simplified_chinese", True)))
        c2.add_check("繁体转简体", self.simplified_cb, "Whisper 偶尔会输出繁体")

        self.filler_cb = QCheckBox()
        self.filler_cb.setChecked(bool(self.cfg.get("text.remove_fillers", True)))
        c2.add_check("去掉口头语", self.filler_cb, "嗯、呃、um、uh…")

        self.trailing_cb = QCheckBox()
        self.trailing_cb.setChecked(bool(self.cfg.get("text.trailing_space", False)))
        c2.add_check("句末自动加空格", self.trailing_cb)
        return p

    # ---------------------------------------------------------------- 词典
    def _page_dict(self) -> Page:
        p = Page()
        c1 = p.section(
            "自定义词典",
            "每行一条，格式：识别结果=期望输出。英文按整词匹配，中文直接替换。",
        )

        self.dict_edit = QPlainTextEdit()
        self.dict_edit.setPlaceholderText(
            "例如：\n飞书=飞书\n威斯给特=VoiceType\nreact=React\nclaude=Claude"
        )
        self.dict_edit.setMinimumHeight(320)
        mapping = self.cfg.get("text.dictionary", {}) or {}
        self.dict_edit.setPlainText("\n".join(f"{k}={v}" for k, v in mapping.items()))
        c1.add_block(self.dict_edit)

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 0, 16, 10)
        h.setSpacing(8)
        tip = QLabel("提示：词典在识别完成后即时生效，无需重启")
        tip.setObjectName("hint")
        h.addWidget(tip)
        h.addStretch(1)

        example = QPushButton("插入示例")
        example.setObjectName("ghost")
        example.clicked.connect(self._insert_dict_example)
        h.addWidget(example)
        p.widget_row(row)
        return p

    def _insert_dict_example(self) -> None:
        demo = (
            "飞书=飞书\n"
            "威斯给特=VoiceType\n"
            "react=React\n"
            "vscode=VSCode\n"
            "接口=API\n"
            "克劳德=Claude"
        )
        current = self.dict_edit.toPlainText().strip()
        self.dict_edit.setPlainText(demo if not current else current + "\n" + demo)

    # ---------------------------------------------------------------- 关于
    def _page_about(self) -> Page:
        p = Page()
        c1 = p.section("运行状态", "纯本地推理，音频与文字都不会离开这台电脑。")
        rows = list(self._status)
        if not rows:
            rows = [("版本", __version__)]
        for label, value in rows:
            v = QLabel(value)
            v.setObjectName("value")
            v.setWordWrap(True)
            c1.add_row(label, v)

        c2 = p.section("文件位置", "配置与日志都在用户目录下，卸载时可以直接删除整个文件夹。")
        data_dir = str(paths.data_dir())
        path_box = QWidget()
        pv = QVBoxLayout(path_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(3)
        plabel = QLabel("数据目录")
        plabel.setObjectName("hint")
        pvalue = QLabel(data_dir)
        pvalue.setObjectName("value")
        pvalue.setWordWrap(True)
        pvalue.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pv.addWidget(plabel)
        pv.addWidget(pvalue)
        c2.add_block(path_box)

        buttons = QWidget()
        h = QHBoxLayout(buttons)
        h.setContentsMargins(0, 8, 0, 4)
        h.setSpacing(8)
        open_data = QPushButton("打开配置目录")
        open_data.clicked.connect(lambda: os.startfile(data_dir))  # noqa: S606
        h.addWidget(open_data)
        open_logs = QPushButton("打开日志")
        open_logs.clicked.connect(lambda: os.startfile(str(paths.logs_dir())))  # noqa: S606
        h.addWidget(open_logs)
        h.addStretch(1)
        c2.add_block(buttons)
        return p

    # ---------------------------------------------------------------- 生命周期
    def _apply_theme(self, name: str) -> None:
        if name not in THEME_LABELS:
            return
        self._theme = name
        self.setStyleSheet(build_qss(name))
        apply_dark_title_bar(self, name != "light")

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(self, self._theme != "light")
        if not getattr(self, "_centered", False):
            self._centered = True
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(
                    geo.center().x() - self.width() // 2,
                    geo.center().y() - self.height() // 2,
                )

    def reject(self) -> None:
        # 取消时把临时预览的主题还原
        if self._theme != self._original_theme:
            self._theme = self._original_theme
            self.setStyleSheet(build_qss(self._theme))
            apply_dark_title_bar(self, self._theme != "light")
        super().reject()

    # ---------------------------------------------------------------- 保存
    def accept(self) -> None:
        cfg = self.cfg

        cfg.set("ui.hud", self.hud_cb.isChecked(), save=False)
        cfg.set("ui.theme", self._theme, save=False)
        cfg.set("ui.live_preview", self.preview_cb.isChecked(), save=False)
        cfg.set("ui.sounds", self.sound_cb.isChecked(), save=False)
        cfg.set("ui.start_with_windows", self.autostart_cb.isChecked(), save=False)
        cfg.set("hotkeys.ptt_auto", self.ptt_auto.currentData(), save=False)
        cfg.set("hotkeys.ptt_en", self.ptt_en.currentData(), save=False)
        cfg.set("hotkeys.ptt_extra", self.ptt_extra.currentData(), save=False)
        cfg.set("advanced.min_hold_ms", self.min_hold.value(), save=False)
        cfg.set("advanced.max_utterance_sec", self.max_utt.value(), save=False)

        cfg.set("asr.model", self.model.currentData(), save=False)
        cfg.set("asr.device", self.device.currentData(), save=False)
        cfg.set("asr.language", self.language.currentData(), save=False)
        cfg.set("asr.beam_size", self.beam.value(), save=False)
        cfg.set("asr.initial_prompt", self.prompt.text().strip(), save=False)
        cfg.set("asr.hotwords", self.hotwords.text().strip(), save=False)
        cfg.set("audio.device", self.mic.currentData(), save=False)

        cfg.set("inject.method", self.method.currentData(), save=False)
        cfg.set("inject.restore_clipboard", self.restore_cb.isChecked(), save=False)
        cfg.set("inject.restore_delay_ms", self.delay.value(), save=False)
        cfg.set("text.code_mode", self.code_cb.isChecked(), save=False)
        cfg.set("text.chinese_punctuation", self.cn_punct_cb.isChecked(), save=False)
        cfg.set("text.simplified_chinese", self.simplified_cb.isChecked(), save=False)
        cfg.set("text.remove_fillers", self.filler_cb.isChecked(), save=False)
        cfg.set("text.trailing_space", self.trailing_cb.isChecked(), save=False)

        mapping: dict[str, str] = {}
        for line in self.dict_edit.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                mapping[k] = v
        cfg.set("text.dictionary", mapping, save=False)
        cfg.save()
        super().accept()
