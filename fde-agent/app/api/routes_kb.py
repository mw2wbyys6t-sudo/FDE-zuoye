# -*- coding: utf-8 -*-
"""知识库接口：入库、检索、统计三个端点，全部走统一响应与角色闸门。"""

from pathlib import Path                                   # 路径校验
from typing import Any, Dict, List, Optional                # 类型标注
from fastapi import APIRouter, Depends, HTTPException       # 路由与依赖
from pydantic import BaseModel, Field                       # 请求体契约
from app.api.envelope import ok                             # 统一响应
from app.deps import ALLOWED_ROLES, KB, ROLE_DEP            # 依赖单例
from app.domain.models import Dimension                     # 维度枚举
from app.harness.guards import GuardError, check_permission   # 权限闸门
from app.knowledge.ingest import parse_ledger_file          # 台账解析
from app.knowledge.retrieve import Retriever                # 检索器

router = APIRouter(prefix="/v1/kb", tags=["kb"])            # 路由前缀


class IngestRequest(BaseModel):                             # 入库请求
    path: str = Field(min_length=3, max_length=500)         # 台账文件路径


class SearchRequest(BaseModel):                             # 检索请求
    query: str = Field(min_length=1, max_length=200)        # 查询串
    dimension: Optional[Dimension] = None                   # 维度过滤
    version: Optional[str] = Field(default=None, max_length=16)   # 版本过滤
    top_k: int = Field(default=5, ge=1, le=20)              # 返回条数


@router.get("/stats")                                       # 统计
def stats(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """返回知识库统计。

    入参：role 由请求头注入。
    出参：统一三键结构。
    失败行为：不抛异常。
    """
    try:                                                     # 权限校验
        check_permission(role, ALLOWED_ROLES)   # 任意合法角色可读统计
    except GuardError as exc:                                # 无权限
        raise HTTPException(status_code=403, detail=exc.msg)  # 交给统一处理器
    return ok(KB.stats())                                 # 返回统计


@router.post("/ingest")                                     # 入库
def ingest(body: IngestRequest, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """把台账文件灌入知识库并落盘。

    入参：body 含文件路径；role 需为 engineer 或 admin。
    出参：统一三键结构，data 含 facts 与 chunks 数量。
    失败行为：文件不存在返回 400；无权限返回 403。
    """
    try:                                                     # 权限校验
        # 原因：入库会改变检索结果与可见性配置，属高影响操作，只允许工程与管理员角色执行
        check_permission(role, ALLOWED_ROLES, require_write=True,
                         write_roles=["engineer", "admin"])   # 收紧写权限
    except GuardError as exc:                                # 无权限
        raise HTTPException(status_code=403, detail=exc.msg)  # 转统一结构
    path = Path(body.path)                                   # 路径对象
    if not path.exists() or path.suffix.lower() not in (".md", ".txt"):   # 只接受文本台账
        raise HTTPException(status_code=400, detail="仅支持已存在的 .md/.txt 台账文件")   # 拒绝
    facts = parse_ledger_file(str(path))                     # 解析台账
    result = KB.ingest(facts)                             # 入库
    KB.save()                                             # 落盘
    return ok({"ingested": result, "stats": KB.stats()})   # 返回统计


@router.post("/search")                                     # 检索
def search(body: SearchRequest, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按角色与维度检索知识片段。

    入参：body 查询条件；role 由请求头注入。
    出参：统一三键结构，data.hits 为命中列表。
    失败行为：查询为空返回空列表；无权限返回 403。
    """
    try:                                                     # 权限校验
        check_permission(role, ALLOWED_ROLES)   # 任意合法角色可检索
    except GuardError as exc:                                # 无权限
        raise HTTPException(status_code=403, detail=exc.msg)  # 转统一结构
    retriever = Retriever(KB)                                # 构造检索器
    hits = retriever.search(body.query, role=role, top_k=body.top_k,
                            dimension=body.dimension, version=body.version)   # 执行检索
    return ok({"hits": [h.model_dump() for h in hits], "count": len(hits)})   # 返回
