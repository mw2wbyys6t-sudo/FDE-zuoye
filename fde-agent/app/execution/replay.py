# -*- coding: utf-8 -*-
"""历史回放评估：拿真实标注单跑规则，算命中率、误报率与分规则贡献。"""

from typing import Any, Dict, List                            # 类型标注
from app.execution.importer import PickingRecord               # 记录
from app.execution.models import ScanContext                    # 上下文
from app.execution.rules import evaluate                        # 规则


def _confusion(pairs: List[tuple]) -> Dict[str, int]:          # 混淆矩阵
    """统计标记与真实标签的四格。

    入参：pairs [(是否被标记, 是否真错发)]。
    出参：tp/fp/fn/tn。
    失败行为：不抛异常。
    """
    tp = sum(1 for flagged, truth in pairs if flagged and truth)     # 命中
    fp = sum(1 for flagged, truth in pairs if flagged and not truth)  # 误报
    fn = sum(1 for flagged, truth in pairs if not flagged and truth)  # 漏报
    tn = sum(1 for flagged, truth in pairs if not flagged and not truth)   # 正确放行
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}             # 返回


def replay(records: List[PickingRecord]) -> Dict[str, Any]:    # 回放
    """对一批记录执行规则并与标注比对。

    入参：records 带 is_error 标注的记录。
    出参：指标字典；无标注时 labeled=False 且指标为 None。
    失败行为：不抛异常。
    """
    labeled = [r for r in records if r.is_error is not None]    # 只统计有标注的
    pairs: List[tuple] = []                                    # 标记与真值
    by_rule: Dict[str, int] = {}                               # 分规则命中
    levels = {"pass": 0, "hint": 0, "hold": 0}                  # 判定分布
    for record in labeled:                                     # 逐条
        decision = evaluate(record.ctx)                         # 跑规则
        levels[decision.level] += 1                             # 分布
        flagged = decision.level in ("hint", "hold")            # 是否被拦
        pairs.append((flagged, bool(record.is_error)))          # 收集
        for reason in decision.reasons:                         # 分规则
            by_rule[reason.rule_id] = by_rule.get(reason.rule_id, 0) + 1   # 累加
    if not pairs:                                              # 无标注
        return {"labeled": False, "total": len(records), "levels": levels,
                "by_rule": by_rule, "precision": None, "recall": None, "f1": None}   # 返回
    cell = _confusion(pairs)                                   # 混淆矩阵
    precision = cell["tp"] / (cell["tp"] + cell["fp"]) if (cell["tp"] + cell["fp"]) else 0.0   # 精确率
    recall = cell["tp"] / (cell["tp"] + cell["fn"]) if (cell["tp"] + cell["fn"]) else 0.0      # 召回率
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0       # F1
    return {"labeled": True, "total": len(records), "labeled_count": len(pairs),
            "levels": levels, "confusion": cell, "by_rule": by_rule,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "flag_rate": round(sum(1 for f, _ in pairs if f) / len(pairs), 3)}   # 返回


def replay_ctx(ctxs: List[ScanContext]) -> Dict[str, Any]:     # 无标注回放
    """只跑规则、不比对标签，用于观察命中结构。

    入参：ctxs 上下文列表。
    出参：判定分布与分规则命中。
    失败行为：不抛异常。
    """
    levels = {"pass": 0, "hint": 0, "hold": 0}                  # 分布
    by_rule: Dict[str, int] = {}                               # 分规则
    for ctx in ctxs:                                           # 逐条
        decision = evaluate(ctx)                               # 判定
        levels[decision.level] += 1                            # 计数
        for reason in decision.reasons:                        # 分规则
            by_rule[reason.rule_id] = by_rule.get(reason.rule_id, 0) + 1   # 累加
    return {"labeled": False, "total": len(ctxs), "levels": levels, "by_rule": by_rule,
            "precision": None, "recall": None, "f1": None}   # 返回
