# -*- coding: utf-8 -*-
"""Agent 接口：冲突检测、口径基线、独立核验与三步串联。"""

from typing import Any, Dict, List                            # 类型标注
from fastapi import APIRouter, Depends, HTTPException          # 路由与依赖
from pydantic import BaseModel, Field                          # 请求体
from app import errors as E                                    # 错误码
from app.agents import a2_conflict, a3_baseline, a5_verify      # 三个 agent
from app.api.envelope import ok                                # 统一响应
from app.deps import ALLOWED_ROLES, KB, ROLE_DEP                # 依赖单例
from app.harness.guards import GuardError, check_permission     # 权限闸门

router = APIRouter(prefix="/v1/agents", tags=["agents"])        # 路由前缀
ANALYST_ROLES = ("engineer", "admin", "safety")                 # 可做分析的岗位


class ClaimIn(BaseModel):                                       # 待核验结论
    text: str = Field(min_length=2, max_length=500)              # 结论文本
    fact_id: str = Field(default="", max_length=8)               # 事实编号


class VerifyIn(BaseModel):                                      # 核验请求
    claims: List[ClaimIn] = Field(default_factory=list)           # 结论列表


def _guard(role: str) -> None:                                   # 分析权限
    """校验分析类接口的权限。

    入参：role 角色。
    出参：无。
    失败行为：无权限时抛 HTTPException(403)。
    """
    try:                                                         # 复用统一闸门
        # 原因：冲突与基线会暴露口径分歧与红线细节，只开放给工程、安全与管理员
        check_permission(role, ALLOWED_ROLES, require_write=False)   # 先过白名单
        if role not in ANALYST_ROLES:                            # 再限岗位
            raise GuardError(E.E_PERM, "该角色不允许执行分析")     # 拒绝
    except GuardError as exc:                                    # 闸门拒绝
        raise HTTPException(status_code=403, detail=exc.msg)      # 转统一结构


@router.post("/conflicts")                                       # 冲突检测
def conflicts(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """对知识库事实做冲突检测。

    入参：role 角色。
    出参：统一三键结构。
    失败行为：知识库为空返回空冲突；无权限 403。
    """
    _guard(role)                                                 # 权限
    result = a2_conflict.detect(KB.facts)                         # 检测
    return ok(result.model_dump())                               # 返回


@router.post("/baseline")                                        # 口径基线
def baseline(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """生成口径基线并自动核验可追溯性。

    入参：role 角色。
    出参：统一三键结构，data 含 rows 与 verify。
    失败行为：无权限 403。
    """
    _guard(role)                                                 # 权限
    output = a3_baseline.build(KB.facts)                          # 构建
    known = {fact.fact_id for fact in KB.facts}                   # 已知编号
    verdict = a5_verify.verify_baseline(output, known)            # 独立核验
    return ok({"baseline": output.model_dump(), "verify": verdict.model_dump()})   # 返回


@router.post("/verify")                                          # 独立核验
def verify(body: VerifyIn, role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """核验一组结论是否带真实事实编号。

    入参：body.claims 结论；role 角色。
    出参：统一三键结构。
    失败行为：无权限 403。
    """
    _guard(role)                                                 # 权限
    known = {fact.fact_id for fact in KB.facts}                   # 已知编号
    verdict = a5_verify.verify_claims([c.model_dump() for c in body.claims], known)   # 核验
    return ok(verdict.model_dump())                               # 返回


@router.post("/pipeline")                                        # 串联
def pipeline(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """一次跑完冲突 → 基线 → 核验。

    入参：role 角色。
    出参：统一三键结构。
    失败行为：无权限 403。
    """
    _guard(role)                                                 # 权限
    conflicts_out = a2_conflict.detect(KB.facts)                  # 冲突
    baseline_out = a3_baseline.build(KB.facts)                    # 基线
    known = {fact.fact_id for fact in KB.facts}                   # 已知编号
    verdict = a5_verify.verify_baseline(baseline_out, known)      # 核验
    return ok({"conflicts": conflicts_out.model_dump(),
               "baseline": baseline_out.model_dump(),
               "verify": verdict.model_dump()})                  # 返回
