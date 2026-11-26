# -*- coding: utf-8 -*-
"""P0 验证脚本：一条命令验证契约、重试、闸门、接口结构与追踪落盘。"""

import sys                                                   # 退出码
from pathlib import Path                                     # 路径处理

ROOT = Path(__file__).resolve().parents[1]                    # 项目根目录（scripts 的上一级）
if str(ROOT) not in sys.path:                                 # 直接运行时脚本目录在首位
    sys.path.insert(0, str(ROOT))                             # 插入项目根，保证 app 包可导入

from fastapi.testclient import TestClient                    # 进程内客户端
from app.config import load_config, get                      # 配置
from app.harness.guards import GuardError, check_evidence, check_boundary   # 闸门
from app.harness.runner import RunSpec, Runner, RunnerError  # 执行器
from app.harness.schema import EvidenceOutput                # 契约
from app.harness.trace import TraceWriter                    # 追踪
from app.main import app                                     # 应用
from app.model.fake import FakeClient                        # 假模型

RESULTS = []                                                 # 收集每条检查的结果
GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 合法输出
TRACE_DIR = Path("var/trace")                                # 追踪目录


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录一条检查
    """记录单条验证结果。

    入参：name 检查名；condition 是否通过；detail 补充说明。
    出参：无。
    失败行为：不抛异常，由 main 汇总退出码。
    """
    RESULTS.append((name, bool(condition), detail))           # 追加结果
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 立即打印


def main() -> int:                                           # 脚本入口
    """执行 P0 全部验证项。

    入参：无。
    出参：0 表示全部通过，1 表示存在失败项。
    失败行为：内部异常向上抛出，由命令行表现。
    """
    config = load_config()                                   # 加载配置
    check("config.env 可读", bool(get(config, "app.env")), str(get(config, "app.env")))   # 配置可用

    trace = TraceWriter(str(TRACE_DIR))                      # 初始化追踪
    runner = Runner(FakeClient(["不是 JSON", GOOD]), trace, max_retry=2)   # 先错后对
    spec = RunSpec(step="verify_p0", prompt_version="v-p0", schema=EvidenceOutput,
                   system="s", user="u",
                   guards=[lambda obj: check_evidence([c.model_dump() for c in obj.claims])])   # 带证据闸门
    result = runner.run(spec)                                # 执行
    check("重试后成功且 attempts=2", result["attempts"] == 2, str(result["attempts"]))   # 重试生效
    trace_file = TRACE_DIR / ("%s.jsonl" % result["trace_id"])   # 追踪文件路径
    check("追踪文件已落盘", trace_file.exists(), str(trace_file))   # 可回放前提

    try:                                                     # 无证据必须拦截
        check_evidence([{"text": "拣选是主因", "fact_id": ""}])   # 空编号
        check("无证据被拦截", False, "未抛异常")               # 未拦截即失败
    except GuardError as exc:                                # 预期异常
        check("无证据被拦截", exc.code == "E_NO_EVIDENCE", exc.code)   # 错误码正确

    try:                                                     # 写库必须拦截
        check_boundary("write_db")                           # 越界动作
        check("写库被拦截", False, "未抛异常")                 # 未拦截即失败
    except GuardError as exc:                                # 预期异常
        check("写库被拦截", exc.code == "E_BOUNDARY", exc.code)   # 错误码正确

    try:                                                     # 重试耗尽必须失败
        Runner(FakeClient(["坏输出"]), trace, max_retry=1).run(
            RunSpec(step="bad", prompt_version="v-p0", schema=EvidenceOutput, system="s", user="u"))   # 始终非法
        check("非法输出最终失败", False, "未抛异常")            # 未抛即失败
    except RunnerError as exc:                               # 预期异常
        check("非法输出最终失败", exc.code == "E_SCHEMA", exc.code)   # 错误码正确

    client = TestClient(app)                                 # 进程内客户端
    health = client.get("/v1/health").json()                 # 健康检查
    check("health 三键结构", set(health.keys()) == {"ok", "data", "error"}, str(sorted(health.keys())))   # 结构正确
    selftest = client.post("/v1/harness/selftest", headers={"X-Role": "engineer"}).json()   # 自测接口
    cases = {c["name"]: c for c in selftest["data"]["cases"]} if selftest.get("ok") else {}   # 索引用例
    check("自测三项齐备", len(cases) == 3, str(list(cases.keys())))   # 三个用例
    check("自测 retry 生效", cases.get("retry", {}).get("detail", {}).get("attempts") == 2,
          str(cases.get("retry", {}).get("detail", {}).get("attempts")))   # 重试次数
    forbidden = client.post("/v1/harness/selftest")           # 缺角色
    check("缺角色返回 403+三键", forbidden.status_code == 403 and set(forbidden.json().keys()) == {"ok", "data", "error"},
          str(forbidden.status_code))                         # 结构与状态码

    failed = [name for name, ok, _ in RESULTS if not ok]      # 汇总失败项
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 汇总
    return 0 if not failed else 1                             # 返回退出码


if __name__ == "__main__":                                    # 直接运行
    sys.exit(main())                                          # 用返回值作为退出码
