# -*- coding: utf-8 -*-
"""模型客户端接口：agent 只能依赖这个接口，不得直接调用任何 SDK。"""

from typing import Protocol                                 # 结构化协议


class ModelClient(Protocol):                                # 所有模型实现必须满足的契约
    def complete(self, system: str, user: str) -> str:       # 单轮补全
        """执行一次补全并返回纯文本。

        入参：system 为系统提示词；user 为用户提示词。
        出参：模型返回的原始文本（可能是 JSON 字符串）。
        失败行为：网络或服务错误时抛异常，由 Runner 决定重试或降级。
        """
        ...                                                 # 协议声明，无实现
