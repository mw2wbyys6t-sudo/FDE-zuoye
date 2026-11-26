# -*- coding: utf-8 -*-
"""P3 验证脚本：冲突检测、基线缺项、独立核验、评估门禁与接口权限。"""

import subprocess                                            # 跑评估门禁
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from fastapi.testclient import TestClient                     # 接口测试
from app.agents import a2_conflict, a3_baseline, a5_verify      # agent
from app.knowledge.ingest import parse_ledger_file              # 台账
from app.main import app                                       # 应用

SOURCE_CANDIDATES = [ROOT.parent / "discovery-report.md",
                     ROOT.parent / "docs" / "discovery-report.md"]   # 两种布局
SOURCE = next((p for p in SOURCE_CANDIDATES if p.exists()), SOURCE_CANDIDATES[0])   # 取存在的
RESULTS = []                                                   # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def main() -> int:                                             # 入口
    """执行 P3 全部验证。

    入参：无。
    出参：0 全通过，1 有失败，2 缺台账。
    失败行为：异常向上抛出。
    """
    if not SOURCE.exists():                                    # 台账缺失
        print("台账不存在：%s" % SOURCE)                        # 提示
        return 2                                               # 退出
    facts = parse_ledger_file(str(SOURCE))                     # 36 条事实
    known = {fact.fact_id for fact in facts}                   # 编号集合

    conflicts = a2_conflict.detect(facts)                      # 冲突检测
    kinds = {item.kind for item in conflicts.conflicts}         # 类型集合
    check("冲突检测有输出", len(conflicts.conflicts) >= 1, str(len(conflicts.conflicts)))   # 数量
    check("识别完成口径冲突", "definition" in kinds, str(sorted(kinds)))   # 口径
    # 说明：36 条事实中未出现"阻断"字样，scope 规则只在合成用例中覆盖，这里不硬凑
    refs_ok = all(fid in known for item in conflicts.conflicts for fid in item.fact_refs)   # 引用真实
    check("冲突引用均为真实编号", refs_ok, "refs")               # 引用校验

    baseline = a3_baseline.build(facts)                        # 基线
    check("基线覆盖五个指标", len(baseline.rows) == 5, str(len(baseline.rows)))   # 行数
    check("责任人缺省为 TBD", all(row.owner == "TBD" for row in baseline.rows), "owner")   # 缺项
    check("存在待定字段", baseline.tbd_count > 0, str(baseline.tbd_count))   # TBD 计数
    error_rate = [row for row in baseline.rows if row.indicator == "错发率"][0]   # 错发率行
    check("错发率行带证据", bool(error_rate.evidence), str(error_rate.evidence[:3]))   # 证据

    verdict = a5_verify.verify_baseline(baseline, known)        # 核验基线
    check("基线核验结构通过", verdict.passed is True, str(verdict.passed))   # 通过
    check("估计值被标注需确认", any("估计值" in item.reason for item in verdict.items), "estimate")   # 等级提示
    bad = a5_verify.verify_claims([{"text": "编造", "fact_id": "f99"}], known)   # 假编号
    check("编造编号不通过核验", bad.passed is False, str(bad.passed))   # 拒绝

    eval_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "eval_run.py"), "--suite", "all"],
                               capture_output=True, text=True, cwd=str(ROOT))   # 跑评估门禁
    check("评估门禁通过", eval_proc.returncode == 0, "exit=%d" % eval_proc.returncode)   # 退出码

    client = TestClient(app)                                   # 接口
    ingest = client.post("/v1/kb/ingest", json={"path": str(SOURCE)}, headers={"X-Role": "engineer"})   # 先入库
    check("接口入库成功", ingest.status_code == 200 and ingest.json()["ok"], str(ingest.status_code))   # 入库
    pipeline = client.post("/v1/agents/pipeline", headers={"X-Role": "engineer"})   # 串联
    check("接口串联返回三块", pipeline.status_code == 200 and set(pipeline.json()["data"].keys()) ==
          {"conflicts", "baseline", "verify"}, str(pipeline.status_code))   # 结构
    deny = client.post("/v1/agents/pipeline", headers={"X-Role": "viewer"})   # 越权
    check("一线角色不能跑分析", deny.status_code == 403
          and deny.json()["error"]["code"] == "E_PERM", str(deny.status_code))   # 403

    failed = [name for name, ok in RESULTS if not ok]           # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
