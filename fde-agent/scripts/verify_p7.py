# -*- coding: utf-8 -*-
"""P7 验证脚本：执行层四规则、三要素闭环、指标与接口权限。"""

import shutil                                                # 清理
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from fastapi.testclient import TestClient                     # 接口
from app.main import app                                      # 应用
from app.execution.models import DispositionIn, ScanContext     # 契约
from app.execution.service import ExecutionError, ExecutionService   # 服务

WORK = ROOT / "var" / "p7-verify"                             # 验证目录
RESULTS = []                                                  # 结果
BASE = dict(biz_id="wv-2001", sku="SKU-B750", base_sku="SKU-B", spec="750ml",
            neighbor_specs=["500ml"], data_asof="2026-11-19T09:00")   # 基础上下文


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def main() -> int:                                             # 入口
    """执行 P7 全部验证。

    入参：无。
    出参：0 全通过。
    失败行为：异常向上抛出。
    """
    shutil.rmtree(WORK, ignore_errors=True)                     # 清理旧数据
    svc = ExecutionService(str(WORK / "exec"))                   # 服务

    hint = svc.scan(ScanContext(**BASE))                         # 规格差异
    hold = svc.scan(ScanContext(**dict(BASE, biz_id="wv-2002", cancelled=True)))   # 取消
    down = svc.scan(ScanContext(**dict(BASE, biz_id="wv-2003", system_available=False)))   # 系统不可用
    note = svc.scan(ScanContext(**dict(BASE, biz_id="wv-2004", note_text="易碎", note_attached=False)))   # 说明
    check("R1 给出提示不挂起", hint.level == "hint" and not hint.requires_human, hint.level)   # 提示
    check("R2 取消单挂起并指定计划员", hold.level == "hold" and hold.human_role == "planner", hold.level)   # 取消
    check("R2 回显数据截止时间", "2026-11-19T09:00" in hold.reasons[0].message, "asof")   # 时间
    check("R4 系统不可用转安全岗", down.level == "hold" and down.human_role == "safety", down.level)   # 系统
    check("R3 识别说明未随单", any(r.rule_id == "R3" for r in note.reasons), "R3")   # 说明
    check("规则版本随判定返回", all(d.rule_version == "exec-v1" for d in (hint, hold, down, note)), "exec-v1")   # 版本

    try:                                                         # 缺三要素
        svc.dispose(DispositionIn(decision_id=hold.decision_id, action="override"))   # 处置
        check("挂起单缺三要素被拒", False, "未拦截")              # 失败
    except ExecutionError as exc:                                # 预期
        check("挂起单缺三要素被拒", exc.code == "E_HUMAN_REQUIRED", exc.code)   # 拦截
    before = svc.metrics()                                        # 处置前指标
    check("未闭环挂起可计数", before["unresolved_holds"] == 2, str(before["unresolved_holds"]))   # 2 条挂起
    svc.dispose(DispositionIn(decision_id=hold.decision_id, action="override",
                              operator="唐映秋", reason="客户确认保留", confirmed_at="2026-11-19T09:06"))   # 闭环
    after = svc.metrics()                                         # 处置后
    check("闭环率计算正确", after["closure_rate"] == 0.5, str(after["closure_rate"]))   # 2 挂起 1 闭环
    check("分规则计数可用", after["by_rule"].get("R1", 0) >= 1 and after["by_rule"].get("R2", 0) >= 1,
          str(after["by_rule"]))                                  # 计数

    svc2 = ExecutionService(str(WORK / "exec2"), dedupe_minutes=10, overdue_minutes=0)   # 去重与超时
    first = svc2.scan(ScanContext(**BASE))                        # 首次
    second = svc2.scan(ScanContext(**BASE))                       # 重复
    check("重复扫码复用同一判定", second.dedupe is True and first.decision_id == second.decision_id, "dedupe")   # 复用
    svc2.scan(ScanContext(**dict(BASE, biz_id="wv-2006", cancelled=True)))   # 产生挂起
    m2 = svc2.metrics()                                           # 指标
    check("去重不重复计入判定数", m2["scans"] == 2 and m2["dedupe_hits"] == 1, str(m2["scans"]))   # 计数
    check("超时挂起单独计数", m2["overdue_holds"] == 1, str(m2["overdue_holds"]))   # 超时

    client = TestClient(app)                                      # 接口
    payload = {"ctx": dict(BASE, biz_id="wv-2005", cancelled=True)}   # 请求体
    ok_scan = client.post("/v1/exec/scan", json=payload, headers={"X-Role": "operator"})   # 一线扫码
    check("接口：operator 可判定", ok_scan.status_code == 200
          and ok_scan.json()["data"]["level"] == "hold", str(ok_scan.status_code))   # 成功
    deny_scan = client.post("/v1/exec/scan", json=payload, headers={"X-Role": "viewer"})   # 越权
    check("接口：viewer 不能判定", deny_scan.status_code == 403, str(deny_scan.status_code))   # 403
    deny_metrics = client.get("/v1/exec/metrics", headers={"X-Role": "operator"})   # 一线看指标
    check("接口：operator 不能看指标", deny_metrics.status_code == 403, str(deny_metrics.status_code))   # 403
    metrics = client.get("/v1/exec/metrics", headers={"X-Role": "engineer"})   # 工程看指标
    check("接口：engineer 可看指标", metrics.status_code == 200
          and metrics.json()["data"]["scans"] >= 1, str(metrics.status_code))   # 成功
    events = client.get("/v1/exec/events?limit=5", headers={"X-Role": "safety"})   # 事件流
    check("接口：事件流可读", events.status_code == 200 and len(events.json()["data"]["items"]) > 0, "events")   # 成功

    failed = [name for name, ok in RESULTS if not ok]             # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                                # 退出码


if __name__ == "__main__":                                       # 直接运行
    sys.exit(main())                                             # 返回退出码
