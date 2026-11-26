# -*- coding: utf-8 -*-
"""A3 口径基线：把事实整理成指标表，缺什么就写 TBD，不猜。"""

import re                                                    # 提取数值
from typing import List, Optional                             # 类型标注
from app.agents.contracts import BaselineOutput, BaselineRow   # 输出契约
from app.domain.models import Confidence, Fact                  # 事实模型

DEFAULT_OWNER = "TBD"                                         # 责任人缺省
EXTRACTORS = [                                                # 指标 -> (正则, 默认分子, 默认分母, 来源)
    ("错发率", r"错发率\s*(\d+(?:\.\d+)?)\s*%", "错发业务单数", "应出库或应正确收货业务单数", "WMS 出库 + 站点收货"),
    ("装车复核时长", r"平均\s*(\d+)\s*分钟", "单次实际耗时（含等待与处理）", "不适用（均值）", "扫码时间戳 + 现场观察"),
    ("拣选作业量", r"每日\s*(\d+)\s*行", "工作量基数", "不适用", "WMS 拣选流水"),
    ("人工重复复核工时", r"(\d+)\s*人时", "重复复核发生的人时", "不适用", "复核岗位工时记录"),
    ("取消同步延迟", r"延迟\s*(\d+)\s*分钟", "OMS 取消时刻到装车侧可见的间隔", "期间全部取消事件", "OMS 与终端事件日志"),
]


def _find_value(facts: List[Fact], pattern: str) -> Optional[str]:   # 找现状值
    """在事实中寻找匹配的数值。

    入参：facts 事实列表；pattern 正则。
    出参：首个匹配数值或 None。
    失败行为：不抛异常。
    """
    for fact in facts:                                        # 逐条
        match = re.search(pattern, fact.statement)            # 匹配
        if match:                                             # 命中
            return match.group(1)                             # 返回数值
    return None                                               # 未命中


def _evidence(facts: List[Fact], pattern: str) -> List[str]:   # 取证据编号
    """返回匹配该指标的事实编号。

    入参：facts 事实列表；pattern 正则。
    出参：编号列表。
    失败行为：不抛异常。
    """
    return [fact.fact_id for fact in facts if re.search(pattern, fact.statement)]   # 过滤


def build(facts: List[Fact]) -> BaselineOutput:                # 入口
    """把事实整理成指标基线表。

    入参：facts 事实列表。
    出参：BaselineOutput。
    失败行为：不抛异常；缺数据写 TBD 并计入缺口。
    """
    rows: List[BaselineRow] = []                               # 结果
    for indicator, pattern, molecule, denominator, source in EXTRACTORS:   # 逐指标
        value = _find_value(facts, pattern)                    # 现状值
        refs = _evidence(facts, pattern)                        # 证据
        gaps: List[str] = []                                   # 缺口
        if value is None:                                      # 无现状值
            gaps.append("现状值未采集")                           # 记缺口
        if not refs:                                           # 无证据
            gaps.append("缺少事实编号")                           # 记缺口
        gaps.append("分母与统计周期待书面确认")                    # 口径类缺口统一提示
        level = Confidence.ESTIMATE if refs else Confidence.TBD   # 有证据仍属估计，无证据为待定
        rows.append(BaselineRow(indicator=indicator, molecule=molecule,
                                denominator=denominator, period="TBD", source=source,
                                owner=DEFAULT_OWNER,
                                current=value or "TBD", level=level,
                                evidence=refs, gaps=gaps))      # 组装行
    tbd = sum(1 for row in rows for field in (row.molecule, row.denominator, row.period,
                                              row.source, row.owner, row.current) if field == "TBD")   # 统计待定
    return BaselineOutput(rows=rows, tbd_count=tbd)             # 返回
