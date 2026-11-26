# -*- coding: utf-8 -*-
"""契约模型：所有 agent 的输入输出都必须经过这里定义的 schema 校验。"""

from enum import Enum                                      # 证据等级枚举
from typing import List                                    # 列表类型
from pydantic import BaseModel, Field, ConfigDict            # 强约束与配置


class Level(str, Enum):                                    # 证据等级：决定数字能否进验收材料
    FACT = "fact"                                          # 事实级：角色明确陈述
    ESTIMATE = "estimate"                                  # 估计级：有数无口径
    EXTRAPOLATION = "extrapolation"                        # 推算级：以估计值推的量级
    TBD = "tbd"                                            # 待定级：尚未核实


class Claim(BaseModel):                                    # 单条结论：必须挂事实编号
    model_config = ConfigDict(extra="forbid")              # 禁止多余字段，防止模型夹带私货
    text: str = Field(min_length=2, max_length=500)        # 结论文本
    fact_id: str = Field(default="", max_length=8)         # 事实编号；是否合法交由证据闸门判定，保证错误码统一



class EvidenceOutput(BaseModel):                           # A1 证据抽取的输出契约
    model_config = ConfigDict(extra="forbid")              # 禁止额外字段
    claims: List[Claim] = Field(default_factory=list)      # 结论列表，可为空表示无证据


class Verdict(BaseModel):                                  # A5 核验结论
    model_config = ConfigDict(extra="forbid")              # 禁止额外字段
    passed: bool                                           # 是否通过
    reason: str = Field(min_length=2, max_length=300)      # 判定理由
    missing: List[str] = Field(default_factory=list)       # 缺失项清单


class SelftestEcho(BaseModel):                             # 自测用最小契约
    model_config = ConfigDict(extra="forbid")              # 禁止额外字段
    step: str = Field(min_length=1, max_length=64)         # 步骤名
    ok: bool                                               # 占位标记
