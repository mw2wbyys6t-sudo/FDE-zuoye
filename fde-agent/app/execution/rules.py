# -*- coding: utf-8 -*-
"""规则引擎：R1 规格差异、R2 取消状态、R3 说明随单、R4 系统不可用。"""

from typing import List                                      # 类型标注
from app.execution.models import Decision, Reason, ScanContext   # 契约

RULE_VERSION = "exec-v1"                                     # 规则版本，随方案签核后升级


def _r1(ctx: ScanContext) -> List[Reason]:                    # 规格差异
    """检测同系列相邻货位的规格差异。

    入参：ctx 扫码上下文。
    出参：命中则返回一条理由，否则空列表。
    失败行为：不抛异常。
    """
    if not ctx.spec or not ctx.neighbor_specs:                 # 缺规格信息
        return []                                             # 不出卡
    # 原因：只要相邻货位出现与当前不同的规格，就有拿错可能；规格全相同则不打扰现场
    if any(spec != ctx.spec for spec in ctx.neighbor_specs):    # 存在不同规格
        return [Reason(rule_id="R1", message="同系列相邻货位存在不同规格，请核对包装与规格字段",
                       fact_refs=["f10"])]                     # 提示
    return []                                                 # 无邻位冲突


def _r2(ctx: ScanContext) -> List[Reason]:                    # 取消状态
    """检测订单已取消但仍在流转。

    入参：ctx 扫码上下文。
    出参：命中返回理由。
    失败行为：不抛异常。
    """
    if not ctx.cancelled:                                     # 未取消
        return []                                             # 不出卡
    # 原因：取消状态可能滞后 12 分钟，必须同时回显数据截止时间，避免现场误以为实时
    suffix = "（状态可能滞后，截止 %s）" % (ctx.data_asof or "未提供")   # 滞后说明
    return [Reason(rule_id="R2", message="该单已取消，请暂停并交波次计划员核对" + suffix,
                   fact_refs=["f11", "f31"])]                  # 挂起理由


def _r3(ctx: ScanContext) -> List[Reason]:                    # 说明随单
    """检测关键说明未随单据结构化交接。

    入参：ctx 扫码上下文。
    出参：命中返回理由。
    失败行为：不抛异常。
    """
    if ctx.note_text and not ctx.note_attached:                # 有说明但没随单
        return [Reason(rule_id="R3", message="该单的说明只存在于便签或群消息，未随单据交接",
                       fact_refs=["f14", "f23"])]              # 提示
    return []                                                 # 无问题


def _r4(ctx: ScanContext) -> List[Reason]:                    # 系统不可用
    """检测关键系统不可用或资料缺依据。

    入参：ctx 扫码上下文。
    出参：命中返回理由。
    失败行为：不抛异常。
    """
    if not ctx.system_available:                               # 系统不可用
        return [Reason(rule_id="R4", message="关键系统不可用，已转人工，请记录原因与接手人",
                       fact_refs=["f44", "f35"])]              # 挂起
    return []                                                 # 正常


def evaluate(ctx: ScanContext) -> Decision:                    # 入口
    """对一次扫码执行全部规则并给出判定。

    入参：ctx 扫码上下文。
    出参：Decision，level 取 hold > hint > pass。
    失败行为：不抛异常；输入字段缺失时按不出卡处理。
    """
    reasons = _r4(ctx) + _r2(ctx) + _r1(ctx) + _r3(ctx)        # 按优先级收集，便于人读
    if not reasons:                                            # 全部未命中
        return Decision(biz_id=ctx.biz_id, level="pass",
                        reasons=[], data_asof=ctx.data_asof, rule_version=RULE_VERSION)   # 放行
    holds = [r for r in reasons if r.rule_id in ("R2", "R4")]    # 需要人处置的规则
    level = "hold" if holds else "hint"                        # 优先级
    role = "planner" if any(r.rule_id == "R2" for r in holds) else ("safety" if holds else "")   # 处置岗位
    return Decision(biz_id=ctx.biz_id, level=level, reasons=reasons,
                    requires_human=bool(holds), human_role=role,
                    data_asof=ctx.data_asof, rule_version=RULE_VERSION)   # 返回判定
