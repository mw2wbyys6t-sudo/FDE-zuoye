# -*- coding: utf-8 -*-
"""写入策略：决定哪条记忆能进哪一层，以及冲突怎么处理。"""

import hashlib                                              # 生成稳定编号
from datetime import datetime, timedelta, timezone           # 时间与过期计算
from typing import List, Tuple                              # 类型标注
from app import errors as E                                  # 错误码
from app.memory.models import MemoryItem, MemoryLayer        # 记忆模型


class MemoryPolicyError(Exception):                          # 策略异常
    def __init__(self, code: str, msg: str):                  # 初始化
        """构造策略异常。

        入参：code 错误码；msg 中文说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                # 交给基类
        self.code = code                                     # 保存错误码
        self.msg = msg                                       # 保存说明


def make_memory_id(layer: MemoryLayer, text: str) -> str:     # 生成编号
    """按层与正文生成稳定编号，便于去重。

    入参：layer 记忆层；text 正文。
    出参：形如 semantic-1a2b3c4d 的编号。
    失败行为：不抛异常。
    """
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]   # 取前 8 位
    return "%s-%s" % (layer.value, digest)                   # 层前缀 + 摘要


def enforce(layer: MemoryLayer, fact_refs: List[str], verified: bool,
            task_id: str = "") -> None:                       # 写入门槛
    """按层检查写入前置条件。

    入参：layer 目标层；fact_refs 事实编号；verified 是否已核验；task_id 任务编号。
    出参：无。
    失败行为：不满足条件时抛 MemoryPolicyError。
    """
    # 原因：semantic 会被后续所有检索命中，未核验或无事实编号的内容一旦写入，等于把猜测固化为知识
    if layer == MemoryLayer.SEMANTIC:                        # 语义记忆
        if not verified:                                     # 未核验
            raise MemoryPolicyError(E.E_HUMAN_REQUIRED, "语义记忆必须经核验后才能写入")   # 拒绝
        if not fact_refs:                                    # 无事实编号
            raise MemoryPolicyError(E.E_NO_EVIDENCE, "语义记忆必须关联事实编号")   # 拒绝
    # 原因：episodic 用于复盘归因，没有任务编号就无法回溯是哪次运行产生的
    if layer == MemoryLayer.EPISODIC and not task_id:        # 轨迹记忆
        raise MemoryPolicyError(E.E_SCHEMA, "轨迹记忆必须带 task_id")   # 拒绝


def build(layer: MemoryLayer, text: str, fact_refs: List[str], role: str,
          verified: bool, visibility: List[str], ttl_days: int = 90) -> MemoryItem:   # 构造记忆
    """按策略构造一条记忆并计算有效期。

    入参：layer 层；text 正文；fact_refs 事实编号；role 角色；verified 核验标记；visibility 可见角色；ttl_days 保留天数。
    出参：MemoryItem。
    失败行为：不抛异常；前置条件由 enforce 单独负责。
    """
    now = datetime.now(timezone.utc)                         # 当前时间
    expires = now + timedelta(days=ttl_days)                 # 过期时间
    return MemoryItem(memory_id=make_memory_id(layer, text), layer=layer, text=text,
                      fact_refs=fact_refs, role=role, verified=verified,
                      visibility=visibility, created_at=now.isoformat(),
                      expires_at=expires.isoformat())         # 组装


def detect_conflict(existing: List[MemoryItem], candidate: MemoryItem) -> bool:   # 冲突检测
    """判断新记忆是否与已有语义记忆冲突。

    入参：existing 已有记忆；candidate 待写入记忆。
    出参：True 表示存在冲突。
    失败行为：不抛异常。
    """
    # 原因：口径与结论冲突时不能自动合并，只能并存并等人工裁定，否则等于系统替人做了业务决定
    if candidate.layer != MemoryLayer.SEMANTIC:              # 只有语义层需要冲突检测
        return False                                          # 其它层直接放过
    key = set(candidate.fact_refs)                            # 用事实集合作为比对键
    for item in existing:                                     # 逐条比对
        if item.layer != MemoryLayer.SEMANTIC:                # 只看语义层
            continue                                          # 跳过
        if set(item.fact_refs) == key and item.text != candidate.text:   # 同证据不同结论
            return True                                       # 标记冲突
    return False                                              # 无冲突
