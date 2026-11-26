# -*- coding: utf-8 -*-
"""执行器：所有模型调用、契约校验、闸门与追踪的唯一入口。"""

import json                                                 # 解析模型输出
import uuid                                                 # 生成追踪号
from dataclasses import dataclass, field                     # 运行规格
from typing import Any, Callable, Dict, List, Optional, Type  # 类型标注
from pydantic import BaseModel, ValidationError               # schema 校验
from app import errors as E                                   # 错误码（harness 不依赖 api 层）
from app.harness.guards import GuardError                     # 闸门异常
from app.harness.trace import TraceWriter                     # 追踪写入器


class RunnerError(Exception):                                 # 执行器异常
    def __init__(self, code: str, msg: str, trace_id: str = ""):   # 初始化
        """构造执行器异常。

        入参：code 错误码；msg 中文说明；trace_id 追踪号。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                 # 交给基类
        self.code = code                                      # 保存错误码
        self.msg = msg                                        # 保存说明
        self.trace_id = trace_id                              # 保存追踪号，便于定位


@dataclass
class RunSpec:                                                # 一次执行所需的全部信息
    step: str                                                 # 步骤名，如 a1_evidence
    prompt_version: str                                       # 提示词版本，回放时必须可定位
    schema: Type[BaseModel]                                   # 输出契约
    system: str                                               # 系统提示词
    user: str                                                 # 用户提示词
    guards: List[Callable[[Any], None]] = field(default_factory=list)   # 需依次通过的闸门
    fallback: Optional[Callable[[], Dict[str, Any]]] = None    # 重试耗尽后的降级结果（必须标记降级）


def _strip_fences(text: str) -> str:                          # 去掉模型常见的代码围栏
    """剥离 ```json 围栏，提取纯 JSON 文本。

    入参：text 模型原始输出。
    出参：去围栏后的字符串。
    失败行为：无围栏时原样返回，不抛异常。
    """
    cleaned = text.strip()                                    # 去掉首尾空白
    if cleaned.startswith("```"):                             # 命中围栏
        lines = cleaned.splitlines()                          # 按行切分
        lines = [ln for ln in lines if not ln.strip().startswith("```")]   # 去掉围栏行
        cleaned = "\n".join(lines)                            # 重新拼回
    return cleaned.strip()                                    # 返回结果


class Runner:                                                 # 统一执行器
    def __init__(self, client: Any, trace: TraceWriter, max_retry: int = 2):   # 构造
        """初始化执行器。

        入参：client 满足 ModelClient 协议；trace 追踪写入器；max_retry 最大重试次数。
        出参：无。
        失败行为：参数缺失时抛 ValueError。
        """
        if client is None or trace is None:                   # 必要依赖校验
            raise ValueError("client 与 trace 不能为空")       # 直接失败
        self.client = client                                  # 保存模型客户端
        self.trace = trace                                    # 保存追踪器
        self.max_retry = max(0, int(max_retry))               # 重试次数不允许为负

    def run(self, spec: RunSpec) -> Dict[str, Any]:            # 执行一次完整步骤
        """执行模型调用 → 解析 → 契约校验 → 闸门 → 返回结果。

        入参：spec 为 RunSpec。
        出参：{"data": 校验后的字典, "trace_id": str, "attempts": int, "degraded": bool}。
        失败行为：重试耗尽且无降级时抛 RunnerError(E_SCHEMA)；闸门不通过时抛 GuardError。
        """
        trace_id = uuid.uuid4().hex[:12]                       # 本次运行追踪号
        last_error = ""                                        # 记录最后一次失败原因
        returned = 0                                           # 成功返回文本的次数
        for attempt in range(self.max_retry + 1):              # 含首次尝试
            prompt = spec.user                                # 首次提问
            if attempt > 0:                                    # 重试时追加修复提示
                prompt = prompt + "\n\n上一次输出不合法：%s。请只返回符合 schema 的 JSON。" % last_error   # 修复提示
            try:                                               # 调用模型，故障也要走重试与降级
                raw = self.client.complete(spec.system, prompt)   # 调用模型
            except Exception as exc:                           # 网络、超时或注入故障
                last_error = str(exc)[:200]                     # 记录原因
                self.trace.write({"trace_id": trace_id, "step": spec.step, "attempt": attempt,
                                  "status": "model_error", "error": last_error})   # 记录故障
                continue                                        # 进入下一次重试或降级
            returned += 1                                       # 记录一次成功返回
            self.trace.write({"trace_id": trace_id, "step": spec.step, "attempt": attempt,
                              "prompt_version": spec.prompt_version, "status": "model_returned",
                              "raw_len": len(raw), "raw": self.trace.raw_of(raw)})   # 记录原文以支持回放
            try:                                               # 解析与校验
                payload = json.loads(_strip_fences(raw))       # 解析 JSON
                obj = spec.schema.model_validate(payload)      # 契约校验
            except (json.JSONDecodeError, ValidationError) as exc:   # 解析或结构失败
                last_error = str(exc)[:200]                    # 截断保留，避免追踪膨胀
                self.trace.write({"trace_id": trace_id, "step": spec.step, "attempt": attempt,
                                  "status": "invalid", "error": last_error})   # 记录失败
                continue                                       # 进入下一次重试
            try:                                               # 闸门校验
                for guard in spec.guards:                      # 依次执行
                    guard(obj)                                 # 任一失败即抛 GuardError
            except GuardError as exc:                          # 闸门拦截
                self.trace.write({"trace_id": trace_id, "step": spec.step, "attempt": attempt,
                                  "status": "guard_blocked", "code": exc.code})   # 记录拦截
                raise                                          # 上抛，由接口层转三键结构
            self.trace.write({"trace_id": trace_id, "step": spec.step, "attempt": attempt,
                              "status": "ok", "prompt_version": spec.prompt_version,
                              "data": obj.model_dump()})             # 记录校验后的结构，供回放比对
            return {"data": obj.model_dump(), "trace_id": trace_id,
                    "attempts": attempt + 1, "degraded": False,
                    "trace_degraded": self.trace.degraded}     # 返回结果并带追踪降级标记
        if spec.fallback is not None:                          # 有降级方案
            self.trace.write({"trace_id": trace_id, "step": spec.step,
                              "status": "degraded", "error": last_error})   # 记录降级
            return {"data": spec.fallback(), "trace_id": trace_id,
                    "attempts": self.max_retry + 1, "degraded": True}   # 返回降级结果
        self.trace.write({"trace_id": trace_id, "step": spec.step,
                          "status": "failed", "error": last_error})   # 记录最终失败
        # 原因：全部尝试都在客户端层失败（未拿到任何文本）属于依赖不可用，与"模型输出不合法"要区分
        code = E.E_MODEL_UNAVAILABLE if returned == 0 else E.E_SCHEMA   # 区分错误类型
        raise RunnerError(code, "模型调用失败或输出始终不符合约定结构" if returned == 0
                          else "模型输出始终不符合约定结构", trace_id)   # 抛出统一异常
