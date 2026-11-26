# -*- coding: utf-8 -*-
"""切分：按事实条目切分，再按句读二分，保证 fact_id 不被打断。"""

import re                                                  # 句读切分
from typing import List                                    # 列表类型
from app.domain.models import Chunk, Fact                   # 领域模型

MAX_LEN = 200                                              # 单片段最大字符数，兼顾检索精度与上下文
SPLIT_PATTERN = re.compile(r"(?<=[。；;！？!?])")            # 在句末标点后切分


def split_text(text: str, limit: int = MAX_LEN) -> List[str]:   # 文本切分
    """把长文本按句读切成不超过 limit 的片段。

    入参：text 原始陈述；limit 单片段上限。
    出参：片段列表，至少一段。
    失败行为：空文本返回空列表，不抛异常。
    """
    if not text.strip():                                    # 空文本
        return []                                           # 返回空列表
    pieces, buffer = [], ""                                 # 结果与缓冲
    for sentence in SPLIT_PATTERN.split(text):              # 先按句切
        if not sentence:                                    # 空句跳过
            continue                                        # 继续
        if len(buffer) + len(sentence) <= limit:            # 能拼进当前片段
            buffer += sentence                              # 拼接
        else:                                               # 超出上限
            if buffer:                                      # 先存已有片段
                pieces.append(buffer)                       # 入结果
            while len(sentence) > limit:                    # 超长单句硬切
                pieces.append(sentence[:limit])             # 按上限切
                sentence = sentence[limit:]                 # 保留剩余
            buffer = sentence                               # 剩余作为新缓冲
    if buffer:                                              # 收尾
        pieces.append(buffer)                               # 入结果
    return pieces                                           # 返回片段


def chunk_fact(fact: Fact, limit: int = MAX_LEN) -> List[Chunk]:   # 单条事实切分
    """把一条事实切成若干检索片段。

    入参：fact 事实对象；limit 片段上限。
    出参：Chunk 列表，chunk_id 为 fXX#序号。
    失败行为：陈述为空时返回空列表。
    """
    chunks = []                                             # 收集片段
    for index, piece in enumerate(split_text(fact.statement, limit)):   # 逐段编号
        chunks.append(Chunk(chunk_id="%s#%d" % (fact.fact_id, index), fact_id=fact.fact_id,
                            text="%s：%s" % (fact.role, piece), dimension=fact.dimension,
                            confidence=fact.confidence, version=fact.version,
                            roles_visible=list(fact.roles_visible), source=fact.source))   # 保留角色前缀便于阅读
    return chunks                                           # 返回


def chunk_facts(facts: List[Fact], limit: int = MAX_LEN) -> List[Chunk]:   # 批量切分
    """批量切分事实列表。

    入参：facts 事实列表；limit 片段上限。
    出参：全部片段。
    失败行为：空输入返回空列表。
    """
    output = []                                             # 结果
    for fact in facts:                                      # 逐条
        output.extend(chunk_fact(fact, limit))              # 追加
    return output                                           # 返回
