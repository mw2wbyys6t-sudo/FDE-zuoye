# -*- coding: utf-8 -*-
"""回放：按追踪文件里的模型原文重放，验证结构一致。"""

import json                                                 # 解析追踪
from pathlib import Path                                    # 路径
from typing import Any, Dict, List                           # 类型标注


class ReplayError(Exception):                               # 回放异常
    def __init__(self, msg: str):                            # 初始化
        """构造回放异常。

        入参：msg 说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                # 基类保存


class ReplayClient:                                        # 回放用模型客户端
    def __init__(self, trace_path: str):                     # 构造
        """读取追踪文件并抽取可回放的模型原文。

        入参：trace_path JSONL 路径。
        出参：无。
        失败行为：文件不存在或缺原文时抛 ReplayError。
        """
        path = Path(trace_path)                              # 路径对象
        if not path.exists():                                # 文件缺失
            raise ReplayError("追踪文件不存在：%s" % trace_path)   # 抛出
        events: List[Dict[str, Any]] = []                    # 事件列表
        for line in path.read_text(encoding="utf-8").splitlines():   # 逐行
            if not line.strip():                             # 空行
                continue                                     # 跳过
            events.append(json.loads(line))                  # 解析
        self.raws = [e["raw"] for e in events
                     if e.get("status") == "model_returned" and e.get("raw")]   # 只取带原文的调用
        if not self.raws:                                    # 没有可回放内容
            raise ReplayError("追踪中未记录模型原文，无法回放（检查 trace.store_raw）")   # 抛出
        self.calls = 0                                       # 调用计数

    def complete(self, system: str, user: str) -> str:       # 回放
        """按顺序返回记录的原文。

        入参：system 与 user 仅为接口对齐。
        出参：下一条原文。
        失败行为：回放内容用尽时抛 ReplayError。
        """
        if self.calls >= len(self.raws):                     # 用尽
            raise ReplayError("回放内容不足，追踪与实际调用次数不一致")   # 抛出
        value = self.raws[self.calls]                        # 取原文
        self.calls += 1                                      # 计数
        return value                                         # 返回
