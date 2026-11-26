# -*- coding: utf-8 -*-
"""P2 验证脚本：记忆分层策略、Wiki 双模式、版本回滚、审计与接口权限。"""

import shutil                                                # 清理临时目录
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from fastapi.testclient import TestClient                     # 接口冒烟
from app.knowledge.ingest import parse_ledger_file             # 台账解析
from app.knowledge.store import KnowledgeStore                 # 知识库
from app.main import app                                       # 应用
from app.memory.models import MemoryLayer                      # 层枚举
from app.memory.policy import MemoryPolicyError                # 策略异常
from app.memory.store import LocalMemoryStore                  # 记忆存储
from app.wiki.service import WikiError, WikiService            # Wiki 服务
from app.wiki.store import WikiStore                           # Wiki 存储

SOURCE_CANDIDATES = [ROOT.parent / "discovery-report.md",
                     ROOT.parent / "docs" / "discovery-report.md"]   # 台账候选位置
SOURCE = next((p for p in SOURCE_CANDIDATES if p.exists()), SOURCE_CANDIDATES[0])   # 取存在的
WORK = ROOT / "var" / "p2-verify"                             # 验证目录
ROLES = ["viewer", "operator", "engineer", "safety", "admin"]   # 角色
RESULTS = []                                                  # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印一条检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                    # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def expect_error(fn, code: str, name: str) -> None:            # 期望异常
    """断言某操作抛出指定错误码。

    入参：fn 可调用；code 期望错误码；name 检查名。
    出参：无。
    失败行为：未抛或码不符则记为失败。
    """
    try:                                                       # 执行
        fn()                                                   # 调用
        check(name, False, "未抛异常")                          # 失败
    except (WikiError, MemoryPolicyError) as exc:              # 预期异常
        check(name, exc.code == code, exc.code)                # 校验错误码


def main() -> int:                                             # 入口
    """执行 P2 全部验证。

    入参：无。
    出参：0 全通过，1 有失败，2 缺台账。
    失败行为：异常向上抛出。
    """
    if not SOURCE.exists():                                    # 台账缺失
        print("台账不存在：%s" % SOURCE)                        # 提示
        return 2                                               # 退出
    shutil.rmtree(WORK, ignore_errors=True)                    # 清理旧数据
    facts = parse_ledger_file(str(SOURCE))                     # 解析 36 条事实
    kb = KnowledgeStore(str(WORK / "kb"))                      # 知识库
    kb.ingest(facts)                                           # 入库

    mem = LocalMemoryStore(str(WORK / "mem"), ttl_days=90)      # 记忆库
    expect_error(lambda: mem.write(MemoryLayer.SEMANTIC, "拣选是主因", [], "engineer", verified=True),
                 "E_NO_EVIDENCE", "语义记忆必须有事实编号")     # 无证据拦截
    first = mem.write(MemoryLayer.SEMANTIC, "错发主因在拣选", ["f10"], "engineer", verified=True)   # 合法写入
    check("语义记忆写入成功", first["conflict"] is False, str(first))   # 成功
    second = mem.write(MemoryLayer.SEMANTIC, "错发主因在装车", ["f10"], "engineer", verified=True)   # 同证据不同结论
    check("冲突被标记且并存", second["conflict"] is True and mem.stats()["total"] == 2, str(mem.stats()))   # 冲突
    mem.write(MemoryLayer.PROCEDURAL, "审批矩阵未核实", [], "safety", visibility=["safety", "admin"])   # 受限可见
    check("记忆角色过滤", mem.search("审批矩阵", role="viewer") == []
          and bool(mem.search("审批矩阵", role="safety")), "viewer/safety")   # 可见性
    sample = mem.items[0]                                      # 取一条
    from datetime import datetime                               # 局部导入避免顶部噪音
    ttl_days = (datetime.fromisoformat(sample.expires_at) - datetime.fromisoformat(sample.created_at)).days   # 有效期
    check("有效期约 90 天", 89 <= ttl_days <= 90, str(ttl_days))   # TTL

    wiki = WikiService(WikiStore(str(WORK / "wiki.json")), kb, ROLES)   # Wiki 服务
    payload = {"slug": "cancel-order-rule", "title": "取消单拦截说明",
               "body": "装车前核对取消状态。", "dimension": "rule", "fact_refs": ["f11"]}   # 页面载荷
    expect_error(lambda: wiki.create("engineer", dict(payload, fact_refs=["f99"])),
                 "E_NO_EVIDENCE", "引用不存在被拒绝")           # 引用校验
    expect_error(lambda: wiki.create("viewer", payload), "E_PERM", "viewer 不能创建")   # 权限
    page = wiki.create("engineer", payload)                    # 创建草稿
    check("草稿版本为 1", page["version"] == 1, str(page["version"]))   # 版本
    check("用户模式看不到草稿", wiki.list_pages("viewer", "user") == [], "draft")   # 双模式
    expect_error(lambda: wiki.publish("engineer", "cancel-order-rule"),
                 "E_HUMAN_REQUIRED", "工程角色不能自行发布")   # 签核
    published = wiki.publish("admin", "cancel-order-rule")     # 管理员发布
    check("发布升版本", published["version"] == 2, str(published["version"]))   # 版本
    check("用户模式可见（safety）", len(wiki.list_pages("safety", "user")) == 1, "published")   # 可见

    updated = wiki.update("engineer", "cancel-order-rule", {"body": "改过的正文"})   # 更新
    restored = wiki.rollback("admin", "cancel-order-rule", 1)   # 回滚 v1
    check("回滚恢复旧正文且升版本", "装车前核对取消状态" in restored["body"] and restored["version"] == 4,
          "v%d" % restored["version"])                         # 回滚
    expect_error(lambda: wiki.audit("viewer"), "E_PERM", "审计仅管理员")   # 审计权限
    check("审计条目齐全", len(wiki.audit("admin")) >= 4, str(len(wiki.audit("admin"))))   # 审计数量

    draft = wiki.draft_from_facts("engineer", "rule", limit=5)   # 聚合草稿
    check("事实聚合草稿有引用", bool(draft["fact_refs"]), str(draft["fact_refs"][:3]))   # 聚合

    client = TestClient(app)                                   # 接口冒烟
    deny = client.get("/v1/wiki/pages?mode=admin", headers={"X-Role": "viewer"})   # 越权
    check("接口：viewer 访问管理员模式被拒", deny.status_code == 403
          and set(deny.json().keys()) == {"ok", "data", "error"}, str(deny.status_code))   # 403 + 三键
    stats = client.get("/v1/memory/stats", headers={"X-Role": "operator"})   # 统计
    check("接口：记忆统计可用", stats.status_code == 200 and stats.json()["ok"] is True,
          str(stats.status_code))                              # 200

    failed = [name for name, ok in RESULTS if not ok]           # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
