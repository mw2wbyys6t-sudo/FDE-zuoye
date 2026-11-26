# -*- coding: utf-8 -*-
"""依赖装配：配置、追踪、知识库、记忆、Wiki 的进程内单例，避免各路由重复初始化。"""

from pathlib import Path                                    # 路径
from app.api.auth import make_role_dependency               # 角色依赖
from app.config import load_config, get                     # 配置
from app.harness.trace import TraceWriter                    # 追踪
from app.knowledge.store import KnowledgeStore               # 知识库
from app.memory.store import LocalMemoryStore                # 记忆
from app.orchestrator.engine import Orchestrator              # 编排
from app.execution.service import ExecutionService            # 执行层
from app.wiki.service import WikiService                     # Wiki 服务
from app.wiki.store import WikiStore                         # Wiki 存储

CONFIG = load_config()                                      # 加载配置
ROLE_DEP = make_role_dependency(CONFIG)                     # 角色依赖
TRACE = TraceWriter(get(CONFIG, "app.trace_dir", "./var/trace"),
                    store_raw=bool(get(CONFIG, "trace.store_raw", True)),
                    max_raw_chars=int(get(CONFIG, "trace.max_raw_chars", 2000)))   # 追踪单例
ALLOWED_ROLES = get(CONFIG, "app.allowed_roles", [])        # 角色白名单

KB = KnowledgeStore(get(CONFIG, "app.kb_dir", "./var/kb"))   # 知识库单例
if (Path(get(CONFIG, "app.kb_dir", "./var/kb")) / "chunks.jsonl").exists():   # 已有落盘
    KB.load()                                               # 恢复

MEMORY = LocalMemoryStore(get(CONFIG, "app.memory_dir", "./var/memory"),
                          int(get(CONFIG, "memory.ttl_days", 90)))   # 记忆单例
if (Path(get(CONFIG, "app.memory_dir", "./var/memory")) / "items.jsonl").exists():   # 已有落盘
    MEMORY.load()                                           # 恢复

WIKI = WikiService(WikiStore(get(CONFIG, "app.wiki_dir", "./var/wiki")), KB, ALLOWED_ROLES)   # Wiki 单例
ORCH = Orchestrator(get(CONFIG, "app.task_dir", "./var/tasks"), KB)   # 编排单例
EXEC = ExecutionService(get(CONFIG, "app.exec_dir", "./var/exec"),
                        dedupe_minutes=int(get(CONFIG, "exec.dedupe_minutes", 10)),
                        overdue_minutes=int(get(CONFIG, "exec.overdue_minutes", 15)))   # 执行层单例
