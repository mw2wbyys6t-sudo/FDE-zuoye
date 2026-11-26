# -*- coding: utf-8 -*-
"""Mem0 适配器：可选后端，未安装或不可用时自动降级为本地存储。"""

from typing import Any, Dict, List                            # 类型标注


class Mem0Adapter:                                           # Mem0 后端封装
    def __init__(self, config: Dict[str, Any]):               # 构造
        """尝试初始化 Mem0 客户端。

        入参：config 为 memory 段配置。
        出参：无。
        失败行为：依赖缺失时 self.available=False，不抛异常，由调用方降级。
        """
        self.config = config                                   # 保存配置
        self.available = False                                 # 默认不可用
        self.client = None                                     # 占位
        try:                                                   # 延迟导入，避免强依赖
            from mem0 import Memory                            # type: ignore
            self.client = Memory.from_config(config)           # 按配置初始化
            self.available = True                              # 标记可用
        except Exception:                                      # 缺包或配置错误
            self.available = False                             # 保持不可用，走本地存储

    def add(self, text: str, user_id: str, metadata: Dict[str, Any]) -> Any:   # 写入
        """写入一条记忆。

        入参：text 正文；user_id 归属；metadata 元数据。
        出参：Mem0 返回结果。
        失败行为：后端不可用时抛 RuntimeError，提示调用方降级。
        """
        if not self.available:                                 # 不可用
            raise RuntimeError("Mem0 不可用，请降级到 LocalMemoryStore")   # 明确报错
        return self.client.add(text, user_id=user_id, metadata=metadata)   # 调用原生接口

    def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:   # 检索
        """按查询检索记忆。

        入参：query 查询串；user_id 归属；limit 条数。
        出参：结果列表。
        失败行为：后端不可用时抛 RuntimeError。
        """
        if not self.available:                                 # 不可用
            raise RuntimeError("Mem0 不可用，请降级到 LocalMemoryStore")   # 明确报错
        return self.client.search(query, user_id=user_id, limit=limit)   # 调用原生接口
