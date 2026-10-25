# VoiceType · Windows 语音输入助手

按住一个键说话，松手文字直接出现在光标处。**纯本地识别（faster-whisper large-v3-turbo）**，中英混合，不联网、不上传。

## 快速开始

```bat
run.bat
```

启动后右下角出现麦克风图标，**按住 `右 Ctrl` 说话，松手即输入**。

| 操作 | 说明 |
|---|---|
| 按住 `右 Ctrl` | 中英自动识别（先检测语言，再选对应标点提示词） |
| 按住 `F8` | 强制英文（写代码、英文邮件用这个，最快） |
| 录音中按 `Esc` | 取消本次输入 |
| 托盘双击 | 打开设置 |
| 托盘 → 代码模式 | 半角标点、句末不加句号、支持符号口令 |
| 托盘 → 撤销上次输入 | 回删刚输入的文字（需焦点窗口未变） |

> 为什么英文键不用「右 Alt」：单独按一下 Alt 会让很多程序进入菜单栏模式，随后的 Ctrl+V 就粘不进文档了。
> 鼠标侧键同理——在浏览器/IDE 里它是「后退」，会翻页。两个键都可在设置里改，但要清楚副作用。

## 特性

- **只说中英**：语言判定只在中文/英文里二选一，日韩俄等语言不会再冒出来
- **边说边看**：按住说话时，光标旁浮层实时显示已识别到的文字，确认有没有录进去
- **纯本地**：模型跑在本机 RTX 4060（int8_float16），首次加载约 6 秒，之后每句识别 0.3~0.7 秒
- **中英混合**：`这个 API 的 response 需要加一个 timeout 参数。`
- **自动标点**：先做语言检测，中文用中文提示词、英文用英文提示词，能稳定输出标点
- **简体化**：Whisper 偶尔输出繁体，自动用 OpenCC 转简体
- **不抢焦点**：HUD 浮层 `WS_EX_NOACTIVATE`，文字只会进你的目标窗口
- **居中不乱动**：浮层水平居中；位置在每次说话开始时锁定一次，过程中不会跟着光标抖动
- **不污染剪贴板**：粘贴后自动恢复原剪贴板（文本/HTML/图片等格式）
- **按应用选注入方式**：终端类窗口自动改用逐字 SendInput，其余用剪贴板粘贴
- **语音命令**：整句说「换行 / 逗号 / 句号 / 撤销」会变成动作
- **可定制**：自定义词典、热词、初始提示词、麦克风、热键、注入方式
- **深色设置界面**：侧边导航 + 卡片式分组，状态、词典、热键一屏可改
- **三套主题**：深色 / 浅色 / 灰色，设置里点一下即时预览，保存后托盘菜单同步切换

## 主题

「设置 → 通用 → 外观」里可以在 **深色 / 浅色 / 灰色** 之间切换：

- 点一下立即预览当前设置窗口，不用重启
- 点「保存」后写入配置，托盘右键菜单同步换色
- 点「取消」会还原成打开设置前的主题

主题作用于设置窗口、托盘菜单和屏幕浮层：浅色主题下浮层会变成近不透明的白色卡片，
在浅色应用里也能看清；深色/灰色主题下浮层保持半透明深色。

## 实时预览是怎么做的

Whisper 不是流式模型，所以预览采用「整段滚动重解码」：

1. 录音时每 800ms 取一次当前**完整**音频（上限 50 秒）
2. 用 `beam_size=5` + 语言提示词（代码模式下换成编程术语提示词）转写
3. 语言只在 **中文 / 英文** 里二选一，其它语言不会出现
4. 结果带一个「代数」编号，松手时代数 +1，所有在途的旧结果都会被丢弃
5. 松手后的正式识别用 `beam_size=5` + VAD，保证最终质量
6. 静音（RMS 过低）不触发；短外文幻觉（Thank you / ご視聴 等）会被过滤
7. 预览文本不允许突然大幅变短，避免某次解码丢开头把显示带偏

因为每次都解码整段，长句不会丢前半段；代价是 25 秒的话单次预览约 1 秒、
50 秒约 1.6 秒，显示会比说话慢 1~2 秒——用速度换准确率。
如果更在意速度，可以在「设置 → 通用」里关掉实时预览。

