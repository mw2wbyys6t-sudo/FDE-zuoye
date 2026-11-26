# -*- coding: utf-8 -*-
"""本地记忆存储：JSONL 持久化 + 倒排检索 + 过期清理，可替换为 Mem0 后端。"""

import json                                                 # 序列化
from datetime import datetime, timezone                      # 过期判断
from pathlib import Path                                     # 路径
from typing import Dict, List, Optional                      # 类型标注
from app.knowledge.index import InvertedIndex                # 复用倒排索引
from app.memory.models import MemoryItem, MemoryLayer         # 记忆模型
from app.memory.policy import MemoryPolicyError, build, detect_conflict, enforce   # 策略


class LocalMemoryStore:                                      # 本地记忆库
    def __init__(self, root: str = "var/memory", ttl_days: int = 90):   # 构造
        """初始化记忆目录与索引。

        入参：root 目录；ttl_days 默认保留天数。
        出参：无。
        失败行为：目录创建失败时抛异常。
        """
        self.root = Path(root)                                # 保存目录
        self.root.mkdir(parents=True, exist_ok=True)          # 创建目录
        self.ttl_days = ttl_days                              # 保存有效期
        self.items: List[MemoryItem] = []                     # 记忆列表
        self.index = InvertedIndex()                          # 倒排索引

    def _reindex(self) -> None:                               # 重建索引
        """按当前记忆重建倒排索引。

        入参：无。
        出参：无。
        失败行为：无。
        """
        self.index = InvertedIndex()                          # 新建索引
        for item in self.items:                               # 逐条
            self.index.add(item.memory_id, item.text)         # 加入倒排

    def write(self, layer: MemoryLayer, text: str, fact_refs: List[str], role: str,
              verified: bool = False, visibility: Optional[List[str]] = None,
              task_id: str = "") -> Dict[str, object]:        # 写入
        """按策略写入一条记忆。

        入参：layer 层；text 正文；fact_refs 事实编号；role 角色；verified 是否核验；visibility 可见角色；task_id 任务编号。
        出参：{"memory_id","conflict","dedup"}。
        失败行为：违反策略时抛 MemoryPolicyError。
        """
        enforce(layer, fact_refs, verified, task_id)          # 先过策略
        visibility = visibility or ["viewer", "operator", "engineer", "safety", "admin"]   # 默认全角色
        candidate = build(layer, text, fact_refs, role, verified, visibility, self.ttl_days)   # 构造
        for item in self.items:                               # 去重
            if item.memory_id == candidate.memory_id:          # 同层同文
                return {"memory_id": item.memory_id, "conflict": item.conflict, "dedup": True}   # 直接返回
        conflict = detect_conflict(self.items, candidate)      # 冲突检测
        candidate = candidate.model_copy(update={"conflict": conflict})   # 回填冲突标记
        self.items.append(candidate)                          # 追加
        self.index.add(candidate.memory_id, candidate.text)    # 入索引
        self.save()                                           # 落盘
        return {"memory_id": candidate.memory_id, "conflict": conflict, "dedup": False}   # 返回

    def search(self, query: str, role: str, layer: Optional[MemoryLayer] = None,
               top_k: int = 5) -> List[MemoryItem]:           # 检索
        """按角色、层与相关度检索记忆。

        入参：query 查询串；role 角色；layer 层过滤；top_k 返回条数。
        出参：MemoryItem 列表。
        失败行为：空查询返回空列表。
        """
        if not query.strip():                                 # 空查询
            return []                                         # 直接返回
        self.prune()                                          # 先清理过期，避免召回僵尸记忆
        allowed = {item.memory_id for item in self.items
                   if role in item.visibility and (layer is None or item.layer == layer)}   # 元数据过滤
        ranked = self.index.search(query, allowed)[:max(1, top_k)]   # 打分
        mapping = {item.memory_id: item for item in self.items}   # 编号索引
        return [mapping[mid] for mid, _ in ranked if mid in mapping]   # 按分数顺序返回

    def prune(self) -> int:                                    # 清理过期
        """删除已过期记忆。

        入参：无。
        出参：删除条数。
        失败行为：时间解析失败时跳过该条，不中断整批。
        """
        now = datetime.now(timezone.utc)                       # 当前时间
        alive, removed = [], 0                                 # 保留列表与删除计数
        for item in self.items:                                # 逐条判断
            try:                                               # 解析过期时间
                expired = datetime.fromisoformat(item.expires_at) < now   # 是否过期
            except ValueError:                                 # 时间缺失或格式异常
                expired = False                                # 视为不过期，交给人工处理
            if expired:                                        # 过期
                removed += 1                                   # 计数
            else:                                              # 未过期
                alive.append(item)                             # 保留
        if removed:                                            # 有删除才重建
            self.items = alive                                 # 更新列表
            self._reindex()                                    # 重建索引
            self.save()                                        # 落盘
        return removed                                         # 返回删除数

    def stats(self) -> Dict[str, object]:                      # 统计
        """返回各层记忆数量与冲突数。

        入参：无。
        出参：字典。
        失败行为：不抛异常。
        """
        layers: Dict[str, int] = {}                            # 分层计数
        for item in self.items:                                # 逐条
            layers[item.layer.value] = layers.get(item.layer.value, 0) + 1   # 累加
        return {"total": len(self.items), "layers": layers,
                "conflicts": sum(1 for item in self.items if item.conflict)}   # 汇总

    def save(self) -> None:                                    # 持久化
        """覆盖写入 JSONL。

        入参：无。
        出参：无。
        失败行为：磁盘错误时抛异常。
        """
        path = self.root / "items.jsonl"                       # 文件路径
        with path.open("w", encoding="utf-8") as fh:            # 覆盖写
            for item in self.items:                            # 逐条
                fh.write(json.dumps(item.model_dump(), ensure_ascii=False) + "\n")   # 单行 JSON

    def load(self) -> "LocalMemoryStore":                      # 读取
        """从 JSONL 恢复记忆。

        入参：无。
        出参：自身。
        失败行为：文件不存在时抛异常。
        """
        path = self.root / "items.jsonl"                       # 文件路径
        self.items = [MemoryItem.model_validate_json(line) for line in
                      path.read_text(encoding="utf-8").splitlines() if line.strip()]   # 逐行还原
        self._reindex()                                        # 重建索引
        return self                                            # 返回自身
