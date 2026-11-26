# -*- coding: utf-8 -*-
"""P8 验证脚本：接入格式、回放门禁、来源隔离与接口权限。"""

import subprocess                                            # 跑回放门禁
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from fastapi.testclient import TestClient                     # 接口
from app.execution.importer import load_csv                    # 导入
from app.execution.replay import replay                        # 回放
from app.main import app                                      # 应用

SAMPLE = ROOT / "data" / "sample" / "picking_sample.csv"       # 样例
RESULTS = []                                                  # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def _run(*args: str) -> tuple:                                 # 跑 CLI
    """执行回放脚本并返回退出码与输出。

    入参：args 参数。
    出参：(退出码, 输出)。
    失败行为：不抛异常。
    """
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "replay_csv.py"), *args],
                          capture_output=True, text=True, cwd=str(ROOT))   # 执行
    return proc.returncode, proc.stdout + proc.stderr             # 返回


def main() -> int:                                             # 入口
    """执行 P8 全部验证。

    入参：无。
    出参：0 全通过。
    失败行为：异常向上抛出。
    """
    check("样例文件存在", SAMPLE.exists(), str(SAMPLE.name))       # 文件
    records = load_csv(str(SAMPLE), provenance="synthetic")        # 读取
    report = replay(records)                                       # 回放
    check("样例 12 条且 5 条真错发", len(records) == 12
          and sum(1 for r in records if r.is_error) == 5, "12/5")   # 条数
    check("精确率与召回率可算", report["precision"] == 0.5 and report["recall"] == 0.8,
          "p=%s r=%s" % (report["precision"], report["recall"]))   # 指标
    check("分规则命中可追溯", set(report["by_rule"]) >= {"R1", "R2", "R3", "R4"},
          str(sorted(report["by_rule"])))                          # 分规则

    code_strict, out_strict = _run("--csv", str(SAMPLE))            # 默认门禁
    check("回放门禁拦住低精确率方案", code_strict == 1 and "FAIL" in out_strict,
          "exit=%d" % code_strict)                                # 应失败
    code_loose, out_loose = _run("--csv", str(SAMPLE), "--min-precision", "0.4",
                                 "--min-recall", "0.7")            # 放宽门禁
    check("放宽门禁可通过", code_loose == 0 and "PASS" in out_loose, "exit=%d" % code_loose)   # 应通过
    code_json, _ = _run("--csv", str(SAMPLE), "--json")             # JSON 输出
    check("JSON 输出可用", code_json in (0, 1), "exit=%d" % code_json)   # 可输出

    client = TestClient(app)                                       # 接口
    imported = client.post("/v1/exec/import", json={"path": str(SAMPLE), "provenance": "synthetic"},
                           headers={"X-Role": "engineer"})          # 导入
    check("接口导入返回计数与回放", imported.status_code == 200
          and imported.json()["data"]["imported"] + imported.json()["data"]["skipped"] == 12
          and imported.json()["data"]["replay"]["labeled"] is True, str(imported.status_code))   # 成功（可重复运行）
    syn = client.get("/v1/exec/metrics?provenance=synthetic", headers={"X-Role": "engineer"})   # 合成统计
    real = client.get("/v1/exec/metrics?provenance=real", headers={"X-Role": "engineer"})        # 真实统计
    check("来源隔离生效", syn.json()["data"]["scans"] >= 12 and real.json()["data"]["scans"] == 0,
          "syn=%s real=%s" % (syn.json()["data"]["scans"], real.json()["data"]["scans"]))   # 隔离
    before = syn.json()["data"]["scans"]                          # 记录导入后判定数
    again = client.post("/v1/exec/import", json={"path": str(SAMPLE), "provenance": "synthetic",
                                                 "batch_id": "repeat"}, headers={"X-Role": "engineer"})   # 重复导入
    after = client.get("/v1/exec/metrics?provenance=synthetic", headers={"X-Role": "engineer"})   # 再看
    check("重复导入全部跳过且不放大判定数",
          again.json()["data"]["imported"] == 0 and again.json()["data"]["skipped"] == 12
          and after.json()["data"]["scans"] == before, "skip=%d" % again.json()["data"]["skipped"])   # 去重
    denied = client.post("/v1/exec/import", json={"path": str(SAMPLE)},
                         headers={"X-Role": "viewer"})              # 越权导入
    check("接口：viewer 不能导入", denied.status_code == 403, str(denied.status_code))   # 403

    failed = [name for name, ok in RESULTS if not ok]               # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                                  # 退出码


if __name__ == "__main__":                                         # 直接运行
    sys.exit(main())                                               # 返回退出码