## 目录

```
src/voicetype/
  app.py              主控状态机
  hotkey.py           GetAsyncKeyState 轮询（无键盘钩子）
  audio.py            WASAPI 采集，流常开
  asr/whisper_engine.py
  text/pipeline.py    标点/口头语/词典/繁简
  inject/             剪贴板粘贴 + SendInput 兜底
  ui/                 HUD / 托盘 / 设置
models/               模型（按 <模型名>/ 分目录）
```

配置和日志：`%LOCALAPPDATA%\VoiceType\`（`config.json`、`logs\voicetype.log`）

## 安装（换机 / 重建环境）

```powershell
# 1. Python 3.11（已装可跳过）
#    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

# 2. 创建虚拟环境
python -m venv .venv

# 3. 装依赖（国内建议用清华源）
.\.venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 以可编辑模式安装本项目
.\.venv\Scripts\python -m pip install -e . --no-deps

# 5. 下载模型（约 1.6GB）
#    直接启动程序即可：会自动按 ModelScope（国内快）→ HF 官方 → hf-mirror 的顺序下载，
#    文件落在 models\large-v3-turbo\ 下。
#    也可以手动从 ModelScope 拉：
#    https://modelscope.cn/api/v1/models/pengzhendong/faster-whisper-large-v3-turbo/repo?Revision=master&FilePath=model.bin
#    （config.json / tokenizer.json / vocabulary.json / preprocessor_config.json 一并放到同目录）
```

> GPU 需要 CUDA 12 运行库，由 `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` 两个 pip 包提供，
> 程序启动时自动把它们的目录注册进 DLL 搜索路径（见 `cuda_setup.py`）。
> 没有 NVIDIA 显卡时会自动降级到 CPU（int8，速度慢 2~3 倍但可用）。

## 测试

```powershell
# 生成中英测试音频（Windows SAPI）
.\.venv\Scripts\python tests\make_samples.py

# 识别验证
.\.venv\Scripts\python tests\probe_asr.py --model large-v3-turbo --out tests\last_probe.txt

# 注入验证（会弹一个窗口并自动打字）
.\.venv\Scripts\python tests\probe_inject.py
```

## 打包（安装包 / 免安装版）

产物在 `dist/`：

| 文件 | 说明 |
|---|---|
| `VoiceType-0.4.0-setup.exe` | 安装版，装到 `%LOCALAPPDATA%\Programs\VoiceType`，不需要管理员权限 |
| `VoiceType-0.4.0-portable.zip` | 免安装版，解压后双击 `VoiceType.exe` |
| `VoiceType/` | 免安装目录（已带 `portable.txt`） |

- 支持 **Windows 10/11 64 位**
- 安装包约 818MB；免安装 zip 约 1.18GB（解压后约 1.9GB，其中 1.6GB 是裁剪后的 CUDA 运行库）
- **不含模型**：首次启动会自动从 ModelScope 下载 `large-v3-turbo`（约 1.6GB），
  也可以手动把 `models` 文件夹放进免安装目录，或用 `VOICETYPE_MODELS_DIR` 指定
- 免安装版：配置/日志在 `<目录>\data`；模型优先用 `<目录>\models`，
  没有就复用 `%LOCALAPPDATA%\VoiceType\models`
- 自带 CUDA 运行库（11 个 DLL），NVIDIA 显卡开箱即用；没有 N 卡自动降级 CPU
- 安装向导是英文（Inno Setup 未随附简体中文语言包），应用本身是中文

重新打包：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

依赖：Python 3.11 venv + `pyinstaller` + Inno Setup 6（默认装在 `C:\Program Files (x86)\Inno Setup 6`）。

## 已知限制

- **管理员窗口**：Win10 UIPI 限制，普通权限的 VoiceType 无法向「以管理员运行」的程序输入。需要的话以管理员身份启动本程序。
- **反作弊游戏 / 部分全屏独占程序**：注入会被拦截。
- **首次按键**：模型加载完成前按下会提示「模型还在加载」。
- **焦点切换**：撤销上次输入要求焦点仍在原窗口，否则会拒绝执行（防止误删）。
- **剪贴板**：备份不含「文件拖放（CF_HDROP）」等少数格式，这些格式在粘贴后会丢失。
