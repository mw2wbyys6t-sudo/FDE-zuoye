# -*- coding: utf-8 -*-
"""A4 方案生成：用基线、冲突与事实拼出最小试点方案，全部结论带编号。"""

from typing import List                                      # 类型标注
from app.agents.contracts import (BaselineOutput, ConflictOutput, DesignOutput,
                                  RuleDraft)                  # 上游输出与自身契约

PILOT_SCOPE = ("单仓区 · 相邻货位相似包装 SKU：拣选扫码解释 + 装车核验错配提醒（只提示，不阻断）")   # 固定范围


def build(baseline: BaselineOutput, conflicts: ConflictOutput) -> DesignOutput:   # 入口
    """由上游产物生成最小试点方案。

    入参：baseline 口径基线；conflicts 冲突检测结果。
    出参：DesignOutput。
    失败行为：输入为空时仍返回骨架方案，但 open_questions 会提示缺证据。
    """
    refs = sorted({fid for row in baseline.rows for fid in row.evidence})   # 汇总基线证据
    for conflict in conflicts.conflicts:                       # 冲突里的证据也要带上
        refs.extend(conflict.fact_refs)                        # 追加
    refs = sorted(set(refs))                                   # 去重排序
    why = [                                                    # 选择理由
        "两处损害都发生在装车扫码之前，提示最早可落在拣货员手边（f11）",
        "提示不改原记录、可一键撤回，失败代价低于阻断（f15）",
        "同时作用于错发率与复核漏扫两条验收硬线，无需另造指标（f02/f42）",
    ]
    rules = [                                                  # 四条规则草案
        RuleDraft(rule_id="R1", trigger="同货位或相邻货位存在同系列不同规格 SKU",
                  output="并排展示规格差异字段与实物核对提示",
                  fallback="字段缺失不出卡；出卡后 3 秒内可标已核对", fact_refs=["f10"]),
        RuleDraft(rule_id="R2", trigger="业务编号存在取消事件且晚于该单可见状态",
                  output="提示该单已取消，暂停建议交波次计划员核对",
                  fallback="显示数据截止时间，窗口内不承诺实时", fact_refs=["f11", "f31"]),
        RuleDraft(rule_id="R3", trigger="拣选行存在便签或群消息中的非正式说明",
                  output="把说明结构化进单据字段并随单流转",
                  fallback="超过一个更新周期标待刷新", fact_refs=["f14", "f23"]),
        RuleDraft(rule_id="R4", trigger="资料缺依据、版本冲突或系统不可用",
                  output="转人工并记录触发原因、接手人、确认时间",
                  fallback="三要素缺一不予关闭", fact_refs=["f44"]),
    ]
    open_questions = [c.question for c in conflicts.conflicts]   # 冲突即待答问题
    open_questions.extend(["%s 的分母与统计周期由谁书面确认" % row.indicator
                           for row in baseline.rows if row.current == "TBD"])   # 无现状值的指标
    return DesignOutput(pilot_scope=PILOT_SCOPE, why=why,
                        interfaces=[row.source for row in baseline.rows] + ["只读接入，不回写业务库（f32）"],
                        rules=rules,
                        acceptance=["错发率下降（口径已冻结）", "复核漏扫为零",
                                    "高位叉车 / 危险品 / 冷链规程未放宽（f42/f40）"],
                        stop_conditions=["触及停止条件即暂停试点，由负责人复盘（f42）",
                                         "出现自动审批或写库动作即终止（f41）"],
                        boundary=["不自动操作叉车、不做盘盈盘亏（f05/f52）",
                                  "不写业务库、不改货位与库存（f32）",
                                  "阻断型拦截须顾明岚与傅景书面批准（f34）"],
                        open_questions=open_questions, fact_refs=refs)   # 组装方案
