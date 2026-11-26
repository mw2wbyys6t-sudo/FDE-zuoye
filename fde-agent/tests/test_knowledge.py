# -*- coding: utf-8 -*-
"""知识库测试：解析、切分、索引、检索与持久化。"""

from pathlib import Path                                    # 临时目录
from app.domain.models import Dimension, Fact, Confidence    # 模型
from app.knowledge.ingest import parse_ledger                # 解析
from app.knowledge.retrieve import Retriever                 # 检索
from app.knowledge.store import KnowledgeStore               # 存储
from app.knowledge.chunk import split_text                   # 切分

SAMPLE = """# 台账
- [logistics-warehouse-f11] 林亦舟：取消订单已进入波次，拣完后仍被装车，配送站到货才发现（物流-005 · 业务事件样本）
- [logistics-warehouse-f40] 傅景：高位叉车、危险品及冷链操作必须遵循现场规程（物流-013 · 访谈事实记录）
- [logistics-warehouse-f00] 顾明岚：错发率 1.8%，目标 0.5%；装车复核平均 35 分钟降到 20 分钟（物流-001 · 访谈事实记录）
"""


def test_parse_fields():                                    # 字段解析
    """验证编号、角色、正文与来源被正确拆出。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = parse_ledger(SAMPLE, source="sample.md")         # 解析样例
    assert [f.fact_id for f in facts] == ["f00", "f11", "f40"]   # 按编号排序
    target = [f for f in facts if f.fact_id == "f11"][0]     # 取取消单事实
    assert target.role == "林亦舟"                            # 角色正确
    assert target.source_type == "业务事件样本"               # 来源类型正确
    assert "取消订单" in target.statement                     # 正文完整


def test_dimension_and_confidence():                         # 维度与等级
    """验证规则维与指标维、等级推断。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = {f.fact_id: f for f in parse_ledger(SAMPLE)}     # 编号索引
    assert facts["f40"].dimension == Dimension.RULE           # 规程归规则维
    assert facts["f00"].dimension == Dimension.INDICATOR      # 指标归指标维
    assert facts["f00"].confidence == Confidence.FACT         # 无估计措辞则为事实级


def test_split_keeps_fact_id():                              # 切分不丢编号
    """验证长文本切分后片段仍属于同一事实。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    pieces = split_text("第一句。" + "内容" * 200 + "。")     # 超长文本
    assert len(pieces) >= 2                                   # 至少两段


def test_store_persistence(tmp_path: Path):                  # 持久化
    """验证入库、落盘与重新加载后片段数一致。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = KnowledgeStore(str(tmp_path / "kb"))              # 临时知识库
    store.ingest(parse_ledger(SAMPLE))                        # 入库
    store.save()                                              # 落盘
    reloaded = KnowledgeStore(str(tmp_path / "kb")).load()    # 重新加载
    assert len(reloaded.chunks) == len(store.chunks)          # 片段数一致


def test_retrieval_and_role_filter(tmp_path: Path):           # 检索与权限
    """验证检索命中，且只读角色看不到规则维。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    store = KnowledgeStore(str(tmp_path / "kb2"))             # 临时知识库
    store.ingest(parse_ledger(SAMPLE))                        # 入库
    retriever = Retriever(store)                              # 检索器
    hits = retriever.search("取消订单 装车", role="operator")  # 一线检索
    assert hits and hits[0].fact_id in {"f11"}                # 命中事件
    rules = retriever.search("现场规程", role="viewer", dimension=Dimension.RULE)   # 只读查规则
    assert rules == []                                        # 不可见
    rules_ok = retriever.search("现场规程", role="safety", dimension=Dimension.RULE)   # 安全角色
    assert rules_ok                                              # 可见
