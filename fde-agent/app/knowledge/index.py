# -*- coding: utf-8 -*-
"""倒排索引：中文用字符二元组，拉丁用词，配 BM25 打分，零外部依赖。"""

import math                                                # 计算 idf 与对数
import re                                                  # 提取拉丁词
from collections import defaultdict                        # 倒排表
from typing import Dict, List                               # 类型标注

LATIN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]*")      # 拉丁词与标识符
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")               # 连续中文片段


def tokenize(text: str) -> List[str]:                       # 分词
    """把文本切成检索词：拉丁词小写 + 中文一元与二元组。

    入参：text 原文。
    出参：词列表（保留重复，用于词频）。
    失败行为：空文本返回空列表。
    """
    tokens = [m.group(0).lower() for m in LATIN_PATTERN.finditer(text)]   # 拉丁词
    for segment in CJK_PATTERN.findall(text):               # 逐段中文
        tokens.extend(list(segment))                        # 加一元，覆盖单字查询
        tokens.extend([segment[i:i + 2] for i in range(len(segment) - 1)])   # 加二元组，覆盖词语
    return tokens                                           # 返回


class InvertedIndex:                                        # 倒排索引
    def __init__(self, k1: float = 1.5, b: float = 0.75):    # 构造
        """初始化索引参数。

        入参：k1 词频饱和参数；b 长度归一参数。
        出参：无。
        失败行为：无。
        """
        self.k1 = k1                                        # 保存 k1
        self.b = b                                          # 保存 b
        self.postings: Dict[str, Dict[str, int]] = defaultdict(dict)   # 词 -> (片段 -> 词频)
        self.lengths: Dict[str, int] = {}                   # 片段长度
        self.avg_len = 0.0                                  # 平均长度

    def add(self, chunk_id: str, text: str) -> None:        # 加入文档
        """把片段加入索引。

        入参：chunk_id 片段编号；text 片段文本。
        出参：无。
        失败行为：空文本也会登记长度，保证分母一致。
        """
        tokens = tokenize(text)                             # 分词
        self.lengths[chunk_id] = len(tokens)                # 记录长度
        for token in tokens:                                # 累计词频
            row = self.postings[token]                      # 取倒排行
            row[chunk_id] = row.get(chunk_id, 0) + 1        # 词频加一
        total = sum(self.lengths.values())                  # 总长度
        self.avg_len = total / max(1, len(self.lengths))    # 更新平均长度

    def search(self, query: str, allowed: set) -> List[tuple]:   # 检索
        """对候选片段集合计算 BM25 分数。

        入参：query 查询词；allowed 允许参与打分的片段编号集合（用于元数据过滤）。
        出参：[(chunk_id, score)] 按分数降序。
        失败行为：无匹配时返回空列表。
        """
        terms = set(tokenize(query))                        # 去重查询词
        total_docs = max(1, len(self.lengths))              # 文档总数
        scores: Dict[str, float] = defaultdict(float)       # 累计分数
        for term in terms:                                  # 逐词
            row = self.postings.get(term)                   # 取倒排行
            if not row:                                     # 无该词
                continue                                    # 跳过
            df = len(row)                                   # 文档频率
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))   # BM25 idf
            for chunk_id, tf in row.items():                # 逐片段
                if chunk_id not in allowed:                 # 元数据过滤
                    continue                                # 跳过
                dl = self.lengths.get(chunk_id, 0)          # 片段长度
                norm = tf + self.k1 * (1 - self.b + self.b * dl / max(1e-9, self.avg_len))   # 归一化分母
                scores[chunk_id] += idf * tf * (self.k1 + 1) / max(1e-9, norm)   # 累加
        return sorted(((k, round(v, 4)) for k, v in scores.items() if v > 0),
                      key=lambda item: item[1], reverse=True)   # 降序返回

    def dumps(self) -> Dict[str, object]:                   # 导出
        """导出为可 JSON 化的结构。

        入参：无。
        出参：包含 postings / lengths / avg_len / k1 / b 的字典。
        失败行为：无。
        """
        return {"postings": {k: dict(v) for k, v in self.postings.items()},
                "lengths": dict(self.lengths), "avg_len": self.avg_len,
                "k1": self.k1, "b": self.b}                 # 扁平结构，便于落盘

    @classmethod                                            # 类方法构造
    def loads(cls, data: Dict[str, object]) -> "InvertedIndex":   # 从字典恢复
        """从导出结构恢复索引。

        入参：data 为 dumps 的结果。
        出参：InvertedIndex 实例。
        失败行为：结构缺失时抛 KeyError，避免带病检索。
        """
        index = cls(k1=float(data["k1"]), b=float(data["b"]))   # 恢复参数
        index.postings = defaultdict(dict, {k: dict(v) for k, v in data["postings"].items()})   # 恢复倒排
        index.lengths = dict(data["lengths"])                # 恢复长度
        index.avg_len = float(data["avg_len"])               # 恢复平均长度
        return index                                        # 返回实例
