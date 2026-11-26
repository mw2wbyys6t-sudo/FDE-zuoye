# -*- coding: utf-8 -*-
"""Fake 模型：P0 阶段用于打通契约、闸门与追踪，不依赖任何本地推理服务。"""

from typing import List                                     # 列表类型


class FakeClient:                                           # 可编排的假模型
    def __init__(self, script: List[str]):                   # 初始化脚本序列
        """构造假模型。

        入参：script 为按调用顺序返回的文本列表，用完后重复最后一条。
        出参：无。
        失败行为：script 为空时构造失败，避免测试中出现无声的空返回。
        """
        if not script:                                       # 必须至少有一条
            raise ValueError("script 不能为空")               # 空脚本直接报错
        self.script = list(script)                           # 复制一份，避免外部修改
        self.calls = 0                                       # 记录调用次数，便于断言

    def complete(self, system: str, user: str) -> str:        # 返回预置文本
        """按顺序返回预置文本。

        入参：system 与 user 仅为接口对齐，Fake 不解析内容。
        出参：脚本中的下一条文本。
        失败行为：不抛异常；脚本用尽后重复最后一条，模拟"模型反复给同一错误答案"。
        """
        index = min(self.calls, len(self.script) - 1)        # 越界则复用最后一条
        self.calls += 1                                      # 计数加一
        return self.script[index]                            # 返回对应文本
