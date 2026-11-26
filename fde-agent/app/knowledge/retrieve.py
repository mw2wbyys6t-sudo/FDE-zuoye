# -*- coding: utf-8 -*-
"""检索：先按元数据过滤，再 BM25 打分，最后返回带证据编号的片段。"""

from typing import List, Optional                           # 类型标注
from app.domain.models import Dimension, Hit                 # 领域模型
from app.knowledge.store import KnowledgeStore               # 存储


class Retriever:                                            # 检索器
    def __init__(self, store: KnowledgeStore):               # 构造
        """绑定知识库。

        入参：store 已加载的知识库。
        出参：无。
        失败行为：store 为空时抛 ValueError。
        """
        if store is None:                                    # 必要依赖校验
            raise ValueError("store 不能为空")                # 直接失败
        self.store = store                                   # 保存
        self.by_id = {chunk.chunk_id: chunk for chunk in store.chunks}   # 编号索引

    def search(self, query: str, role: str, top_k: int = 5,
               dimension: Optional[Dimension] = None,
               version: Optional[str] = None) -> List[Hit]:   # 检索入口
        """执行一次带权限过滤的检索。

        入参：query 查询串；role 当前角色；top_k 返回条数；dimension 维度过滤；version 版本过滤。
        出参：Hit 列表，按分数降序。
        失败行为：查询为空返回空列表；无命中返回空列表。
        """
        if not query.strip():                                # 空查询
            return []                                        # 直接返回
        allowed = set()                                      # 允许参与打分的片段
        for chunk in self.store.chunks:                      # 逐片段做元数据过滤
            # 原因：角色可见性必须在检索层过滤，放到提示词层等于把不该看的内容先读进上下文
            if role not in chunk.roles_visible:              # 角色不可见
                continue                                     # 跳过
            if dimension is not None and chunk.dimension != dimension:   # 维度不符
                continue                                     # 跳过
            if version is not None and chunk.version != version:   # 版本不符
                continue                                     # 跳过
            allowed.add(chunk.chunk_id)                      # 加入候选集
        ranked = self.store.index.search(query, allowed)[:max(1, top_k)]   # 打分并截断
        hits: List[Hit] = []                                 # 结果
        for chunk_id, score in ranked:                       # 组装命中
            chunk = self.by_id.get(chunk_id)                 # 取片段
            if chunk is None:                                # 索引与片段不一致
                continue                                     # 跳过
            hits.append(Hit(chunk_id=chunk.chunk_id, fact_id=chunk.fact_id, score=score,
                            text=chunk.text, dimension=chunk.dimension,
                            confidence=chunk.confidence, source=chunk.source))   # 保留证据编号
        return hits                                          # 返回
