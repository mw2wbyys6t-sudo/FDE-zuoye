# -*- coding: utf-8 -*-
"""A2 冲突检测：纯规则实现，同一指标不同数值、完成口径、提示与阻断范围。"""

import re                                                    # 提取数值
from typing import Dict, List, Tuple                          # 类型标注
from app.agents.contracts import Conflict, ConflictOutput      # 输出契约
from app.domain.models import Fact                             # 事实模型

METRIC_PATTERNS: List[Tuple[str, str]] = [                    # 指标名 -> 提取正则
    ("错发率", r"错发率\s*(\d+(?:\.\d+)?)\s*%"),               # 百分比
    ("复核时长", r"平均\s*(\d+)\s*分钟"),                       # 平均分钟
    ("拣选作业量", r"每日\s*(\d+)\s*行"),                       # 每日行数
    ("复核工时", r"(\d+)\s*人时"),                              # 人时
    ("取消同步延迟", r"延迟\s*(\d+)\s*分钟"),                     # 延迟分钟
]


def _collect_values(facts: List[Fact]) -> Dict[str, Dict[str, List[str]]]:   # 汇总指标值
    """按指标收集数值与对应事实编号。

    入参：facts 事实列表。
    出参：{指标: {数值: [事实编号]}}。
    失败行为：不抛异常。
    """
    result: Dict[str, Dict[str, List[str]]] = {}               # 结果容器
    for fact in facts:                                         # 逐条事实
        for metric, pattern in METRIC_PATTERNS:                # 逐个指标
            for match in re.finditer(pattern, fact.statement):   # 一条事实可能有多个数值
                value = match.group(1)                           # 取数值
                slot = result.setdefault(metric, {}).setdefault(value, [])   # 初始化
                if fact.fact_id not in slot:                     # 去重
                    slot.append(fact.fact_id)                    # 记录来源
    return result                                              # 返回


def _value_conflicts(facts: List[Fact]) -> List[Conflict]:     # 数值冲突
    """检测同一指标出现多个不同数值的冲突。

    入参：facts 事实列表。
    出参：冲突列表。
    失败行为：不抛异常。
    """
    conflicts: List[Conflict] = []                             # 结果
    for metric, values in _collect_values(facts).items():       # 逐指标
        if len(values) < 2:                                     # 只有一个数值
            continue                                            # 无冲突
        refs: List[str] = []                                    # 涉及事实
        for ids in values.values():                             # 汇总编号
            refs.extend(ids)                                    # 追加
        conflicts.append(Conflict(kind="value", metric=metric,
                                  values=sorted(values.keys()),
                                  fact_refs=sorted(set(refs)),
                                  question="%s存在多个数值，以哪一条口径为准？" % metric))   # 生成冲突
    return conflicts                                           # 返回


def _definition_conflicts(facts: List[Fact]) -> List[Conflict]:   # 口径冲突
    """检测完成口径不一致。

    入参：facts 事实列表。
    出参：冲突列表。
    失败行为：不抛异常。
    """
    outbound = [f.fact_id for f in facts if "出库算完成" in f.statement]   # 仓内口径
    inbound = [f.fact_id for f in facts if "正确收货算完成" in f.statement]   # 站点口径
    if outbound and inbound:                                   # 两套口径同时存在
        return [Conflict(kind="definition", metric="完成口径",
                         values=["仓内出库", "站点正确收货"],
                         fact_refs=sorted(set(outbound + inbound)),
                         question="同一业务的完成时点以出库还是正确收货为准？")]   # 生成
    return []                                                  # 无冲突


def _scope_conflicts(facts: List[Fact]) -> List[Conflict]:      # 范围冲突
    """检测提示与阻断两种范围诉求并存。

    入参：facts 事实列表。
    出参：冲突列表。
    失败行为：不抛异常。
    """
    hint_only = [f.fact_id for f in facts if "不自动操作叉车" in f.statement]   # 只提示
    block = [f.fact_id for f in facts if "阻断" in f.statement]                   # 要求阻断
    if hint_only and block:                                    # 两者并存
        return [Conflict(kind="scope", metric="允许动作",
                         values=["仅提示", "阻断操作"],
                         fact_refs=sorted(set(hint_only + block)),
                         question="提示之外是否允许阻断，由谁批准？")]   # 生成
    return []                                                  # 无冲突


def detect(facts: List[Fact]) -> ConflictOutput:               # 入口
    """对事实集合执行全部冲突检测。

    入参：facts 事实列表。
    出参：ConflictOutput。
    失败行为：不抛异常；输入为空时返回空冲突。
    """
    conflicts = _value_conflicts(facts) + _definition_conflicts(facts) + _scope_conflicts(facts)   # 三类合并
    return ConflictOutput(conflicts=conflicts)                 # 返回
