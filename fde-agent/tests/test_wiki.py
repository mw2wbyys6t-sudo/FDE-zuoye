# -*- coding: utf-8 -*-
"""Wiki 服务测试：双模式可见性、引用校验、发布签核、版本回滚与审计。"""

from pathlib import Path                                        # 临时目录
import pytest                                                   # 断言与异常
from app.knowledge.ingest import parse_ledger                    # 构造知识库
from app.knowledge.store import KnowledgeStore                   # 存储
from app.wiki.service import WikiError, WikiService              # 服务
from app.wiki.store import WikiStore                             # 存储

SAMPLE = """# 台账
- [logistics-warehouse-f11] 林亦舟：取消订单已进入波次，拣完后仍被装车，配送站到货才发现（物流-005 · 业务事件样本）
- [logistics-warehouse-f40] 傅景：高位叉车、危险品及冷链操作必须遵循现场规程（物流-013 · 访谈事实记录）
- [logistics-warehouse-f00] 顾明岚：错发率 1.8%，目标 0.5%（物流-001 · 访谈事实记录）
"""
ROLES = ["viewer", "operator", "engineer", "safety", "admin"]    # 角色白名单


def _service(tmp_path: Path) -> WikiService:                     # 构造服务
    """创建带样例知识库的 Wiki 服务。

    入参：tmp_path 临时目录。
    出参：WikiService。
    失败行为：无。
    """
    kb = KnowledgeStore(str(tmp_path / "kb"))                     # 知识库
    kb.ingest(parse_ledger(SAMPLE))                               # 灌入三条事实
    return WikiService(WikiStore(str(tmp_path / "wiki.json")), kb, ROLES)   # 组装


def _page(fact_refs=None) -> dict:                               # 构造页面载荷
    """返回最小页面载荷。

    入参：fact_refs 事实编号列表。
    出参：字典。
    失败行为：无。
    """
    return {"slug": "cancel-order-rule", "title": "取消单拦截说明",
            "summary": "取消状态必须在装车前可见", "body": "## 说明\n装车前核对取消状态。",
            "dimension": "rule", "fact_refs": fact_refs or ["f11"]}   # 默认引用取消单事实


def test_create_requires_evidence(tmp_path: Path):                # 引用必须存在
    """验证引用不存在的事实编号会被拒绝。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    with pytest.raises(WikiError):                                # 期望异常
        service.create("engineer", _page(["f99"]))                # 不存在的编号


def test_viewer_cannot_create(tmp_path: Path):                    # 只读角色不能写
    """验证一线角色创建页面被拒。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    with pytest.raises(WikiError):                                # 期望异常
        service.create("viewer", _page())                         # 越权


def test_two_modes_visibility(tmp_path: Path):                    # 双模式
    """验证草稿仅在管理员模式可见，发布后用户模式可见。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    service.create("engineer", _page())                           # 创建草稿
    assert service.list_pages("admin", "admin")                   # 管理员可见
    assert service.list_pages("viewer", "user") == []             # 一线不可见
    service.publish("admin", "cancel-order-rule")                 # 管理员发布
    # 原因：规则维默认对 viewer 不可见，发布后应由 safety/engineer/admin 看到，这是策略而非缺陷
    assert len(service.list_pages("safety", "user")) == 1         # 安全角色可见
    assert service.list_pages("viewer", "user") == []             # 一线仍不可见


def test_publish_requires_admin(tmp_path: Path):                  # 发布签核
    """验证工程角色不能自行发布。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    service.create("engineer", _page())                           # 创建
    with pytest.raises(WikiError):                                # 期望异常
        service.publish("engineer", "cancel-order-rule")          # 越权发布


def test_version_and_rollback(tmp_path: Path):                    # 版本回滚
    """验证更新升版本、回滚恢复旧内容且再升一版。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    service.create("engineer", _page())                           # v1
    updated = service.update("engineer", "cancel-order-rule", {"body": "改过的内容"})   # v2
    assert updated["version"] == 2                                # 版本递增
    restored = service.rollback("admin", "cancel-order-rule", 1)  # 回滚到 v1
    assert "装车前核对取消状态" in restored["body"]                 # 内容恢复
    assert restored["version"] == 3                               # 回滚也升版本


def test_audit_only_admin(tmp_path: Path):                        # 审计权限
    """验证审计记录仅管理员可读。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    service.create("engineer", _page())                           # 产生审计
    with pytest.raises(WikiError):                                # 期望异常
        service.audit("viewer")                                   # 越权
    assert service.audit("admin")                                 # 管理员可读


def test_draft_from_facts(tmp_path: Path):                        # 聚合草稿
    """验证按维度聚合事实生成草稿。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    service = _service(tmp_path)                                  # 服务
    page = service.draft_from_facts("engineer", "rule", limit=5)  # 规则维聚合
    assert page["fact_refs"]                                      # 有引用
    assert page["status"] == "draft"                              # 默认草稿
