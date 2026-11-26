# -*- coding: utf-8 -*-
"""Wiki 服务：用户模式（只读已发布）与管理员模式（编辑、发布、回滚）。"""

from enum import Enum                                       # 模式枚举
from typing import Dict, List, Optional                      # 类型标注
from app import errors as E                                  # 错误码
from app.domain.models import Dimension                       # 维度
from app.harness.guards import GuardError, check_evidence, check_permission   # 闸门
from app.knowledge.ingest import visible_roles                # 继承知识库的可见角色规则
from app.knowledge.store import KnowledgeStore                # 知识库
from app.wiki.models import WikiPage                          # 页面模型
from app.wiki.store import WikiStore                          # 存储


class WikiError(Exception):                                  # 服务异常
    def __init__(self, code: str, msg: str):                  # 初始化
        """构造服务异常。

        入参：code 错误码；msg 中文说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                # 交给基类
        self.code = code                                     # 保存错误码
        self.msg = msg                                       # 保存说明


class WikiMode(str, Enum):                                   # 两种使用模式
    USER = "user"                                            # 用户模式：只读、只看已发布且可见
    ADMIN = "admin"                                          # 管理员模式：可写、可发布、可回滚


EDITOR_ROLES = ("engineer", "admin")                         # 可编辑角色
PUBLISH_ROLES = ("admin",)                                   # 可发布角色


class WikiService:                                           # Wiki 服务
    def __init__(self, store: WikiStore, knowledge: KnowledgeStore,
                 allowed_roles: List[str]):                  # 构造
        """绑定存储、知识库与角色白名单。

        入参：store Wiki 存储；knowledge 知识库；allowed_roles 角色白名单。
        出参：无。
        失败行为：缺少依赖时抛 ValueError。
        """
        if store is None or knowledge is None:               # 必要依赖
            raise ValueError("store 与 knowledge 不能为空")    # 直接失败
        self.store = store                                   # 保存
        self.knowledge = knowledge                           # 保存
        self.allowed_roles = allowed_roles                   # 保存

    def _known_fact_ids(self) -> set:                        # 已知事实集合
        """返回知识库中全部事实编号。

        入参：无。
        出参：编号集合。
        失败行为：不抛异常。
        """
        return {chunk.fact_id for chunk in self.knowledge.chunks}   # 从片段反推

    def _check_editor(self, role: str) -> None:               # 编辑权限
        """校验编辑权限。

        入参：role 当前角色。
        出参：无。
        失败行为：无权限时抛 WikiError(E_PERM)。
        """
        try:                                                 # 复用统一权限闸门
            check_permission(role, self.allowed_roles, require_write=True, write_roles=EDITOR_ROLES)   # 写校验
        except GuardError as exc:                            # 闸门拒绝
            raise WikiError(exc.code, exc.msg)               # 转为服务异常

    def _check_refs(self, fact_refs: List[str]) -> None:      # 引用校验
        """校验页面引用的事实编号真实存在。

        入参：fact_refs 事实编号列表。
        出参：无。
        失败行为：缺失或不存在时抛 WikiError(E_NO_EVIDENCE)。
        """
        if not fact_refs:                                    # 无引用
            # 原因：Wiki 是项目知识资产，任何结论必须能回到访谈事实，否则会变成无出处的传言
            raise WikiError(E.E_NO_EVIDENCE, "页面必须至少引用一条事实编号")   # 拒绝
        try:                                                 # 复用证据闸门
            check_evidence([{"text": "ref", "fact_id": fid} for fid in fact_refs],
                           known_ids=self._known_fact_ids())   # 格式与存在性双检
        except GuardError as exc:                            # 闸门拒绝
            raise WikiError(exc.code, exc.msg)               # 转服务异常

    def list_pages(self, role: str, mode: str = "user") -> List[Dict[str, object]]:   # 列表
        """按模式列出页面。

        入参：role 角色；mode user/admin。
        出参：页面摘要列表。
        失败行为：管理员模式下无权限时抛 WikiError(E_PERM)。
        """
        if mode == WikiMode.ADMIN.value:                      # 管理员模式
            self._check_editor(role)                          # 需要编辑权限
            pages = list(self.store.pages.values())           # 全部页面
        else:                                                 # 用户模式
            pages = [p for p in self.store.pages.values()
                     if p.status == "published" and role in p.visibility]   # 只返回已发布且可见
        return [{"slug": p.slug, "title": p.title, "summary": p.summary,
                 "dimension": p.dimension.value, "status": p.status,
                 "version": p.version, "fact_refs": p.fact_refs} for p in sorted(pages, key=lambda x: x.slug)]   # 摘要

    def get_page(self, slug: str, role: str, mode: str = "user") -> Dict[str, object]:   # 详情
        """按模式读取单个页面。

        入参：slug 标识；role 角色；mode user/admin。
        出参：页面字典。
        失败行为：不存在 404 语义（E_SCHEMA），不可见或无权限抛 WikiError。
        """
        page = self.store.get(slug)                           # 取页面
        if page is None:                                      # 不存在
            raise WikiError(E.E_SCHEMA, "页面不存在：%s" % slug)   # 抛出
        if mode == WikiMode.ADMIN.value:                      # 管理员模式
            self._check_editor(role)                          # 编辑权限
        else:                                                 # 用户模式
            if page.status != "published" or role not in page.visibility:   # 未发布或不可见
                raise WikiError(E.E_PERM, "该页面未发布或对当前角色不可见")   # 拒绝
        return page.model_dump()                              # 返回

    def create(self, role: str, payload: Dict[str, object]) -> Dict[str, object]:   # 创建
        """创建草稿页面。

        入参：role 角色；payload 含 slug/title/body/dimension/fact_refs/visibility。
        出参：页面字典。
        失败行为：权限不足或引用非法时抛 WikiError。
        """
        self._check_editor(role)                              # 权限
        refs = [str(x) for x in payload.get("fact_refs", [])]  # 规范化引用
        self._check_refs(refs)                                # 引用校验
        slug = str(payload.get("slug", "")).strip()           # 取标识
        if slug in self.store.pages:                          # 已存在
            raise WikiError(E.E_SCHEMA, "页面已存在：%s" % slug)   # 拒绝覆盖
        dimension = Dimension(str(payload.get("dimension", Dimension.FACT.value)))   # 维度
        page = WikiPage(slug=slug, title=str(payload.get("title", "")),
                        summary=str(payload.get("summary", "")),
                        body=str(payload.get("body", "")), dimension=dimension,
                        fact_refs=refs,
                        visibility=list(payload.get("visibility") or visible_roles(dimension)),
                        status="draft", version=1, owner=role)   # 新建草稿
        saved = self.store.put(page, action="create", role=role, detail="创建草稿")   # 保存
        return saved.model_dump()                             # 返回

    def update(self, role: str, slug: str, payload: Dict[str, object]) -> Dict[str, object]:   # 更新
        """更新页面内容并升版本。

        入参：role 角色；slug 标识；payload 需含 body。
        出参：页面字典。
        失败行为：权限不足、页面不存在或引用非法时抛 WikiError。
        """
        self._check_editor(role)                              # 权限
        page = self.store.get(slug)                           # 取页面
        if page is None:                                      # 不存在
            raise WikiError(E.E_SCHEMA, "页面不存在：%s" % slug)   # 抛出
        refs = [str(x) for x in payload.get("fact_refs", page.fact_refs)]   # 引用可继承
        self._check_refs(refs)                                # 引用校验
        updated = page.model_copy(update={
            "title": str(payload.get("title", page.title)),
            "summary": str(payload.get("summary", page.summary)),
            "body": str(payload.get("body", page.body)),
            "fact_refs": refs,
            "visibility": list(payload.get("visibility", page.visibility)),
            "version": page.version + 1})                     # 升版本
        saved = self.store.put(updated, action="update", role=role, detail="内容更新")   # 保存
        return saved.model_dump()                             # 返回

    def publish(self, role: str, slug: str) -> Dict[str, object]:   # 发布
        """把草稿发布给用户模式可见。

        入参：role 角色；slug 标识。
        出参：页面字典。
        失败行为：非管理员或页面不存在时抛 WikiError。
        """
        # 原因：发布等于对外承诺，必须由管理员签核，工程角色可以写但不能自己放行
        if role not in PUBLISH_ROLES:                         # 非管理员
            raise WikiError(E.E_HUMAN_REQUIRED, "发布需管理员签核")   # 拒绝
        page = self.store.get(slug)                           # 取页面
        if page is None:                                      # 不存在
            raise WikiError(E.E_SCHEMA, "页面不存在：%s" % slug)   # 抛出
        published = page.model_copy(update={"status": "published", "version": page.version + 1})   # 升版本并发布
        saved = self.store.put(published, action="publish", role=role, detail="发布")   # 保存
        return saved.model_dump()                             # 返回

    def rollback(self, role: str, slug: str, version: int) -> Dict[str, object]:   # 回滚
        """回滚到指定历史版本，回滚本身也生成新版本。

        入参：role 角色；slug 标识；version 目标版本。
        出参：页面字典。
        失败行为：非管理员、页面或版本不存在时抛 WikiError。
        """
        if role not in PUBLISH_ROLES:                         # 非管理员
            raise WikiError(E.E_PERM, "回滚需管理员权限")        # 拒绝
        page = self.store.get(slug)                           # 取页面
        snapshot = self.store.revision(slug, version)          # 取快照
        if page is None or snapshot is None:                  # 任一缺失
            raise WikiError(E.E_SCHEMA, "页面或版本不存在")     # 抛出
        restored = page.model_copy(update={"title": snapshot.title, "body": snapshot.body,
                                           "status": snapshot.status,
                                           "version": page.version + 1})   # 用快照内容生成新版本
        saved = self.store.put(restored, action="rollback", role=role,
                               detail="回滚到 v%d" % version)   # 保存
        return saved.model_dump()                             # 返回

    def draft_from_facts(self, role: str, dimension: str, limit: int = 10) -> Dict[str, object]:   # 由事实生成草稿
        """把某一维的事实聚合成 Wiki 草稿，供管理员再编辑。

        入参：role 角色；dimension 维度；limit 最多条目。
        出参：新草稿页面。
        失败行为：权限不足或维度无数据时抛 WikiError。
        """
        self._check_editor(role)                              # 权限
        target = Dimension(dimension)                         # 维度枚举
        rows: Dict[str, Dict[str, str]] = {}                  # 按事实编号聚合
        for chunk in self.knowledge.chunks:                   # 遍历片段
            if chunk.dimension != target:                     # 维度不符
                continue                                      # 跳过
            row = rows.setdefault(chunk.fact_id, {"role": "", "text": ""})   # 初始化行
            if not row["text"]:                               # 只取首片段摘要
                row["text"] = chunk.text                          # 记录
                row["role"] = chunk.text.split("：", 1)[0]        # 取角色前缀
        if not rows:                                          # 无数据
            raise WikiError(E.E_SCHEMA, "该维度暂无可聚合事实")    # 抛出
        picked = sorted(rows.items())[:max(1, limit)]          # 取前 N 条
        body = "\n".join("- **%s**（%s）：%s" % (fid, item["role"], item["text"])
                         for fid, item in picked)              # 生成正文
        payload = {"slug": "draft-%s-facts" % target.value, "title": "%s维度事实草稿" % target.value,
                   "summary": "由知识库自动聚合，需管理员核对后发布",
                   "body": body, "dimension": target.value,
                   "fact_refs": [fid for fid, _ in picked]}    # 组装载荷
        if payload["slug"] in self.store.pages:               # 已存在则升版本
            return self.update(role, str(payload["slug"]), {"body": body,
                                                             "fact_refs": payload["fact_refs"]})   # 更新
        return self.create(role, payload)                      # 新建

    def audit(self, role: str) -> List[Dict[str, object]]:     # 审计
        """返回审计记录，仅管理员可见。

        入参：role 角色。
        出参：审计列表。
        失败行为：无权限时抛 WikiError(E_PERM)。
        """
        # 原因：审计记录含角色与操作轨迹，一线账号不应看到审批与发布细节
        if role not in PUBLISH_ROLES:                          # 非管理员
            raise WikiError(E.E_PERM, "审计记录仅管理员可见")     # 拒绝
        return [entry.model_dump() for entry in self.store.audit]   # 返回
