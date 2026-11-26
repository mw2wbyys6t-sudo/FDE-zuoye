# -*- coding: utf-8 -*-
"""执行层接口：扫码判定、处置闭环、指标与事件流。"""

from typing import Any, Dict                                   # 类型标注
from fastapi import APIRouter, Depends, HTTPException, Query    # 路由
from pydantic import BaseModel, Field                           # 请求体包装
from app import errors as E                                     # 错误码
from app.api.envelope import ok                                 # 统一响应
from app.deps import ALLOWED_ROLES, EXEC, ROLE_DEP               # 依赖
from app.execution.models import DispositionIn, ScanContext      # 契约
from app.execution.importer import ImportError_, load_csv        # 导入
from app.execution.replay import replay                          # 回放
from app.execution.service import ExecutionError                 # 业务异常
from app.harness.guards import GuardError, check_permission      # 权限闸门

router = APIRouter(prefix="/v1/exec", tags=["execution"])        # 路由前缀
SCAN_ROLES = ("operator", "engineer", "admin")                    # 可扫码角色
VIEW_ROLES = ("engineer", "safety", "admin")                      # 可看指标角色


class ScanIn(BaseModel):                                         # 扫码请求
    ctx: ScanContext = Field(...)                                 # 上下文


class ImportIn(BaseModel):                                       # 导入请求
    path: str = Field(min_length=3, max_length=400)               # 导出文件路径
    provenance: str = Field(default="real", pattern=r"^(real|synthetic)$")   # 来源标记
    batch_id: str = Field(default="", max_length=40)              # 批次号，留空自动生成


def _guard(role: str, roles) -> None:                            # 权限
    """校验角色并转成 HTTP 异常。

    入参：role 角色；roles 允许集合。
    出参：无。
    失败行为：无权限时抛 HTTPException(403)。
    """
    try:                                                          # 复用统一闸门
        check_permission(role, ALLOWED_ROLES)                     # 白名单
        if role not in roles:                                     # 岗位限制
            raise GuardError(E.E_PERM, "该角色不允许此操作")        # 拒绝
    except GuardError as exc:                                     # 拦截
        raise HTTPException(status_code=403, detail=exc.msg)      # 转 HTTP


@router.post("/scan")                                             # 扫码判定
def scan(body: ScanIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """对一次扫码执行规则判定。

    入参：body.ctx 上下文；role 角色。
    出参：统一三键结构，data 为判定。
    失败行为：无权限 403。
    """
    _guard(role, SCAN_ROLES)                                      # 权限
    return ok(EXEC.scan(body.ctx).model_dump())                   # 判定


@router.post("/dispositions")                                     # 处置
def dispose(body: DispositionIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """记录处置并校验挂起单三要素。

    入参：body 处置请求；role 角色。
    出参：统一三键结构。
    失败行为：无权限 403；挂起单缺三要素 400。
    """
    _guard(role, SCAN_ROLES + ("safety",))                        # 权限
    try:                                                          # 业务校验
        return ok(EXEC.dispose(body).model_dump())                # 处置
    except ExecutionError as exc:                                 # 业务异常
        code = 403 if exc.code == E.E_HUMAN_REQUIRED else 400     # 人审类 403
        raise HTTPException(status_code=code, detail=exc.msg)     # 转 HTTP


@router.get("/metrics")                                           # 指标
def metrics(provenance: str = Query(default="", pattern=r"^(|real|synthetic)$"),
            role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """返回判定与处置统计。

    入参：provenance 空表示全部，real/synthetic 用于隔离验收；role 角色。
    出参：统一三键结构。
    失败行为：无权限 403。
    """
    _guard(role, VIEW_ROLES)                                      # 权限
    return ok(EXEC.metrics(provenance or None))                   # 统计


@router.post("/import")                                           # 导入历史数据
def import_records(body: ImportIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """导入现场导出文件并立即给出回放指标。

    入参：body.path 文件；body.provenance 来源；role 角色。
    出参：统一三键结构，data 含 imported 与 replay。
    失败行为：无权限 403；格式错误 400。
    """
    _guard(role, ("engineer", "admin"))                            # 仅工程与管理员
    try:                                                          # 读取
        records = load_csv(body.path, provenance=body.provenance)   # 导入
    except ImportError_ as exc:                                   # 格式问题
        raise HTTPException(status_code=400, detail=exc.msg)      # 转 HTTP
    imported = EXEC.ingest(records, provenance=body.provenance, batch_id=body.batch_id)   # 落事件（自动去重）
    return ok({"imported": imported["imported"], "skipped": imported["skipped"],
               "replay": replay(records)})                        # 返回计数与回放指标


@router.get("/events")                                            # 事件流
def events(limit: int = Query(default=20, ge=1, le=200), role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """返回最近事件，供排查与回放。

    入参：limit 条数；role 角色。
    出参：统一三键结构。
    失败行为：无权限 403。
    """
    _guard(role, VIEW_ROLES)                                      # 权限
    return ok({"items": EXEC.events()[-limit:]})                  # 截取尾部
