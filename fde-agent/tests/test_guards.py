# -*- coding: utf-8 -*-
"""闸门测试：证据、边界、权限三条硬线必须可拦截。"""

import pytest                                                  # 断言与异常
from app import errors as E                                    # 错误码
from app.harness.guards import (GuardError, check_evidence,
                                check_boundary, check_permission)   # 被测函数


def test_evidence_missing_fact_id():                           # 缺编号必须拦截
    """验证缺少事实编号时抛 E_NO_EVIDENCE。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError) as info:                     # 期望异常
        check_evidence([{"text": "拣选是主因", "fact_id": ""}])   # 空编号
    assert info.value.code == E.E_NO_EVIDENCE                   # 错误码正确


def test_evidence_unknown_fact_id():                           # 编造编号必须拦截
    """验证事实编号不在台账时抛 E_NO_EVIDENCE。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError):                             # 期望异常
        check_evidence([{"text": "某个结论", "fact_id": "f99"}], known_ids={"f11", "f31"})   # f99 不存在


def test_boundary_blocks_write():                              # 写库必须拦截
    """验证写业务库动作被边界闸门拒绝。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError) as info:                     # 期望异常
        check_boundary("write_db")                              # 越界动作
    assert info.value.code == E.E_BOUNDARY                      # 错误码正确


def test_boundary_blocks_auto_approval_text():                 # 自动审批意图必须拦截
    """验证载荷中出现自动审批意图时被拒绝。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError):                             # 期望异常
        check_boundary(None, {"note": "命中后自动审批"})          # 文本意图


def test_permission_denies_unknown_role():                     # 未知角色拒绝
    """验证非白名单角色被拒绝。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError) as info:                     # 期望异常
        check_permission("guest", ["viewer", "operator"])        # guest 不在白名单
    assert info.value.code == E.E_PERM                          # 错误码正确


def test_permission_write_requires_role():                     # 写权限仅限授权角色
    """验证只读角色不能执行写操作。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(GuardError):                             # 期望异常
        check_permission("viewer", ["viewer", "admin"], require_write=True, write_roles=["admin"])   # 只读角色请求写
