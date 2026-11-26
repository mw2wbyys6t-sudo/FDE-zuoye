# -*- coding: utf-8 -*-
"""应用入口：装配配置、追踪、模型与路由，只暴露 P0 所需的最小接口。"""

from typing import Any, Dict, List                           # 类型标注
from pathlib import Path                                     # 静态目录定位
from fastapi import Depends, FastAPI                         # 框架
from fastapi.responses import RedirectResponse               # 根路径跳转
from fastapi.staticfiles import StaticFiles                  # 静态文件挂载
from app.api.auth import make_role_dependency                # 角色依赖
from app.api.envelope import ok, fail, register_handlers     # 统一响应
from app.api import errors as E                              # 错误码
from app.config import load_config, get                      # 配置加载
from app.harness.guards import GuardError, check_evidence     # 闸门
from app.harness.runner import RunSpec, Runner, RunnerError   # 执行器
from app.harness.schema import EvidenceOutput                 # 契约
from app.harness.trace import TraceWriter                     # 追踪
from app.model.fake import FakeClient                         # 假模型
from app.api.routes_kb import router as kb_router              # 知识库路由
from app.api.routes_memory import router as memory_router      # 记忆路由
from app.api.routes_wiki import router as wiki_router          # Wiki 路由
from app.api.routes_agents import router as agents_router      # Agent 路由
from app.api.routes_tasks import router as tasks_router        # 任务编排路由
from app.api.routes_execution import router as exec_router     # 执行层路由

CONFIG = load_config()                                        # 启动即加载配置，缺配置直接失败
TRACE = TraceWriter(get(CONFIG, "app.trace_dir", "./var/trace"),
                    store_raw=bool(get(CONFIG, "trace.store_raw", True)),
                    max_raw_chars=int(get(CONFIG, "trace.max_raw_chars", 2000)))   # 按配置决定是否记录原文
ROLE_DEP = make_role_dependency(CONFIG)                        # 构造角色依赖

app = FastAPI(title="FDE Agent Harness", version="0.1.0")      # 创建应用
register_handlers(app)                                         # 注册统一异常处理
app.include_router(kb_router)                                  # 挂载知识库路由
app.include_router(memory_router)                              # 挂载记忆路由
app.include_router(wiki_router)                                # 挂载 Wiki 路由
app.include_router(agents_router)                              # 挂载 Agent 路由
app.include_router(tasks_router)                               # 挂载任务编排路由
app.include_router(exec_router)                                # 挂载执行层路由
WEB_DIR = Path(__file__).parent / "web"                        # 前端静态目录
app.mount("/ui", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")   # 挂载 MVP 控制台


@app.get("/")                                                  # 根路径
def index() -> RedirectResponse:
    """把根路径重定向到控制台。

    入参：无。
    出参：重定向响应。
    失败行为：静态目录缺失时由 /ui 返回 404，便于定位部署问题。
    """
    return RedirectResponse(url="/ui/")                         # 跳转控制台


def _build_client(script: List[str]) -> FakeClient:            # 构造 P0 用的假模型
    """按脚本构造 Fake 模型客户端。

    入参：script 为按调用顺序返回的文本列表。
    出参：FakeClient 实例。
    失败行为：脚本为空时抛 ValueError。
    """
    return FakeClient(script)                                  # 直接返回，P0 不接真实模型


def _run_case(name: str, script: List[str], guards: List[Any]) -> Dict[str, Any]:   # 跑单个自测用例
    """执行一个自测用例并汇总结果。

    入参：name 用例名；script 假模型脚本；guards 需挂载的闸门列表。
    出参：{"name","ok","detail"}。
    失败行为：内部异常被捕获并标记为失败，保证自测整体可完成。
    """
    runner = Runner(_build_client(script), TRACE, max_retry=2)  # 每个用例独立客户端，避免脚本串味
    spec = RunSpec(step=name, prompt_version="p0-selftest", schema=EvidenceOutput,
                   system="只返回 JSON。", user="抽取结论。", guards=guards)   # 固定测试规格
    try:                                                         # 执行并捕获两类预期异常
        result = runner.run(spec)                                # 运行
        return {"name": name, "ok": True, "detail": result}      # 成功用例
    except GuardError as exc:                                    # 闸门拦截属于预期结果之一
        return {"name": name, "ok": False, "detail": {"code": exc.code, "msg": exc.msg}}   # 返回拦截信息
    except RunnerError as exc:                                   # 契约失败
        return {"name": name, "ok": False, "detail": {"code": exc.code, "msg": exc.msg}}   # 返回失败信息


@app.get("/v1/health")                                         # 健康检查
def health() -> Dict[str, Any]:
    """返回服务与依赖状态。

    入参：无。
    出参：统一三键结构，data 含环境、模型提供方与追踪目录。
    失败行为：不抛异常。
    """
    return ok({"status": "up", "env": get(CONFIG, "app.env", "dev"),
               "model_provider": get(CONFIG, "model.provider", "fake"),
               "trace_dir": get(CONFIG, "app.trace_dir", "./var/trace")})   # 基础自检信息


@app.post("/v1/harness/selftest")                              # Harness 自测
def selftest(role: str = Depends(ROLE_DEP)) -> Dict[str, Any]:
    """用三个固定用例验证契约、重试、降级与证据闸门。

    入参：role 由 X-Role 请求头注入，用于权限闸门演示。
    出参：统一三键结构，data.cases 为三个用例结果。
    失败行为：不抛异常；用例失败通过 ok=false 与错误码体现。
    """
    good = '[{"text":"取消单已进波次仍被装车","fact_id":"f11"}]'          # 合法输出（包装成 claims 结构见下）
    good_json = '{"claims":[{"text":"取消单已进波次仍被装车","fact_id":"f11"}]}'   # 合法契约
    bad_then_good = ["这不是 JSON", good_json]                    # 首次不合法，第二次合法
    no_evidence = '{"claims":[{"text":"拣选是错发主因","fact_id":""}]}'   # 缺少事实编号，应被拦截
    cases = [                                                     # 三个用例
        _run_case("valid", [good_json], [lambda obj: check_evidence([c.model_dump() for c in obj.claims])]),   # 正常路径
        _run_case("retry", bad_then_good, []),                    # 重试路径
        _run_case("no_evidence", [no_evidence],
                  [lambda obj: check_evidence([c.model_dump() for c in obj.claims])]),   # 闸门路径
    ]
    passed = [c["ok"] for c in cases]                             # 汇总通过情况
    data = {"cases": cases, "passed": sum(1 for p in passed if p),
            "expected": {"valid": True, "retry": True, "no_evidence": False}}   # 期望值随结果返回
    return ok(data)                                               # 统一返回
