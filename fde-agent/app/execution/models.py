# -*- coding: utf-8 -*-
"""执行层契约：扫码上下文、判定结果、处置记录与指标。"""

from typing import List, Optional                            # 类型标注
from pydantic import BaseModel, Field, ConfigDict             # 强约束


class ScanContext(BaseModel):                                # 一次扫码/拣选上下文
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    biz_id: str = Field(min_length=3, max_length=40)          # 业务编号（波次行或订单）
    sku: str = Field(min_length=1, max_length=40)             # 实际扫描 SKU
    base_sku: str = Field(min_length=1, max_length=40)        # 同系列基础编号
    spec: str = Field(default="", max_length=40)              # 当前规格
    neighbor_specs: List[str] = Field(default_factory=list)    # 相邻货位规格
    cancelled: bool = False                                  # 订单是否已取消（装车侧可见状态）
    cancel_seen_ago_min: Optional[int] = Field(default=None, ge=0)   # 取消事件已过去分钟数
    note_text: str = Field(default="", max_length=200)        # 随单说明文本
    note_attached: bool = Field(default=True)                 # 说明是否随单据结构化交接
    system_available: bool = Field(default=True)              # 关键系统是否可用
    data_asof: str = Field(default="", max_length=40)         # 数据截止时间，必须回显


class Reason(BaseModel):                                     # 单条判定理由
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    rule_id: str = Field(pattern=r"^R[1-9]$")                 # R1–R9
    message: str = Field(min_length=2, max_length=200)        # 给现场看的一句话
    fact_refs: List[str] = Field(default_factory=list)        # 依据事实编号


class Decision(BaseModel):                                   # 判定结果
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    decision_id: str = Field(default="pending", min_length=6, max_length=40)   # 规则层占位，服务层补发
    biz_id: str = Field(min_length=3, max_length=40)          # 业务编号
    level: str = Field(pattern=r"^(pass|hint|hold)$")         # 放行 / 提示 / 挂起
    reasons: List[Reason] = Field(default_factory=list)       # 理由
    requires_human: bool = False                             # 是否必须人工处置
    human_role: str = Field(default="", max_length=20)        # 处置岗位
    data_asof: str = Field(default="", max_length=40)         # 数据截止时间
    rule_version: str = Field(default="exec-v1", max_length=20)   # 规则版本，便于回放
    dedupe: bool = False                                     # 是否为重复扫码复用结果（不再重复出卡）


class DispositionIn(BaseModel):                              # 处置请求
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    decision_id: str = Field(min_length=6, max_length=40)     # 判定编号
    action: str = Field(pattern=r"^(accept|override|return)$")   # 采纳 / 覆盖 / 退回
    operator: str = Field(default="", max_length=40)          # 接手人（挂起单必填）
    reason: str = Field(default="", max_length=200)           # 触发原因（挂起单必填）
    confirmed_at: str = Field(default="", max_length=40)      # 确认时间（挂起单必填）
    note: str = Field(default="", max_length=200)             # 备注


class Disposition(BaseModel):                                # 处置记录
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    disposition_id: str = Field(min_length=6, max_length=40)  # 处置编号
    decision_id: str = Field(min_length=6, max_length=40)     # 对应判定
    action: str = Field(min_length=5, max_length=10)          # 动作
    operator: str = Field(default="", max_length=40)          # 接手人
    reason: str = Field(default="", max_length=200)           # 原因
    confirmed_at: str = Field(default="", max_length=40)      # 确认时间
    closed: bool = False                                     # 是否闭环
