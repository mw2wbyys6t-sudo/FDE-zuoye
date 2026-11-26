# -*- coding: utf-8 -*-
"""链路追踪：每次调用落 JSONL；写盘失败时降级但不阻断业务。"""

import json                                                 # 序列化
import os                                                   # 目录与错误
import uuid                                                 # 追踪号
from datetime import datetime, timezone                     # 时间
from typing import Any, Dict, Optional                      # 类型标注


class TraceWriter:                                          # 追踪写入器
    def __init__(self, trace_dir: str, store_raw: bool = True, max_raw_chars: int = 2000,
                 strict: bool = False):                     # 构造
        """初始化追踪目录与回放策略。

        入参：trace_dir 目录；store_raw 是否记录模型原文；max_raw_chars 原文截断长度；strict 写失败是否抛错。
        出参：无。
        失败行为：strict=True 且目录创建失败时抛异常；否则降级。
        """
        self.trace_dir = trace_dir                          # 保存目录
        self.store_raw = store_raw                          # 是否记录原文（回放必需）
        self.max_raw_chars = max_raw_chars                  # 截断长度
        self.strict = strict                                # 严格模式
        self.degraded = False                               # 是否已降级
        try:                                                # 创建目录
            os.makedirs(trace_dir, exist_ok=True)           # 已存在不报错
        except OSError:                                     # 磁盘或权限问题
            self.degraded = True                            # 标记降级
            if strict:                                      # 严格模式
                raise                                       # 向上抛

    def write(self, event: Dict[str, Any]) -> str:          # 写入事件
        """追加一条追踪事件并返回追踪号。

        入参：event 事件字典。
        出参：trace_id。
        失败行为：写盘失败时标记 degraded；strict=True 时抛异常。
        """
        trace_id = event.get("trace_id") or uuid.uuid4().hex[:12]   # 追踪号
        payload = dict(event)                               # 复制，避免改调用方对象
        payload["trace_id"] = trace_id                      # 回填
        payload["ts"] = datetime.now(timezone.utc).isoformat()   # 时间戳
        path = os.path.join(self.trace_dir, "%s.jsonl" % trace_id)   # 每 trace 一个文件
        try:                                                # 写盘
            with open(path, "a", encoding="utf-8") as fh:    # 追加
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")   # 单行 JSON
        except OSError:                                     # 磁盘异常
            # 原因：追踪是旁路能力，写失败不应阻断业务判定，但必须显式标记降级供验收发现
            self.degraded = True                            # 标记降级
            if self.strict:                                 # 严格模式
                raise                                       # 抛出
        return trace_id                                     # 返回追踪号

    def raw_of(self, raw: str) -> Optional[str]:            # 处理原文
        """按策略决定是否记录原文。

        入参：raw 模型原始输出。
        出参：需记录时返回截断文本，否则 None。
        失败行为：不抛异常。
        """
        if not self.store_raw:                              # 关闭记录
            return None                                     # 返回空
        return raw[: self.max_raw_chars]                    # 截断，避免单行过大
