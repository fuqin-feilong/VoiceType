"""词典：内置技术术语大小写修正 + 用户自定义替换。"""
from __future__ import annotations

import re

# 常见技术专有名词（不区分大小写匹配，替换为规范写法）
TECH_TERMS: dict[str, str] = {
    "github": "GitHub",
    "gitlab": "GitLab",
    "vscode": "VSCode",
    "vs code": "VSCode",
    "visual studio code": "Visual Studio Code",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "numpy": "NumPy",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "openai": "OpenAI",
    "chatgpt": "ChatGPT",
    "llm": "LLM",
    "api": "API",
    "sdk": "SDK",
    "json": "JSON",
    "yaml": "YAML",
    "html": "HTML",
    "css": "CSS",
    "http": "HTTP",
    "https": "HTTPS",
    "url": "URL",
    "sql": "SQL",
    "linux": "Linux",
    "macos": "macOS",
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
    "python": "Python",
    "react": "React",
    "vue": "Vue",
    "npm": "npm",
    "pnpm": "pnpm",
    "devops": "DevOps",
}

_ASCII_TOKEN = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z][A-Za-z0-9_.+# ]*?)(?![A-Za-z0-9_.])")


def _build_regex(keys: list[str]) -> re.Pattern | None:
    if not keys:
        return None
    # 长词优先，避免 "vs code" 被 "code" 抢先
    keys = sorted(keys, key=len, reverse=True)
    alts = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"(?<![A-Za-z0-9_])(?:{alts})(?![A-Za-z0-9_])", re.I)


_TECH_RE = _build_regex(list(TECH_TERMS))
_TECH_LOOKUP = {k.lower(): v for k, v in TECH_TERMS.items()}


def apply_tech_terms(text: str) -> str:
    if not _TECH_RE:
        return text

    def repl(m: re.Match) -> str:
        return _TECH_LOOKUP.get(m.group(0).lower(), m.group(0))

    return _TECH_RE.sub(repl, text)


def apply_custom(text: str, mapping: dict[str, str]) -> str:
    """用户词典：ASCII 词按词边界，中文按直接替换。"""
    if not mapping:
        return text
    for src, dst in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
        if not src:
            continue
        if src.isascii():
            text = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])",
                dst,
                text,
                flags=re.I,
            )
        else:
            text = text.replace(src, dst)
    return text
