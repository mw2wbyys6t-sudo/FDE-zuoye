# -*- coding: utf-8 -*-
"""Wiki 接口：用户模式只读、管理员模式可写。"""

from typing import Any, Dict, List, Optional                  # 类型标注
from fastapi import APIRouter, Depends, HTTPException         # 路由与依赖
from pydantic import BaseModel, Field                          # 请求体
from app.api.envelope import ok                                # 统一响应
from app.deps import ALLOWED_ROLES, ROLE_DEP, WIKI             # 依赖单例
from app.wiki.service import WikiError, WikiMode               # 服务与模式

router = APIRouter(prefix="/v1/wiki", tags=["wiki"])           # 路由前缀


class PageIn(BaseModel):                                       # 创建请求
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{2,48}$")    # 页面标识
    title: str = Field(min_length=2, max_length=80)            # 标题
    summary: str = Field(default="", max_length=300)            # 摘要
    body: str = Field(min_length=1, max_length=20000)           # 正文
    dimension: str = Field(default="fact")                      # 维度
    fact_refs: List[str] = Field(min_length=1)                  # 事实引用
    visibility: Optional[List[str]] = None                      # 可见角色


class PagePatch(BaseModel):                                    # 更新请求
    title: Optional[str] = Field(default=None, max_length=80)   # 标题
    summary: Optional[str] = Field(default=None, max_length=300)   # 摘要
    body: Optional[str] = Field(default=None, max_length=20000)   # 正文
    fact_refs: Optional[List[str]] = None                       # 事实引用
    visibility: Optional[List[str]] = None                      # 可见角色


class DraftIn(BaseModel):                                      # 聚合草稿请求
    dimension: str = Field(default="fact")                      # 维度
    limit: int = Field(default=10, ge=1, le=50)                 # 条数上限


def _fail(exc: WikiError) -> HTTPException:                    # 异常转换
    """把服务异常转成 HTTP 异常，交由统一处理器封装。

    入参：exc 服务异常。
    出参：HTTPException。
    失败行为：无。
    """
    status = 403 if exc.code in ("E_PERM", "E_HUMAN_REQUIRED") else 400   # 权限类给 403
    return HTTPException(status_code=status, detail="%s: %s" % (exc.code, exc.msg))   # 带上错误码


@router.get("/pages")                                          # 列表
def list_pages(mode: str = "user", role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按模式返回页面列表。

    入参：mode user/admin；role 角色。
    出参：统一三键结构。
    失败行为：管理员模式无权限时返回 403。
    """
    try:                                                       # 调用服务
        pages = WIKI.list_pages(role=role, mode=mode)           # 列表
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok({"mode": mode, "pages": pages, "count": len(pages)})   # 返回


@router.get("/pages/{slug}")                                   # 详情
def get_page(slug: str, mode: str = "user", role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按模式读取单个页面。

    入参：slug 标识；mode 模式；role 角色。
    出参：统一三键结构。
    失败行为：不存在或不可见时返回 4xx。
    """
    try:                                                       # 调用服务
        page = WIKI.get_page(slug=slug, role=role, mode=mode)   # 读取
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.post("/pages")                                         # 创建
def create_page(body: PageIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """创建草稿页面，仅工程与管理员。

    入参：body 页面内容；role 角色。
    出参：统一三键结构。
    失败行为：权限不足或引用不存在时返回 4xx。
    """
    try:                                                       # 调用服务
        page = WIKI.create(role, body.model_dump())             # 创建
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.patch("/pages/{slug}")                                 # 更新
def update_page(slug: str, body: PagePatch, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """更新页面并升版本。

    入参：slug 标识；body 变更内容；role 角色。
    出参：统一三键结构。
    失败行为：权限不足或引用非法时返回 4xx。
    """
    payload = {k: v for k, v in body.model_dump().items() if v is not None}   # 忽略未传字段
    try:                                                       # 调用服务
        page = WIKI.update(role, slug, payload)                 # 更新
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.post("/pages/{slug}/publish")                          # 发布
def publish_page(slug: str, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """发布页面，仅管理员。

    入参：slug 标识；role 角色。
    出参：统一三键结构。
    失败行为：非管理员返回 403。
    """
    try:                                                       # 调用服务
        page = WIKI.publish(role, slug)                         # 发布
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.post("/pages/{slug}/rollback/{version}")               # 回滚
def rollback_page(slug: str, version: int, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """回滚到指定版本，仅管理员。

    入参：slug 标识；version 目标版本；role 角色。
    出参：统一三键结构。
    失败行为：非管理员或版本不存在时返回 4xx。
    """
    try:                                                       # 调用服务
        page = WIKI.rollback(role, slug, version)               # 回滚
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.post("/draft-from-facts")                              # 聚合草稿
def draft_from_facts(body: DraftIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按维度聚合事实生成草稿。

    入参：body 维度与条数；role 角色。
    出参：统一三键结构。
    失败行为：权限不足或维度无数据时返回 4xx。
    """
    try:                                                       # 调用服务
        page = WIKI.draft_from_facts(role, body.dimension, body.limit)   # 生成
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok(page)                                            # 返回


@router.get("/audit")                                          # 审计
def audit(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """返回审计记录，仅管理员。

    入参：role 角色。
    出参：统一三键结构。
    失败行为：非管理员返回 403。
    """
    try:                                                       # 调用服务
        entries = WIKI.audit(role)                              # 读取
    except WikiError as exc:                                   # 服务异常
        raise _fail(exc)                                       # 转 HTTP
    return ok({"entries": entries, "count": len(entries), "roles": ALLOWED_ROLES})   # 返回
