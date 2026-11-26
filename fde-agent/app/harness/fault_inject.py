# -*- coding: utf-8 -*-
"""故障注入：让模型超时、报错或返回垃圾，用于演练降级路径。"""

import time                                                  # 模拟阻塞
from typing import Any, Optional                             # 类型标注


class FaultMode:                                            # 故障模式常量
    RAISE = "raise"                                          # 直接抛异常
    GARBAGE = "garbage"                                       # 返回非法文本
    TIMEOUT = "timeout"                                       # 先睡再抛超时


class FaultyClient:                                         # 故障客户端
    def __init__(self, inner: Any, fail_times: int = 1, mode: str = FaultMode.RAISE,
                 delay_s: float = 0.01):                     # 构造
        """包装真实客户端并注入前 N 次故障。

        入参：inner 真实客户端；fail_times 故障次数；mode 故障模式；delay_s 超时模拟秒数。
        出参：无。
        失败行为：mode 非法时抛 ValueError。
        """
        if mode not in (FaultMode.RAISE, FaultMode.GARBAGE, FaultMode.TIMEOUT):   # 模式校验
            raise ValueError("未知故障模式：%s" % mode)        # 抛出
        self.inner = inner                                   # 保存真实客户端
        self.remaining = max(0, int(fail_times))             # 剩余故障次数
        self.mode = mode                                     # 模式
        self.delay_s = delay_s                               # 延迟

    def complete(self, system: str, user: str) -> str:       # 调用
        """前 N 次按模式制造故障，之后透传。

        入参：system 与 user 透传给真实客户端。
        出参：模型文本。
        失败行为：故障次数内抛 RuntimeError 或返回垃圾文本。
        """
        if self.remaining > 0:                               # 仍在故障窗口
            self.remaining -= 1                              # 消耗一次
            if self.mode == FaultMode.RAISE:                 # 抛异常
                raise RuntimeError("注入故障：模型不可用")     # 抛出
            if self.mode == FaultMode.TIMEOUT:               # 模拟超时
                time.sleep(self.delay_s)                     # 短暂阻塞
                raise TimeoutError("注入故障：调用超时")       # 抛出
            return "这不是 JSON，只是一段解释文字。"            # 垃圾输出
        return self.inner.complete(system, user)             # 正常透传
