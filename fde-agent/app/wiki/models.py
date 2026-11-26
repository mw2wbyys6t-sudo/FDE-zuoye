# -*- coding: utf-8 -*-
"""Wiki 模型：页面、版本快照与审计条目。"""

from typing import List                                     # 列表
from pydantic import BaseModel, Field, ConfigDict             # 强约束
from app.domain.models import Dimension                       # 复用四维枚举


class WikiPage(BaseModel):                                   # 页面当前状态
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{2,48}$")   # 页面标识，小写短横线
    title: str = Field(min_length=2, max_length=80)          # 标题
    summary: str = Field(default="", max_length=300)         # 摘要
    body: str = Field(min_length=1, max_length=20000)        # 正文 Markdown
    dimension: Dimension = Dimension.FACT                    # 归属维度
    fact_refs: List[str] = Field(default_factory=list)       # 引用的事实编号
    visibility: List[str] = Field(default_factory=list)      # 可见角色
    status: str = Field(default="draft", pattern=r"^(draft|published|archived)$")   # 状态
    version: int = Field(default=1, ge=1)                    # 当前版本号
    owner: str = Field(default="", max_length=32)            # 创建者角色
    updated_at: str = Field(default="", max_length=40)       # 更新时间


class WikiRevision(BaseModel):                               # 版本快照
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    slug: str                                                # 页面标识
    version: int                                             # 版本号
    title: str                                               # 标题
    body: str                                                # 正文
    status: str                                              # 当时状态
    editor: str                                              # 编辑角色
    created_at: str                                          # 快照时间


class AuditEntry(BaseModel):                                 # 审计条目
    model_config = ConfigDict(extra="forbid")                # 禁止多余字段
    action: str = Field(pattern=r"^(create|update|publish|rollback|archive)$")   # 动作类型
    slug: str                                                # 页面标识
    role: str                                                # 操作角色
    version: int                                             # 涉及版本
    detail: str = Field(default="", max_length=200)          # 说明
    created_at: str                                          # 时间
