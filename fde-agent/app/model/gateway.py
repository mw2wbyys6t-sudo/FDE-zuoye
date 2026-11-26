# -*- coding: utf-8 -*-
"""OpenAI 兼容模型网关：本地 Ollama / vLLM 共用同一份调用代码。"""

import json                                                 # 解析响应体
import urllib.error                                         # 捕获 HTTP 错误
import urllib.request                                       # 发起 HTTPS 请求
from typing import Any, Dict                                # 类型标注


class OpenAICompatibleClient:                               # 兼容 /v1/chat/completions 的客户端
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.0, seed: int = 42, timeout_s: int = 30):   # 构造
        """初始化客户端。

        入参：base_url 服务地址；api_key 令牌；model 模型名；temperature 温度；seed 随机种子；timeout_s 超时秒数。
        出参：无。
        失败行为：base_url 或 model 为空时抛 ValueError，避免发出无意义的请求。
        """
        if not base_url or not model:                        # 必要参数校验
            raise ValueError("base_url 与 model 不能为空，请检查环境变量")   # 直接失败
        self.base_url = base_url.rstrip("/")                 # 去掉结尾斜杠
        self.api_key = api_key                               # 保存令牌（仅内存）
        self.model = model                                   # 保存模型名
        self.temperature = temperature                       # 保存温度
        self.seed = seed                                     # 保存种子
        self.timeout_s = timeout_s                           # 保存超时

    def complete(self, system: str, user: str) -> str:       # 单轮补全
        """调用 chat/completions 并返回首条消息内容。

        入参：system 系统提示词；user 用户提示词。
        出参：模型回复文本。
        失败行为：HTTP 非 2xx 或响应结构异常时抛 RuntimeError，交由 Runner 重试或降级。
        """
        body: Dict[str, Any] = {                             # 组装请求体
            "model": self.model,                             # 模型名
            "temperature": self.temperature,                 # 判定任务固定 0
            "seed": self.seed,                               # 固定种子
            "messages": [                                    # 消息列表
                {"role": "system", "content": system},       # 系统提示
                {"role": "user", "content": user},           # 用户提示
            ],
        }
        data = json.dumps(body).encode("utf-8")              # 序列化
        req = urllib.request.Request(self.base_url + "/chat/completions", data=data, method="POST")   # 构造请求
        req.add_header("Content-Type", "application/json")    # 请求类型
        if self.api_key:                                     # 本地服务通常不需要令牌
            req.add_header("Authorization", "Bearer " + self.api_key)   # 有令牌才加
        try:                                                 # 网络调用
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:   # 发起请求
                payload = json.loads(resp.read().decode("utf-8"))   # 解析响应
        except urllib.error.HTTPError as exc:                # HTTP 错误
            raise RuntimeError("模型返回 %s" % exc.code)      # 统一转为运行时错误
        try:                                                 # 结构解析
            return payload["choices"][0]["message"]["content"]   # 取首条内容
        except (KeyError, IndexError) as exc:                # 结构不符
            raise RuntimeError("模型响应结构异常")            # 统一报错
