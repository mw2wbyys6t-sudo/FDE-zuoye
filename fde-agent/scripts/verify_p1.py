# -*- coding: utf-8 -*-
"""P1 验证脚本：台账解析、四维分布、持久化往返、检索质量与角色过滤。"""

import shutil                                                # 清理临时目录
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from app.domain.models import Dimension                       # 维度
from app.knowledge.ingest import parse_ledger_file             # 解析
from app.knowledge.retrieve import Retriever                   # 检索
from app.knowledge.store import KnowledgeStore                 # 存储

SOURCE_CANDIDATES = [                                          # 台账候选位置，兼容两种目录布局
    ROOT.parent / "discovery-report.md",                       # 与项目同级
    ROOT.parent / "docs" / "discovery-report.md",              # 放在 docs/ 子目录
]
SOURCE = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])   # 取存在的那份
STORE_DIR = ROOT / "var" / "kb-verify"                         # 验证专用目录
RESULTS = []                                                   # 结果收集

QUERIES = [                                                    # 检索用例与期望编号
    ("取消订单 延迟 12 分钟", {"f11", "f31"}),                  # 取消单事件链
    ("错发率 1.8% 目标 0.5%", {"f00"}),                        # 指标目标
    ("复核漏扫 为零", {"f02", "f42"}),                          # 验收硬线
    ("主编号 编码 不一致", {"f30", "f31", "f33"}),              # 数据治理
    ("交接 业务编号 接手人", {"f23"}),                          # 交接五要素
]


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录检查
    """记录单条结果并打印。

    入参：name 检查名；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                    # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def main() -> int:                                             # 入口
    """执行 P1 全部验证项。

    入参：无。
    出参：0 全通过，1 存在失败。
    失败行为：源文件缺失时直接返回 2。
    """
    if not SOURCE.exists():                                    # 台账必须存在
        print("台账不存在：%s" % SOURCE)                        # 提示
        return 2                                               # 非零退出
    facts = parse_ledger_file(str(SOURCE))                     # 解析台账
    check("解析出 36 条事实", len(facts) == 36, str(len(facts)))   # 数量
    check("编号唯一", len({f.fact_id for f in facts}) == len(facts), "唯一性")   # 唯一
    check("全部带来源", all(f.source for f in facts), "source")   # 来源齐全

    shutil.rmtree(STORE_DIR, ignore_errors=True)               # 清理旧数据，保证可复现
    store = KnowledgeStore(str(STORE_DIR))                     # 新建存储
    result = store.ingest(facts)                               # 入库
    dims = store.stats()["dimensions"]                         # 维度分布
    check("四维均有数据", all(dims.get(d.value, 0) > 0 for d in Dimension), str(dims))   # 覆盖四维

    store.save()                                               # 落盘
    reloaded = KnowledgeStore(str(STORE_DIR)).load()           # 重新加载
    check("持久化往返一致", len(reloaded.chunks) == len(store.chunks), str(len(reloaded.chunks)))   # 往返

    retriever = Retriever(reloaded)                            # 检索器
    for query, expected in QUERIES:                            # 逐个查询
        hits = retriever.search(query, role="engineer", top_k=5)   # 检索
        ids = {hit.fact_id for hit in hits}                    # 命中编号
        check("检索：%s" % query, bool(ids & expected), "命中=%s" % sorted(ids))   # 命中交集

    viewer_rules = retriever.search("签核 审批", role="viewer",
                                    dimension=Dimension.RULE, top_k=5)   # 只读角色查规则维
    check("viewer 不可见规则维", len(viewer_rules) == 0, str(len(viewer_rules)))   # 权限过滤
    safety_rules = retriever.search("签核 审批", role="safety",
                                    dimension=Dimension.RULE, top_k=5)   # 安全角色查规则维
    check("safety 可见规则维", len(safety_rules) > 0, str(len(safety_rules)))   # 权限放行

    failed = [name for name, ok in RESULTS if not ok]          # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
