# -*- coding: utf-8 -*-
"""A5 独立核验：不共享上游上下文，只按证据与规则判定通过与否。"""

from typing import Any, Dict, Iterable, List, Set             # 类型标注
from app.agents.contracts import BaselineOutput, VerifyItem, VerifyOutput   # 输出契约


def _missing(claims: Iterable[Dict[str, Any]], known: Set[str]) -> List[str]:   # 缺失项
    """返回结论中不合法或不存在的事实编号。

    入参：claims 结论列表；known 已知编号。
    出参：缺失编号列表。
    失败行为：不抛异常。
    """
    missing: List[str] = []                                    # 结果
    for claim in claims:                                       # 逐条
        fact_id = str(claim.get("fact_id") or "").strip()       # 取编号
        if not fact_id or fact_id not in known:                 # 缺失或不存在
            missing.append(fact_id or "<空>")                    # 记录
    return missing                                             # 返回


def verify_claims(claims: List[Dict[str, Any]], known: Set[str]) -> VerifyOutput:   # 核验结论
    """逐条核验结论是否带真实事实编号。

    入参：claims 结论；known 已知编号。
    出参：VerifyOutput。
    失败行为：不抛异常。
    """
    items: List[VerifyItem] = []                               # 结果
    for index, claim in enumerate(claims):                      # 逐条
        missing = _missing([claim], known)                      # 缺失
        items.append(VerifyItem(target="claim#%d" % (index + 1), passed=not missing,
                                reason="证据齐全" if not missing else "证据缺失",
                                missing=missing))                # 组装
    return VerifyOutput(items=items, passed=all(i.passed for i in items))   # 汇总


def verify_baseline(output: BaselineOutput, known: Set[str]) -> VerifyOutput:   # 核验基线
    """核验每行基线是否可追溯，并标出估计与待定。

    入参：output 基线输出；known 已知编号。
    出参：VerifyOutput。
    失败行为：不抛异常。
    """
    items: List[VerifyItem] = []                                # 结果
    for row in output.rows:                                     # 逐行
        missing = [fid for fid in row.evidence if fid not in known]   # 不存在的编号
        if not row.evidence:                                    # 完全无证据
            missing.append("<无证据>")                           # 记缺失
        needs_human = row.level.value in ("estimate", "extrapolation")   # 估计值需人工确认
        passed = not missing                                    # 有证据即结构通过
        reason = "可追溯" if passed else "证据不足"
        if passed and needs_human:                              # 结构通过但等级不足
            reason = "可追溯，但为估计值，需书面确认口径"          # 提示
        items.append(VerifyItem(target=row.indicator, passed=passed,
                                reason=reason, missing=missing))   # 组装
    return VerifyOutput(items=items, passed=all(i.passed for i in items))   # 汇总


def _bigrams(text: str) -> Set[str]:                           # 字符二元组
    """把中文文本切成字符二元组集合。

    入参：text 文本。
    出参：二元组集合。
    失败行为：短于 2 字时返回单字集合，保证非空。
    """
    clean = "".join(ch for ch in text if ch.strip())            # 去掉空白
    if len(clean) < 2:                                         # 过短
        return set(clean)                                       # 返回单字
    return {clean[i:i + 2] for i in range(len(clean) - 1)}      # 二元组


def verify_relevance(claims: List[Dict[str, Any]], facts: Dict[str, str],
                     min_overlap: float = 0.25) -> VerifyOutput:   # 相关性核验
    """校验结论文本与被引用事实确实相关。

    入参：claims 结论；facts 编号到陈述的映射；min_overlap 最小重合比例。
    出参：VerifyOutput。
    失败行为：不抛异常；事实缺失时判为不相关。
    """
    items: List[VerifyItem] = []                                # 结果
    for index, claim in enumerate(claims):                      # 逐条
        fact_id = str(claim.get("fact_id") or "").strip()       # 编号
        statement = facts.get(fact_id, "")                      # 对应陈述
        if not statement:                                       # 编号不在台账
            items.append(VerifyItem(target="claim#%d" % (index + 1), passed=False,
                                    reason="事实编号不存在", missing=[fact_id or "<空>"]))   # 失败
            continue                                            # 下一条
        claim_set = _bigrams(str(claim.get("text", "")))        # 结论二元组
        fact_set = _bigrams(statement)                          # 事实二元组
        overlap = len(claim_set & fact_set) / max(1, len(claim_set))   # 重合比例
        passed = overlap >= min_overlap                         # 是否达标
        items.append(VerifyItem(target="claim#%d" % (index + 1), passed=passed,
                                reason="相关度 %.2f" % overlap,
                                missing=[] if passed else ["文本与证据不匹配"]))   # 组装
    return VerifyOutput(items=items, passed=all(i.passed for i in items))   # 汇总


def verify_all(claims: List[Dict[str, Any]], baseline: BaselineOutput,
               known: Set[str]) -> VerifyOutput:                # 总核验
    """合并结论与基线两条核验链。

    入参：claims 结论；baseline 基线；known 已知编号。
    出参：VerifyOutput。
    失败行为：不抛异常。
    """
    first = verify_claims(claims, known)                        # 结论核验
    second = verify_baseline(baseline, known)                   # 基线核验
    items = first.items + second.items                          # 合并
    return VerifyOutput(items=items, passed=all(i.passed for i in items))   # 汇总
