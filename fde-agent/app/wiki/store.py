# -*- coding: utf-8 -*-
"""Wiki 存储：页面 + 版本快照 + 审计，全部落一个 JSON 文件，便于迁移。"""

import json                                                 # 序列化
from datetime import datetime, timezone                      # 时间
from pathlib import Path                                     # 路径
from typing import Dict, List, Optional                      # 类型标注
from app.wiki.models import AuditEntry, WikiPage, WikiRevision   # 模型


class WikiStore:                                            # Wiki 存储
    def __init__(self, path: str = "var/wiki/wiki.json"):    # 构造
        """初始化存储。

        入参：path 数据文件路径。
        出参：无。
        失败行为：目录创建失败时抛异常。
        """
        self.path = Path(path)                                # 保存路径
        self.path.parent.mkdir(parents=True, exist_ok=True)    # 创建目录
        self.pages: Dict[str, WikiPage] = {}                  # 页面索引
        self.revisions: List[WikiRevision] = []               # 版本快照
        self.audit: List[AuditEntry] = []                     # 审计记录
        if self.path.exists():                                # 已有数据
            self.load()                                       # 直接恢复

    def _now(self) -> str:                                    # 当前时间
        """返回 UTC ISO 时间串。

        入参：无。
        出参：时间字符串。
        失败行为：无。
        """
        return datetime.now(timezone.utc).isoformat()         # 统一时区

    def save(self) -> None:                                   # 持久化
        """写入 JSON 文件。

        入参：无。
        出参：无。
        失败行为：磁盘错误时抛异常。
        """
        payload = {"pages": {k: v.model_dump() for k, v in self.pages.items()},
                   "revisions": [r.model_dump() for r in self.revisions],
                   "audit": [a.model_dump() for a in self.audit]}   # 全量导出
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")   # 写文件

    def load(self) -> "WikiStore":                            # 读取
        """从 JSON 恢复。

        入参：无。
        出参：自身。
        失败行为：JSON 损坏时抛异常。
        """
        payload = json.loads(self.path.read_text(encoding="utf-8"))   # 读取
        self.pages = {k: WikiPage.model_validate(v) for k, v in payload.get("pages", {}).items()}   # 还原页面
        self.revisions = [WikiRevision.model_validate(r) for r in payload.get("revisions", [])]   # 还原版本
        self.audit = [AuditEntry.model_validate(a) for a in payload.get("audit", [])]   # 还原审计
        return self                                            # 返回自身

    def get(self, slug: str) -> Optional[WikiPage]:            # 取页面
        """按标识取页面。

        入参：slug 页面标识。
        出参：页面或 None。
        失败行为：不抛异常。
        """
        return self.pages.get(slug)                            # 直接查字典

    def put(self, page: WikiPage, action: str, role: str, detail: str = "") -> WikiPage:   # 写入
        """保存页面并记录版本与审计。

        入参：page 页面；action 动作；role 操作角色；detail 说明。
        出参：保存后的页面。
        失败行为：无。
        """
        page = page.model_copy(update={"updated_at": self._now()})   # 更新时间
        self.pages[page.slug] = page                            # 覆盖
        self.revisions.append(WikiRevision(slug=page.slug, version=page.version,
                                           title=page.title, body=page.body,
                                           status=page.status, editor=role,
                                           created_at=self._now()))   # 记录快照
        self.audit.append(AuditEntry(action=action, slug=page.slug, role=role,
                                     version=page.version, detail=detail,
                                     created_at=self._now()))   # 记录审计
        self.save()                                             # 落盘
        return page                                             # 返回

    def revisions_of(self, slug: str) -> List[WikiRevision]:    # 版本列表
        """返回某页面的全部版本，按版本号升序。

        入参：slug 页面标识。
        出参：版本列表。
        失败行为：不抛异常。
        """
        return sorted((r for r in self.revisions if r.slug == slug), key=lambda r: r.version)   # 过滤排序

    def revision(self, slug: str, version: int) -> Optional[WikiRevision]:   # 取快照
        """按版本号取快照。

        入参：slug 页面标识；version 版本号。
        出参：快照或 None。
        失败行为：不抛异常。
        """
        for item in self.revisions:                            # 线性查找
            if item.slug == slug and item.version == version:   # 命中
                return item                                    # 返回
        return None                                            # 未找到
