# -*- coding: utf-8 -*-
"""A1 证据抽取：把访谈文本抽成带事实编号的结论，未命中证据即拒答。"""

from typing import Any, Dict, List, Optional                  # 类型标注
from app.harness.runner import RunSpec, Runner                # 执行器
from app.harness.schema import EvidenceOutput                 # 输出契约
from app.harness.guards import check_evidence                 # 证据闸门

PROMPT_VERSION = "a1-evidence-v1"                             # 提示词版本，回放必须可定位
SYSTEM_PROMPT = ("你是证据抽取器。只输出 JSON："
                 "{\"claims\":[{\"text\":\"...\",\"fact_id\":\"fXX\"}]}。"
                 "每条结论必须来自给定事实台账，无法对应时必须返回空数组，禁止编造编号。")   # 系统提示


def build_spec(text: str, known_ids: List[str]) -> RunSpec:    # 构造执行规格
    """按输入文本构造 A1 的 RunSpec。

    入参：text 访谈文本；known_ids 已知事实编号。
    出参：RunSpec。
    失败行为：不抛异常。
    """
    user = ("已知事实编号：%s\n请从下列文本中抽取结论，逐条给出事实编号：\n%s"
            % (", ".join(known_ids), text))                    # 把台账编号放进提示，减少编造
    return RunSpec(step="a1_evidence", prompt_version=PROMPT_VERSION, schema=EvidenceOutput,
                   system=SYSTEM_PROMPT, user=user,
                   guards=[lambda obj: check_evidence([c.model_dump() for c in obj.claims],
                                                      known_ids=set(known_ids))])   # 输出即过闸门


def extract(runner: Runner, text: str, known_ids: List[str],
            fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:   # 执行抽取
    """执行一次证据抽取。

    入参：runner 执行器；text 文本；known_ids 已知编号；fallback 可选降级结果。
    出参：{"claims":[...], "trace_id", "attempts", "degraded"}。
    失败行为：模型始终不合法时抛 RunnerError；闸门拦截时抛 GuardError。
    """
    spec = build_spec(text, known_ids)                          # 构造规格
    spec.fallback = fallback                                    # 可选降级
    return runner.run(spec)                                     # 交给执行器
