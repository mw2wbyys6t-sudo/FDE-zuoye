# -*- coding: utf-8 -*-
"""知识库存储：JSONL 存片段 + JSON 存索引，后续可平滑替换为向量库。"""

import json                                                # 序列化
from pathlib import Path                                   # 路径
from typing import Dict, List                               # 类型标注
from app.domain.models import Chunk, Fact                    # 领域模型
from app.knowledge.chunk import chunk_facts                  # 切分
from app.knowledge.index import InvertedIndex                # 倒排索引


class KnowledgeStore:                                       # 本地知识库
    def __init__(self, root: str = "var/kb"):                # 构造
        """初始化存储目录。

        入参：root 为知识库目录。
        出参：无。
        失败行为：目录创建失败时抛异常，避免静默丢库。
        """
        self.root = Path(root)                               # 保存根目录
        self.root.mkdir(parents=True, exist_ok=True)         # 不存在则创建
        self.chunks: List[Chunk] = []                        # 片段列表
        self.index = InvertedIndex()                         # 倒排索引
        self.facts: List[Fact] = []                          # 事实列表

    def ingest(self, facts: List[Fact]) -> Dict[str, int]:    # 入库
        """灌入事实并重建索引。

        入参：facts 事实列表。
        出参：{"facts": n, "chunks": m}。
        失败行为：重复编号以后者覆盖前者，不抛异常。
        """
        merged = {fact.fact_id: fact for fact in self.facts}   # 先并入已有事实
        for fact in facts:                                   # 逐条覆盖
            merged[fact.fact_id] = fact                       # 同编号覆盖
        self.facts = [merged[key] for key in sorted(merged)]   # 按编号排序
        self.chunks = chunk_facts(self.facts)                 # 重新切分
        self.index = InvertedIndex()                          # 重建索引
        for chunk in self.chunks:                             # 逐片段建索引
            self.index.add(chunk.chunk_id, chunk.text)        # 加入倒排
        return {"facts": len(self.facts), "chunks": len(self.chunks)}   # 返回统计

    def save(self) -> None:                                  # 持久化
        """把片段与索引写入磁盘。

        入参：无。
        出参：无。
        失败行为：磁盘写入失败时抛异常。
        """
        chunks_path = self.root / "chunks.jsonl"             # 片段文件
        with chunks_path.open("w", encoding="utf-8") as fh:   # 覆盖写
            for chunk in self.chunks:                         # 逐条
                fh.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")   # 单行 JSON
        (self.root / "index.json").write_text(
            json.dumps(self.index.dumps(), ensure_ascii=False), encoding="utf-8")   # 索引落盘
        with (self.root / "facts.jsonl").open("w", encoding="utf-8") as fh:   # 事实单独落盘，便于重建
            for fact in self.facts:                           # 逐条
                fh.write(json.dumps(fact.model_dump(), ensure_ascii=False) + "\n")   # 单行 JSON

    def load(self) -> "KnowledgeStore":                       # 读取
        """从磁盘恢复片段与索引。

        入参：无。
        出参：自身，便于链式调用。
        失败行为：文件不存在时抛异常，由调用方决定是否重新入库。
        """
        chunks_path = self.root / "chunks.jsonl"              # 片段文件
        self.chunks = [Chunk.model_validate_json(line) for line in
                       chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]   # 逐行还原
        index_path = self.root / "index.json"                 # 索引文件
        self.index = InvertedIndex.loads(json.loads(index_path.read_text(encoding="utf-8")))   # 还原索引
        facts_path = self.root / "facts.jsonl"                # 事实文件
        if facts_path.exists():                               # 有则恢复，供 A2/A3 使用
            self.facts = [Fact.model_validate_json(line) for line in
                          facts_path.read_text(encoding="utf-8").splitlines() if line.strip()]   # 逐行还原
        return self                                           # 返回自身

    def stats(self) -> Dict[str, object]:                     # 统计
        """返回知识库概况，供接口与验收脚本使用。

        入参：无。
        出参：含片段数、维度分布、角色可见分布。
        失败行为：不抛异常。
        """
        dims: Dict[str, int] = {}                             # 维度计数
        for chunk in self.chunks:                             # 逐片段
            dims[chunk.dimension.value] = dims.get(chunk.dimension.value, 0) + 1   # 累加
        return {"chunks": len(self.chunks), "dimensions": dims,
                "facts": len({chunk.fact_id for chunk in self.chunks})}   # 汇总
