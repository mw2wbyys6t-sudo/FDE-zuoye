# -*- coding: utf-8 -*-
"""记忆模型：四层记忆 + 可见性与有效期。"""

from enum import Enum                                       # 枚举
from typing import List                                     # 列表
from pydantic import BaseModel, Field, ConfigDict             # 强约束


class MemoryLayer(str, Enum):                               # 记忆分层
    WORKING = "working"                                     # 会话内临时上下文
    EPISODIC = "episodic"                                   # 任务轨迹摘要
    SEMANTIC = "semantic"                                   # 已核验的事实与规则
    PROCEDURAL = "procedural"                               # 流程模板与环境画像


class MemoryItem(BaseModel):                                # 一条记忆
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    memory_id: str = Field(min_length=6, max_length=40)       # 唯一编号
    layer: MemoryLayer                                       # 所属层
    text: str = Field(min_length=2, max_length=800)          # 记忆正文
    fact_refs: List[str] = Field(default_factory=list)       # 关联事实编号
    role: str = Field(default="system", max_length=32)       # 写入角色
    version: str = Field(default="v1", max_length=16)        # 版本
    verified: bool = Field(default=False)                    # 是否已通过核验
    visibility: List[str] = Field(default_factory=list)      # 可见角色
    created_at: str = Field(default="", max_length=40)       # 写入时间
    expires_at: str = Field(default="", max_length=40)       # 过期时间
    conflict: bool = Field(default=False)                    # 是否与其他记忆冲突
