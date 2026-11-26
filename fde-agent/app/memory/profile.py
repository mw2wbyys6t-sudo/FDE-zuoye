# -*- coding: utf-8 -*-
"""环境画像：把行业、角色、术语与默认口径固化为可迁移的 procedural 记忆。"""

import json                                                  # 序列化
from pathlib import Path                                     # 路径
from typing import Dict, List                                 # 类型标注
from app.knowledge.store import KnowledgeStore                # 读取知识库统计


def build_profile(store: KnowledgeStore, extra_terms: List[str] = None) -> Dict[str, object]:   # 生成画像
    """从知识库与配置生成环境画像。

    入参：store 已入库的知识库；extra_terms 追加术语。
    出参：含行业、角色、术语、口径提示的字典。
    失败行为：知识库为空时仍返回可用骨架，不抛异常。
    """
    terms = ["拣选", "波次", "复核", "装车核验", "错发", "漏扫", "取消单", "主编号"]   # 领域基础术语
    terms.extend(extra_terms or [])                           # 追加自定义术语
    return {"industry": "logistics-warehouse",                # 行业标识
            "roles": ["viewer", "operator", "engineer", "safety", "admin"],   # 角色表
            "terms": terms,                                    # 术语表
            "defaults": {"ttl_days": 90, "top_k": 5},           # 默认参数
            "knowledge": store.stats()}                        # 知识库概况


def save_profile(profile: Dict[str, object], path: str = "var/memory/profile.json") -> None:   # 保存
    """把画像写入文件。

    入参：profile 画像；path 目标路径。
    出参：无。
    失败行为：磁盘错误时抛异常。
    """
    target = Path(path)                                       # 路径对象
    target.parent.mkdir(parents=True, exist_ok=True)           # 确保目录存在
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")   # 写文件


def load_profile(path: str = "var/memory/profile.json") -> Dict[str, object]:   # 读取
    """读取环境画像。

    入参：path 文件路径。
    出参：画像字典；文件不存在时返回空字典。
    失败行为：JSON 损坏时抛异常，避免带病运行。
    """
    target = Path(path)                                       # 路径对象
    if not target.exists():                                   # 不存在
        return {}                                             # 返回空画像
    return json.loads(target.read_text(encoding="utf-8"))      # 解析
