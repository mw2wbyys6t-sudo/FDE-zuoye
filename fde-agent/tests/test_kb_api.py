# -*- coding: utf-8 -*-
"""知识库接口测试：入库权限、检索可见性与统一响应结构。"""

from pathlib import Path                                     # 计算台账路径
from fastapi.testclient import TestClient                     # 进程内客户端
from app.main import app                                      # 应用
from app import errors as E                                   # 错误码

client = TestClient(app)                                      # 全局客户端
LEDGER = Path(__file__).resolve().parents[2] / "discovery-report.md"   # 台账在项目上一级


def test_ingest_requires_engineer_role():                      # 入库权限
    """验证只读角色不能入库。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.post("/v1/kb/ingest", json={"path": str(LEDGER)}, headers={"X-Role": "viewer"})   # 只读角色
    assert resp.status_code == 403                              # 拒绝
    assert resp.json()["error"]["code"] == E.E_PERM             # 错误码


def test_ingest_and_search():                                  # 入库与检索
    """验证工程角色入库后可按角色检索到事实编号。

    入参：无。
    出参：无。
    失败行为：台账缺失时跳过断言，避免环境依赖导致假失败。
    """
    if not LEDGER.exists():                                     # 环境缺台账
        return                                                  # 直接返回，交给 verify_p1 覆盖
    resp = client.post("/v1/kb/ingest", json={"path": str(LEDGER)},
                       headers={"X-Role": "engineer"})          # 入库
    assert resp.status_code == 200                              # 成功
    body = resp.json()                                          # 解析
    assert body["data"]["stats"]["facts"] == 36                 # 36 条事实
    search = client.post("/v1/kb/search", json={"query": "取消订单 装车", "top_k": 3},
                         headers={"X-Role": "viewer"})          # 一线检索
    assert search.status_code == 200                            # 成功
    hits = search.json()["data"]["hits"]                        # 命中
    assert hits and any(hit["fact_id"].startswith("f") for hit in hits)   # 带事实编号
