# -*- coding: utf-8 -*-
"""任务接口：创建、执行、查看、签核，全部走统一响应与角色闸门。"""

from typing import Any, Dict, List, Optional                  # 类型标注
from fastapi import APIRouter, Depends, HTTPException          # 路由与依赖
from pydantic import BaseModel, Field                          # 请求体
from app.api.envelope import ok                                # 统一响应
from app import errors as E                                    # 错误码
from app.deps import ALLOWED_ROLES, ORCH, ROLE_DEP              # 依赖单例
from app.harness.guards import GuardError, check_permission     # 权限闸门
from app.orchestrator.engine import OrchestratorError           # 编排异常

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])          # 路由前缀
CREATE_ROLES = ("engineer", "admin")                            # 可创建任务的角色


class RunIn(BaseModel):                                         # 执行请求
    steps: Optional[List[str]] = None                            # 指定步骤，缺省全部


class DecideIn(BaseModel):                                      # 签核请求
    decision: str = Field(pattern=r"^(approve|reject)$")          # 批准或驳回
    note: str = Field(default="", max_length=200)                 # 说明


def _fail(exc: Exception) -> HTTPException:                      # 异常转换
    """把编排或权限异常转成 HTTP 异常。

    入参：exc 异常。
    出参：HTTPException。
    失败行为：无。
    """
    code = getattr(exc, "code", E.E_INTERNAL)                    # 取错误码
    status = 403 if code in (E.E_PERM, E.E_HUMAN_REQUIRED) else 400   # 权限类 403
    return HTTPException(status_code=status, detail="%s: %s" % (code, str(exc)))   # 带上错误码


@router.post("")                                                # 创建
def create_task(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """创建编排任务。

    入参：role 角色。
    出参：统一三键结构。
    失败行为：无权限 403。
    """
    try:                                                        # 权限
        check_permission(role, ALLOWED_ROLES, require_write=True, write_roles=CREATE_ROLES)   # 写权限
    except GuardError as exc:                                   # 拒绝
        raise _fail(exc)                                        # 转 HTTP
    return ok(ORCH.create(role))                                # 返回任务


@router.get("/{task_id}")                                       # 查看
def get_task(task_id: str, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """读取任务状态与产物。

    入参：task_id 编号；role 角色。
    出参：统一三键结构。
    失败行为：任务不存在 400。
    """
    try:                                                        # 权限
        check_permission(role, ALLOWED_ROLES)                   # 任意合法角色可读
        return ok(ORCH.get(task_id))                            # 返回
    except OrchestratorError as exc:                            # 不存在
        raise _fail(exc)                                        # 转 HTTP
    except GuardError as exc:                                   # 无权限
        raise _fail(exc)                                        # 转 HTTP


@router.post("/{task_id}/run")                                  # 执行
def run_task(task_id: str, body: RunIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """按步执行任务，已完成步骤自动复用。

    入参：task_id 编号；body.steps 步骤；role 角色。
    出参：统一三键结构。
    失败行为：无权限或步骤非法 4xx。
    """
    try:                                                        # 权限
        check_permission(role, ALLOWED_ROLES, require_write=True, write_roles=CREATE_ROLES)   # 写权限
        record = ORCH.run(task_id, body.steps)                  # 执行
    except (OrchestratorError, GuardError) as exc:              # 异常
        raise _fail(exc)                                        # 转 HTTP
    return ok(record)                                           # 返回


@router.post("/{task_id}/gate/decide")                          # 签核
def decide_gate(task_id: str, body: DecideIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """处理人工闸门，仅安全或管理员可签核。

    入参：task_id 编号；body 决定与说明；role 角色。
    出参：统一三键结构。
    失败行为：无权限或无待签核项 4xx。
    """
    try:                                                        # 权限
        check_permission(role, ALLOWED_ROLES)                   # 白名单
        record = ORCH.decide(task_id, role, body.decision, body.note)   # 签核
    except (OrchestratorError, GuardError) as exc:              # 异常
        raise _fail(exc)                                        # 转 HTTP
    return ok(record)                                           # 返回
