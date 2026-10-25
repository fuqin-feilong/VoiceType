# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）。

用法（在项目根目录）：
    .venv\\Scripts\\pyinstaller.exe --noconfirm --clean packaging\\voicetype.spec
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).resolve().parent
SP = ROOT / ".venv" / "Lib" / "site-packages"

datas = []
binaries = []

# ---- 运行时数据 ----
datas += collect_data_files("opencc")          # 繁简词典
datas += collect_data_files("faster_whisper")  # VAD / 内置资源
datas += collect_data_files(
    "_sounddevice_data", includes=["portaudio-binaries/*.dll"]
)

# ---- 原生库 ----
binaries += collect_dynamic_libs("ctranslate2")
binaries += collect_dynamic_libs("onnxruntime")
binaries += collect_dynamic_libs("av")

# ---- 裁剪后的 CUDA（只保留推理必需的 11 个 DLL） ----
CUDA_FILES = [
    ("cublas/bin", "cublas64_12.dll"),
    ("cublas/bin", "cublasLt64_12.dll"),
    ("cudnn/bin", "cudnn64_9.dll"),
    ("cudnn/bin", "cudnn_ops64_9.dll"),
    ("cudnn/bin", "cudnn_cnn64_9.dll"),
    ("cudnn/bin", "cudnn_graph64_9.dll"),
    ("cudnn/bin", "cudnn_heuristic64_9.dll"),
    ("cudnn/bin", "cudnn_engines_precompiled64_9.dll"),
    ("cudnn/bin", "cudnn_engines_runtime_compiled64_9.dll"),
    ("cudnn/bin", "cudnn_engines_tensor_ir64_9.dll"),
    ("cudnn/bin", "cudnn_ext64_9.dll"),
]
for sub, name in CUDA_FILES:
    src = SP / "nvidia" / sub / name
    if not src.exists():
        raise SystemExit(f"缺少 CUDA 文件: {src}")
    binaries.append((str(src), "cuda"))

hiddenimports = [
    "comtypes.gen.UIAutomationClient",
    "voicetype",
]

excludes = [
    # 用不到的 Qt 模块
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtWebSockets",
    "PySide6.QtWebChannel",
    # 无关的重型依赖
    "tkinter",
    "nvidia",
    "torch",
    "transformers",
    "scipy",
    "pandas",
    "matplotlib",
    "IPython",
    "pytest",
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceType",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "src" / "voicetype" / "assets" / "voicetype.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VoiceType",
)
