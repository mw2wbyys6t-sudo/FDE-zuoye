# -*- coding: utf-8 -*-
"""领域模型：事实、规则、指标、案例四条主线共用的数据结构。"""

from enum import Enum                                     # 维度与置信度枚举
from typing import List                                   # 列表类型
from pydantic import BaseModel, Field, ConfigDict          # 强约束


class Dimension(str, Enum):                               # 知识库四维
    FACT = "fact"                                         # D1 事实：访谈事实台账
    RULE = "rule"                                         # D2 规则：红线、审批、版本约束
    INDICATOR = "indicator"                               # D3 指标：分子分母、周期、责任人
    CASE = "case"                                         # D4 案例：错例、回放、误判


class Confidence(str, Enum):                              # 证据分级
    FACT = "fact"                                         # 事实级
    ESTIMATE = "estimate"                                 # 估计级
    EXTRAPOLATION = "extrapolation"                       # 推算级
    TBD = "tbd"                                           # 待定级


class Fact(BaseModel):                                    # 一条结构化事实
    model_config = ConfigDict(extra="forbid")             # 禁止多余字段
    fact_id: str = Field(pattern=r"^f[0-9]{2}$")          # 事实编号，全库唯一
    role: str = Field(min_length=1, max_length=32)        # 陈述角色
    statement: str = Field(min_length=2, max_length=1000)  # 陈述正文
    source: str = Field(default="", max_length=120)       # 来源文件名或资料编号
    source_type: str = Field(default="", max_length=40)   # 来源类型：访谈事实/流程约束等
    dimension: Dimension = Dimension.FACT                 # 归属维度
    confidence: Confidence = Confidence.FACT              # 证据等级
    version: str = Field(default="v1", max_length=16)     # 版本号，支持按版本检索
    roles_visible: List[str] = Field(default_factory=list)  # 可见角色白名单


class Chunk(BaseModel):                                   # 检索最小单元
    model_config = ConfigDict(extra="forbid")             # 禁止多余字段
    chunk_id: str                                         # 形如 f11#0
    fact_id: str                                          # 所属事实编号
    text: str                                             # 文本片段
    dimension: Dimension                                  # 维度
    confidence: Confidence                                # 证据等级
    version: str                                          # 版本
    roles_visible: List[str]                              # 可见角色
    source: str                                           # 来源


class Hit(BaseModel):                                     # 检索命中
    model_config = ConfigDict(extra="forbid")             # 禁止多余字段
    chunk_id: str                                         # 片段编号
    fact_id: str                                          # 事实编号
    score: float                                          # 相关度分数
    text: str                                             # 片段文本
    dimension: Dimension                                  # 维度
    confidence: Confidence                                # 证据等级
    source: str                                           # 来源
