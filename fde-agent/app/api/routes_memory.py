# -*- coding: utf-8 -*-
"""记忆接口：写入、检索、统计，全部按角色与层过滤。"""

from typing import Any, Dict, List, Optional                  # 类型标注
from fastapi import APIRouter, Depends, HTTPException         # 路由与依赖
from pydantic import BaseModel, Field                          # 请求体
from app.api.envelope import ok                                # 统一响应
from app import errors as E                                    # 错误码
from app.deps import ALLOWED_ROLES, MEMORY, ROLE_DEP            # 依赖单例
from app.harness.guards import GuardError, check_permission     # 权限闸门
from app.memory.models import MemoryLayer                       # 层枚举
from app.memory.policy import MemoryPolicyError                  # 策略异常

router = APIRouter(prefix="/v1/memory", tags=["memory"])        # 路由前缀


class WriteIn(BaseModel):                                      # 写入请求
    layer: MemoryLayer = MemoryLayer.WORKING                     # 目标层
    text: str = Field(min_length=2, max_length=800)              # 正文
    fact_refs: List[str] = Field(default_factory=list)           # 事实编号
    verified: bool = False                                       # 是否已核验
    visibility: Optional[List[str]] = None                       # 可见角色
    task_id: str = Field(default="", max_length=64)              # 任务编号


class SearchIn(BaseModel):                                     # 检索请求
    query: str = Field(min_length=1, max_length=200)             # 查询串
    layer: Optional[MemoryLayer] = None                          # 层过滤
    top_k: int = Field(default=5, ge=1, le=20)                   # 返回条数


def _fail(exc: Exception) -> HTTPException:                     # 异常转换
    """把策略或权限异常转成 HTTP 异常。

    入参：exc 异常对象。
    出参：HTTPException。
    失败行为：无。
    """
    code = getattr(exc, "code", E.E_INTERNAL)                    # 取错误码
    status = 403 if code in (E.E_PERM, E.E_HUMAN_REQUIRED) else 400   # 权限类 403
    return HTTPException(status_code=status, detail="%s: %s" % (code, str(exc)))   # 带上错误码


@router.post("/write")                                         # 写入
def write(body: WriteIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """写入一条记忆。

    入参：body 记忆内容；role 角色。
    出参：统一三键结构，data 含 memory_id 与是否冲突。
    失败行为：违反策略返回 4xx。
    """
    try:                                                        # 权限校验
        # 原因：语义层记忆会进入全局检索，写权限必须限定在工程与管理员
        check_permission(role, ALLOWED_ROLES, require_write=True,
                         write_roles=["engineer", "admin"])     # 写权限
        result = MEMORY.write(layer=body.layer, text=body.text, fact_refs=body.fact_refs,
                              role=role, verified=body.verified,
                              visibility=body.visibility, task_id=body.task_id)   # 写入
    except (GuardError, MemoryPolicyError) as exc:             # 权限或策略异常
        raise _fail(exc)                                        # 转 HTTP
    return ok(result)                                           # 返回


@router.post("/search")                                        # 检索
def search(body: SearchIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按角色、层与相关度检索记忆。

    入参：body 查询条件；role 角色。
    出参：统一三键结构，data.items 为命中。
    失败行为：无权限返回 403。
    """
    try:                                                        # 权限校验
        check_permission(role, ALLOWED_ROLES)                   # 任意合法角色可读
    except GuardError as exc:                                   # 无权限
        raise _fail(exc)                                        # 转 HTTP
    items = MEMORY.search(body.query, role=role, layer=body.layer, top_k=body.top_k)   # 检索
    return ok({"items": [item.model_dump() for item in items], "count": len(items)})   # 返回


@router.get("/stats")                                          # 统计
def stats(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """返回记忆分层统计。

    入参：role 角色。
    出参：统一三键结构。
    失败行为：无权限返回 403。
    """
    try:                                                        # 权限校验
        check_permission(role, ALLOWED_ROLES)                   # 任意合法角色可读
    except GuardError as exc:                                   # 无权限
        raise _fail(exc)                                        # 转 HTTP
    return ok(MEMORY.stats())                                   # 返回统计
