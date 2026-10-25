"""ASR 引擎抽象：便于以后接流式引擎或云端引擎。"""
from __future__ import annotations

from typing import Protocol

import numpy as np


class AsrEngine(Protocol):
    name: str

    def load(self) -> None: ...

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,
        hotwords: str | None = None,
    ) -> str: ...
