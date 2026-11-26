# -*- coding: utf-8 -*-
"""接口测试：所有响应必须是三键结构，403 也必须被封装。"""

from fastapi.testclient import TestClient                       # 进程内测试客户端
from app.main import app                                        # 被测应用
from app import errors as E                                     # 错误码

client = TestClient(app)                                        # 全局客户端


def test_health_envelope():                                     # 健康检查结构
    """验证 /v1/health 返回三键结构。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.get("/v1/health")                             # 发起请求
    assert resp.status_code == 200                              # 状态码
    body = resp.json()                                          # 解析
    assert set(body.keys()) == {"ok", "data", "error"}          # 只允许三键
    assert body["ok"] is True                                   # 成功标记


def test_selftest_envelope_and_cases():                          # 自测接口
    """验证自测接口返回三个用例且预期结果成立。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.post("/v1/harness/selftest", headers={"X-Role": "engineer"})   # 带合法角色
    assert resp.status_code == 200                              # 状态码
    body = resp.json()                                          # 解析
    cases = {c["name"]: c for c in body["data"]["cases"]}        # 按名字索引
    assert cases["valid"]["ok"] is True                          # 正常路径通过
    assert cases["retry"]["detail"]["attempts"] == 2             # 重试一次后成功
    assert cases["no_evidence"]["detail"]["code"] == E.E_NO_EVIDENCE   # 无证据被拦截


def test_missing_role_returns_envelope():                        # 缺角色
    """验证缺少 X-Role 时返回 403 且仍是三键结构。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.post("/v1/harness/selftest")                   # 不带角色
    assert resp.status_code == 403                              # 状态码
    body = resp.json()                                          # 解析
    assert body["ok"] is False                                  # 失败标记
    assert body["error"]["code"] == E.E_PERM                     # 错误码
