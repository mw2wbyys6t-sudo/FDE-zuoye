# -*- coding: utf-8 -*-
"""评估入口：跑黄金集，输出 FF1/FF2/FF3 三项指标并给出退出码。"""

import argparse                                              # 参数解析
import sys                                                   # 退出码
from pathlib import Path                                     # 路径
import yaml                                                  # 读取用例

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from app.agents.a1_evidence import extract                     # A1
from app.harness.guards import GuardError                      # 闸门异常
from app.harness.runner import Runner, RunnerError             # 执行器
from app.harness.trace import TraceWriter                      # 追踪
from app.knowledge.ingest import parse_ledger_file              # 台账
from app.model.fake import FakeClient                           # 假模型

EVAL_DIR = ROOT / "evals" / "cases"                            # 用例目录
TRACE = TraceWriter(str(ROOT / "var" / "trace-eval"))          # 评估专用追踪


def _known_ids() -> set:                                       # 已知编号
    """从真实台账提取事实编号集合。

    入参：无。
    出参：编号集合。
    失败行为：台账缺失时返回空集合，用例会被全部拒绝。
    """
    candidates = [ROOT.parent / "discovery-report.md",
                  ROOT.parent / "docs" / "discovery-report.md"]   # 两种布局
    source = next((p for p in candidates if p.exists()), None)   # 取存在的
    if source is None:                                         # 都没有
        return set()                                           # 空集合
    return {fact.fact_id for fact in parse_ledger_file(str(source))}   # 解析


def _run_case(case: dict, known: set) -> dict:                  # 跑单条
    """执行一条用例并返回结果。

    入参：case 用例字典；known 已知编号。
    出参：{"id","status","code"}。
    失败行为：不抛异常，所有失败都转成状态。
    """
    runner = Runner(FakeClient([case["model_output"]]), TRACE, max_retry=0)   # 单次尝试，暴露真实表现
    try:                                                       # 执行
        result = extract(runner, case["text"], sorted(known))   # 抽取
        claims = result["data"]["claims"]                       # 结论
        bad = [c for c in claims if c["fact_id"] not in known]   # 校验编号真实存在
        return {"id": case["id"], "status": "accepted",
                "code": "" if not bad else "E_NO_EVIDENCE", "claims": claims}   # 接受
    except GuardError as exc:                                  # 闸门拦截
        return {"id": case["id"], "status": "rejected", "code": exc.code, "claims": []}   # 拒绝
    except RunnerError as exc:                                 # 契约失败
        return {"id": case["id"], "status": "rejected", "code": exc.code, "claims": []}   # 拒绝


def main() -> int:                                             # 入口
    """执行评估套件。

    入参：--suite evidence|no_evidence|all。
    出参：0 达标，1 不达标。
    失败行为：用例文件缺失时返回 2。
    """
    parser = argparse.ArgumentParser(description="黄金集评估")   # 参数
    parser.add_argument("--suite", default="all")               # 套件
    args = parser.parse_args()                                  # 解析
    files = {"evidence": ["evidence.yaml"], "no_evidence": ["no_evidence.yaml"],
             "all": ["evidence.yaml", "no_evidence.yaml"]}[args.suite]   # 选择文件
    known = _known_ids()                                        # 已知编号
    results = []                                                # 收集
    for name in files:                                          # 逐文件
        path = EVAL_DIR / name                                  # 路径
        if not path.exists():                                   # 缺失
            print("用例文件缺失：%s" % path)                      # 提示
            return 2                                            # 非零
        for case in yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]:   # 逐用例
            results.append((_run_case(case, known), case))       # 执行
    accepted = [r for r, _ in results if r["status"] == "accepted"]   # 接受数
    rejected = [r for r, _ in results if r["status"] == "rejected"]   # 拒绝数
    claims = [c for r in accepted for c in r["claims"]]          # 全部结论
    evidence_ok = sum(1 for c in claims if c["fact_id"] in known)   # 证据合法数
    negatives = [r for r, case in results if case["expect"] == "rejected"]   # 负例
    negative_hit = sum(1 for r in negatives if r["status"] == "rejected")   # 正确拒绝数
    ff1 = 1.0 if not claims else evidence_ok / len(claims)       # 证据可追溯率
    ff2 = 1.0 if not negatives else negative_hit / len(negatives)   # 负例拒答率
    ff3 = 1.0 if not results else len([r for r, _ in results if r["status"] in ("accepted", "rejected")]) / len(results)   # 结构可用率
    for result, case in results:                                # 明细
        ok = (result["status"] == case["expect"]) and (not case.get("code") or result["code"] == case["code"])   # 判定
        print("%s %-18s status=%s code=%s" % ("PASS" if ok else "FAIL", result["id"], result["status"], result["code"]))   # 打印
    print("\nFF1 证据可追溯率 %.3f（要求 1.000）" % ff1)           # 指标
    print("FF2 负例拒答率 %.3f（要求 ≥0.950）" % ff2)              # 指标
    print("FF3 用例结构可用率 %.3f（要求 1.000）" % ff3)            # 指标
    passed = ff1 >= 1.0 and ff2 >= 0.95 and ff3 >= 1.0          # 门禁
    return 0 if passed else 1                                   # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
