# -*- coding: utf-8 -*-
"""记忆层测试：分层策略、冲突检测、角色过滤与过期清理。"""

from datetime import datetime, timedelta, timezone             # 构造过期时间
from pathlib import Path                                        # 临时目录
import pytest                                                   # 断言与异常
from app.memory.models import MemoryLayer                       # 层枚举
from app.memory.policy import MemoryPolicyError                 # 策略异常
from app.memory.store import LocalMemoryStore                   # 存储


def _store(tmp_path: Path) -> LocalMemoryStore:                 # 构造临时存储
    """创建临时记忆库。

    入参：tmp_path 临时目录。
    出参：LocalMemoryStore。
    失败行为：无。
    """
    return LocalMemoryStore(str(tmp_path / "mem"), ttl_days=90)   # 90 天保留


def test_semantic_requires_evidence(tmp_path: Path):             # 语义层必须有证据
    """验证未核验或无事实编号时禁止写入语义层。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = _store(tmp_path)                                     # 临时库
    with pytest.raises(MemoryPolicyError):                       # 缺证据
        store.write(MemoryLayer.SEMANTIC, "拣选是主因", [], "engineer", verified=True)   # 无引用
    with pytest.raises(MemoryPolicyError):                       # 未核验
        store.write(MemoryLayer.SEMANTIC, "错发率 1.8%", ["f00"], "engineer", verified=False)   # 未核验


def test_semantic_write_and_conflict(tmp_path: Path):            # 写入与冲突
    """验证同证据不同结论会标记冲突且两条并存。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = _store(tmp_path)                                     # 临时库
    first = store.write(MemoryLayer.SEMANTIC, "错发主因在拣选", ["f10"], "engineer", verified=True)   # 第一条
    assert first["conflict"] is False                            # 无冲突
    second = store.write(MemoryLayer.SEMANTIC, "错发主因在装车", ["f10"], "engineer", verified=True)   # 同证据不同结论
    assert second["conflict"] is True                            # 标记冲突
    assert store.stats()["conflicts"] == 1                       # 冲突计数


def test_dedup(tmp_path: Path):                                  # 去重
    """验证同层同文重复写入不会产生第二条。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = _store(tmp_path)                                     # 临时库
    store.write(MemoryLayer.WORKING, "本轮已用 f11", [], "operator")   # 首次
    again = store.write(MemoryLayer.WORKING, "本轮已用 f11", [], "operator")   # 重复
    assert again["dedup"] is True                                # 命中去重
    assert store.stats()["total"] == 1                           # 只有一条


def test_role_filter(tmp_path: Path):                           # 角色过滤
    """验证不可见角色检索不到记忆。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = _store(tmp_path)                                     # 临时库
    store.write(MemoryLayer.PROCEDURAL, "审批矩阵未核实", [], "safety", visibility=["safety", "admin"])   # 仅安全与管理员可见
    assert store.search("审批矩阵", role="viewer") == []          # 一线不可见
    assert store.search("审批矩阵", role="safety")               # 安全可见


def test_prune_expired(tmp_path: Path):                         # 过期清理
    """验证过期记忆被清理。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = _store(tmp_path)                                     # 临时库
    store.write(MemoryLayer.WORKING, "临时草稿", [], "operator")   # 写入一条
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()   # 昨天
    store.items[0] = store.items[0].model_copy(update={"expires_at": past})   # 改成已过期
    assert store.prune() == 1                                    # 清理一条
    assert store.stats()["total"] == 0                           # 库为空
