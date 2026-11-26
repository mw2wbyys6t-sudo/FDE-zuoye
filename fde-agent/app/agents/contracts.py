# -*- coding: utf-8 -*-
"""Agent 契约：冲突、基线、核验三组输出结构，全部强约束。"""

from typing import List                                     # 列表
from pydantic import BaseModel, Field, ConfigDict             # 强约束
from app.domain.models import Confidence                      # 证据等级


class Conflict(BaseModel):                                   # 一条冲突
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    kind: str = Field(pattern=r"^(value|definition|scope)$")   # 冲突类型：数值/口径/范围
    metric: str = Field(min_length=1, max_length=40)         # 涉及指标或议题
    values: List[str] = Field(min_length=2)                  # 冲突的具体值
    fact_refs: List[str] = Field(min_length=1)               # 涉及的证据编号；单条事实也可能同时陈述两种口径
    question: str = Field(min_length=2, max_length=200)      # 需要人回答的核对问题


class ConflictOutput(BaseModel):                             # 冲突检测输出
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    conflicts: List[Conflict] = Field(default_factory=list)   # 冲突列表


class BaselineRow(BaseModel):                                # 指标基线一行
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    indicator: str = Field(min_length=2, max_length=40)      # 指标名
    molecule: str = Field(default="TBD", max_length=120)     # 分子
    denominator: str = Field(default="TBD", max_length=120)  # 分母
    period: str = Field(default="TBD", max_length=80)        # 统计周期
    source: str = Field(default="TBD", max_length=120)       # 数据来源
    owner: str = Field(default="TBD", max_length=80)         # 出数责任人
    current: str = Field(default="TBD", max_length=80)       # 现状值
    level: Confidence = Confidence.TBD                       # 证据等级
    evidence: List[str] = Field(default_factory=list)        # 依据事实编号
    gaps: List[str] = Field(default_factory=list)            # 缺口说明


class BaselineOutput(BaseModel):                             # 基线输出
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    rows: List[BaselineRow] = Field(default_factory=list)     # 指标行
    tbd_count: int = Field(default=0, ge=0)                  # 待定字段数量


class VerifyItem(BaseModel):                                 # 单条核验
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    target: str = Field(min_length=1, max_length=80)         # 被核验对象
    passed: bool                                             # 是否通过
    reason: str = Field(min_length=2, max_length=200)        # 理由
    missing: List[str] = Field(default_factory=list)         # 缺失项


class VerifyOutput(BaseModel):                               # 核验输出
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    items: List[VerifyItem] = Field(default_factory=list)     # 核验项
    passed: bool = False                                     # 总体是否通过


class RuleDraft(BaseModel):                                  # 方案中的一条规则
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    rule_id: str = Field(pattern=r"^R[1-9]$")                 # R1–R9
    trigger: str = Field(min_length=2, max_length=200)        # 触发条件
    output: str = Field(min_length=2, max_length=200)         # 输出内容
    fallback: str = Field(min_length=2, max_length=200)       # 兜底路径
    fact_refs: List[str] = Field(default_factory=list)        # 依据事实


class DesignOutput(BaseModel):                               # A4 方案输出
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    pilot_scope: str = Field(min_length=4, max_length=200)    # 最小试点范围
    why: List[str] = Field(min_length=2)                      # 选择理由
    interfaces: List[str] = Field(default_factory=list)       # 数据与接口
    rules: List[RuleDraft] = Field(default_factory=list)      # 规则草案
    acceptance: List[str] = Field(min_length=1)               # 验收标准
    stop_conditions: List[str] = Field(min_length=1)          # 停止条件
    boundary: List[str] = Field(min_length=1)                 # 不做清单
    open_questions: List[str] = Field(default_factory=list)   # 待核实问题
    fact_refs: List[str] = Field(default_factory=list)        # 方案引用的事实编号
