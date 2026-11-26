// 前端入口：零构建原生 JS，所有数据来自 /v1 接口
const $ = (sel) => document.querySelector(sel);                 // 选择器简写
const state = { role: "engineer", view: "overview", taskId: "", wikiMode: "user", slug: "", decisionId: "" }; // 页面状态

// 统一请求：自动带 X-Role，统一解析 {ok,data,error}
async function api(path, options = {}) {
  const headers = Object.assign({ "X-Role": state.role }, options.headers || {}); // 角色走请求头
  if (options.body) headers["Content-Type"] = "application/json";                 // 有体才设类型
  const resp = await fetch("/v1" + path, {                             // 拼接前缀
    method: options.method || "GET",                                   // 默认 GET
    headers,                                                       // 请求头
    body: options.body ? JSON.stringify(options.body) : undefined,     // 序列化
  });
  const payload = await resp.json().catch(() => ({ ok: false, error: { code: "E_PARSE", msg: "响应不是 JSON" } })); // 容错
  if (!payload.ok) {                                                   // 业务失败
    const err = new Error(payload.error?.msg || "请求失败");            // 组装错误
    err.code = payload.error?.code || "E_UNKNOWN";                     // 错误码
    err.status = resp.status;                                          // HTTP 状态
    throw err;                                                        // 抛出给调用方
  }
  return payload.data;                                                 // 返回业务数据
}

// 顶栏状态与视图切换
function setStatus(text, kind = "") {
  const el = $("#status");                                             // 状态节点
  el.textContent = text;                                               // 文案
  el.className = "status " + kind;                                     // 颜色类
}

function switchView(view) {
  state.view = view;                                                   // 记录当前视图
  document.querySelectorAll(".nav-item").forEach((btn) => {            // 导航高亮
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((el) => {                 // 视图显隐
    el.classList.toggle("hidden", el.id !== "view-" + view);
  });
  $("#crumbs").textContent = ({ overview: "概览", tasks: "任务编排", wiki: "知识 Wiki",
    memory: "记忆与审计", exec: "现场执行" })[view];               // 面包屑
  const loaders = { overview: loadOverview, tasks: refreshTask, wiki: loadWiki,
    memory: loadMemory, exec: loadExec };                          // 路由表
  loaders[view]?.();                                                    // 触发加载
}

// 概览：四张卡
async function loadOverview() {
  try {
    const [health, kb, mem, wiki] = await Promise.all([                 // 并行拉取
      api("/health"),                                                   // 健康
      api("/kb/stats"),                                                 // 知识库
      api("/memory/stats"),                                             // 记忆
      api("/wiki/pages?mode=" + (state.role === "admin" ? "admin" : "user")), // 页面
    ]);
    $("#m-health").textContent = health.status.toUpperCase();           // 状态值
    $("#m-env").textContent = "env=" + health.env + " · provider=" + health.model_provider; // 环境
    $("#m-facts").textContent = kb.facts;                               // 事实数
    $("#m-dims").textContent = Object.entries(kb.dimensions).map(([k, v]) => k + " " + v).join(" · "); // 维度分布
    $("#m-mem").textContent = mem.total;                                // 记忆数
    $("#m-conflict").textContent = "冲突 " + mem.conflicts + " · " + JSON.stringify(mem.layers); // 分层
    $("#m-wiki").textContent = wiki.count;                              // 页面数
    setStatus("已连接", "ok");                                          // 顶栏
  } catch (err) {                                                       // 失败
    setStatus(err.code + "：" + err.message, "err");                     // 显示错误
  }
}

// 任务：创建并执行
async function createTask() {
  try {
    const task = await api("/tasks", { method: "POST" });               // 创建
    state.taskId = task.task_id;                                        // 记住编号
    renderTask(task);                                                   // 渲染
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function runTask() {
  if (!state.taskId) { setStatus("请先新建任务", "err"); return; }      // 前置校验
  try {
    const task = await api("/tasks/" + state.taskId + "/run", { method: "POST", body: {} }); // 执行
    renderTask(task);                                                   // 渲染
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function refreshTask() {
  if (!state.taskId) { $("#task-meta").textContent = "尚未创建任务"; return; } // 无任务
  try { renderTask(await api("/tasks/" + state.taskId)); return; }      // 拉取
  catch (err) { state.taskId = ""; $("#task-meta").textContent = "任务不存在，请新建"; } // 失效
}

const STEP_ORDER = ["conflicts", "baseline", "design", "verify"];      // 固定步骤
function renderTask(task) {
  $("#task-meta").textContent = "task_id=" + task.task_id + " · state=" + task.state + " · 角色=" + task.role; // 元信息
  const done = new Set(task.done_steps || []);                          // 已完成集合
  $("#task-steps").innerHTML = STEP_ORDER.map((s) =>                          // 渲染步骤
    `<span class="step ${done.has(s) ? "done" : ""}">${s}</span>`).join("");
  const gate = task.gate;                                               // 签核信息
  $("#task-gate").hidden = !gate || gate.status !== "pending";          // 有待签核才显示
  if (gate) {                                                           // 渲染签核卡
    $("#g-reason").textContent = "原因：" + gate.reason + " · 需要角色：" + gate.required_roles.join("/");
    $("#g-result").textContent = gate.status === "pending" ? "" : "已由 " + gate.decided_by + " 于 " + gate.decided_at + " 处理";
  }
  const design = task.payload?.design;                                  // 方案
  $("#task-design").hidden = !design;                                   // 有方案才显示
  if (!design) return;                                                  // 提前结束
  $("#d-scope").textContent = design.pilot_scope;                       // 范围
  $("#d-rules").innerHTML = design.rules.map((r) => `<li>${r.rule_id} ${r.trigger}</li>`).join("");       // 规则
  $("#d-accept").innerHTML = design.acceptance.map((x) => `<li>${x}</li>`).join("");                     // 验收
  $("#d-boundary").innerHTML = design.boundary.map((x) => `<li>${x}</li>`).join("");                     // 边界
  $("#d-questions").innerHTML = (design.open_questions || []).slice(0, 6).map((x) => `<li>${x}</li>`).join(""); // 待答
}

async function decideGate(decision) {
  if (!state.taskId) return;                                            // 前置
  try {
    const task = await api("/tasks/" + state.taskId + "/gate/decide", {  // 签核
      method: "POST", body: { decision, note: $("#g-note").value || "" },
    });
    renderTask(task);                                                   // 刷新
    setStatus("签核完成：" + decision, "ok");                            // 提示
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

// Wiki：双模式列表与详情
async function loadWiki() {
  const isAdmin = state.wikiMode === "admin";                           // 是否管理员模式
  $("#wiki-editor").hidden = !isAdmin;                                  // 编辑器只在管理员模式显示
  $("#wiki-hint").textContent = isAdmin                                    // 模式说明
    ? "管理员模式：可见草稿与已发布页面，可创建、发布、回滚。"
    : "用户模式：只读已发布且当前角色可见的页面。";
  try {
    const data = await api("/wiki/pages?mode=" + state.wikiMode);       // 拉列表
    $("#wiki-list").innerHTML = data.pages.length ? data.pages.map((p) =>   // 渲染
      `<li data-slug="${p.slug}" class="${state.slug === p.slug ? "active" : ""}">` +
      `${p.title}<br><span class="tag">${p.dimension}</span> <span class="hint">${p.status} v${p.version}</span></li>`
    ).join("") : `<li class="hint">暂无页面</li>`;
    document.querySelectorAll("#wiki-list li[data-slug]").forEach((li) => { // 绑定点击
      li.onclick = () => openPage(li.dataset.slug);                     // 打开详情
    });
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function openPage(slug) {
  state.slug = slug;                                                    // 记录
  try {
    const page = await api("/wiki/pages/" + slug + "?mode=" + state.wikiMode); // 拉详情
    const actions = state.wikiMode === "admin"                                // 管理员可见操作
      ? `<div class="row"><button class="btn primary" onclick="publishPage()">发布</button>` +
        `<button class="btn" onclick="rollbackPage()">回滚到 v1</button></div>` : "";
    $("#wiki-detail").innerHTML =                                        // 渲染
      `<h4>${page.title}</h4><p class="hint">${page.summary || ""} · 证据 ${page.fact_refs.join(",")} · v${page.version} · ${page.status}</p>` +
      `<pre>${page.body}</pre>` + actions;
    loadWiki();                                                          // 刷新高亮
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function publishPage() {
  try {
    await api("/wiki/pages/" + state.slug + "/publish", { method: "POST" }); // 发布
    setStatus("已发布", "ok");                                           // 提示
    openPage(state.slug);                                                // 刷新详情
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function rollbackPage() {
  try {
    await api("/wiki/pages/" + state.slug + "/rollback/1", { method: "POST" }); // 回滚 v1
    setStatus("已回滚", "ok");                                           // 提示
    openPage(state.slug);                                                // 刷新
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function saveDraft() {
  const body = {                                                         // 组装载荷
    slug: $("#w-slug").value.trim(), title: $("#w-title").value.trim(),
    summary: "", body: $("#w-body").value.trim(), dimension: $("#w-dim").value,
    fact_refs: $("#w-refs").value.split(",").map((x) => x.trim()).filter(Boolean),
  };
  try {
    const page = await api("/wiki/pages", { method: "POST", body });     // 创建
    $("#w-result").textContent = "已创建草稿 v" + page.version + "，可点击发布"; // 提示
    state.slug = page.slug;                                              // 记录
    loadWiki();                                                          // 刷新列表
  } catch (err) { $("#w-result").textContent = err.code + "：" + err.message; } // 错误
}

// 记忆与审计
async function loadMemory() {
  try {
    const stats = await api("/memory/stats");                            // 统计
    $("#mem-stats").textContent = "总数 " + stats.total + " · 分层 " + JSON.stringify(stats.layers) +
      " · 冲突 " + stats.conflicts;
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function writeMemory() {
  const body = {                                                         // 组装载荷
    layer: $("#mem-layer").value, text: $("#mem-text").value.trim(),
    fact_refs: $("#mem-refs").value.split(",").map((x) => x.trim()).filter(Boolean),
    verified: $("#mem-verified").value === "true",
  };
  try {
    const result = await api("/memory/write", { method: "POST", body });  // 写入
    $("#mem-result").textContent = "已写入 " + result.memory_id + (result.conflict ? "（标记冲突）" : ""); // 提示
    loadMemory();                                                        // 刷新统计
  } catch (err) { $("#mem-result").textContent = err.code + "：" + err.message; } // 错误
}

async function searchMemory() {
  try {
    const data = await api("/memory/search", { method: "POST", body: { query: $("#mem-query").value || "取消" } }); // 检索
    $("#mem-hits").innerHTML = data.items.map((m) =>                      // 渲染命中
      `<li>${m.layer} · ${m.text} <span class="tag">${m.fact_refs.join(",") || "无编号"}</span></li>`).join("");
  } catch (err) { setStatus(err.code + "：" + err.message, "err"); }    // 错误
}

async function loadAudit() {
  try {
    const data = await api("/wiki/audit");                               // 审计
    $("#audit-body").innerHTML = data.entries.slice().reverse().map((e) => // 倒序渲染
      `<tr><td>${e.created_at.slice(5, 19)}</td><td>${e.action}</td><td>${e.slug}</td><td>${e.role}</td><td>v${e.version}</td></tr>`
    ).join("");
  } catch (err) {                                                         // 非管理员会 403
    $("#audit-body").innerHTML = `<tr><td colspan="5" class="hint">${err.code}：${err.message}</td></tr>`;
  }
}

// 现场执行：判定 → 提示/挂起 → 处置闭环 → 指标
async function loadExec() {
  try {
    const m = await api("/exec/metrics");                               // 指标
    $("#x-scans").textContent = m.scans;                                // 判定次数
    $("#x-rules").textContent = "规则版本 " + m.rule_version + " · " + JSON.stringify(m.by_rule); // 分规则
    $("#x-levels").textContent = m.hints + " / " + m.holds;             // 提示/挂起
    $("#x-unresolved").textContent = m.unresolved_holds;                // 未闭环
    $("#x-overdue").textContent = "超时 " + m.overdue_holds + " · 去重 " + m.dedupe_hits; // 超时与去重
    $("#x-closure").textContent = (m.closure_rate * 100).toFixed(0) + "%"; // 闭环率
  } catch (err) { $("#x-error").textContent = err.code + "：" + err.message; } // 无权限时提示
}

// 场景预设：一线只选情况，不面对字段；技术细节留在「高级字段」里
const SCENES = {
  normal:    { spec: "500ml", neighbors: "",      cancelled: "false", available: "true",  note: "",       attached: "true"  }, // 正常拣选
  similar:   { spec: "500ml", neighbors: "750ml", cancelled: "false", available: "true",  note: "",       attached: "true"  }, // 相似包装
  cancelled: { spec: "500ml", neighbors: "750ml", cancelled: "true",  available: "true",  note: "",       attached: "true"  }, // 订单已取消
  system:    { spec: "500ml", neighbors: "750ml", cancelled: "false", available: "false", note: "",       attached: "true"  }, // 系统中断
  note:      { spec: "500ml", neighbors: "750ml", cancelled: "false", available: "true",  note: "易碎品优先", attached: "false" }, // 说明未随单
};

function applyScene(name) {
  const preset = SCENES[name];                                          // 取预设
  if (!preset) return;                                                 // 未知场景
  $("#x-spec").value = preset.spec;                                     // 规格
  $("#x-neighbors").value = preset.neighbors;                           // 相邻规格
  $("#x-cancelled").value = preset.cancelled;                           // 取消状态
  $("#x-available").value = preset.available;                           // 系统可用
  $("#x-note").value = preset.note;                                     // 说明文本
  $("#x-attached").value = preset.attached;                             // 说明是否随单
  document.querySelectorAll("#x-scenes .btn").forEach((btn) => {        // 高亮当前场景
    btn.classList.toggle("primary", btn.dataset.scene === name);
  });
}

async function doScan() {
  const ctx = {                                                         // 组装上下文
    biz_id: $("#x-biz").value.trim(), sku: $("#x-sku").value.trim(),
    base_sku: $("#x-base").value.trim(), spec: $("#x-spec").value.trim(),
    neighbor_specs: $("#x-neighbors").value.split(",").map((x) => x.trim()).filter(Boolean),
    cancelled: $("#x-cancelled").value === "true",
    system_available: $("#x-available").value === "true",
    note_text: $("#x-note").value.trim(),
    note_attached: $("#x-attached").value === "true",
    data_asof: $("#x-asof").value.trim(),
  };
  try {
    const decision = await api("/exec/scan", { method: "POST", body: { ctx } }); // 判定
    state.decisionId = decision.decision_id;                            // 记住编号
    $("#x-result").hidden = false;                                      // 显示结果
    const dedupeTip = decision.dedupe ? " · 刚已核对过，未重复出卡" : "";   // 去重提示
    $("#x-level").textContent = "判定：" + decision.level + " · 需人工：" +
      (decision.requires_human ? "是（" + decision.human_role + "）" : "否") + dedupeTip; // 结论
    $("#x-reasons").innerHTML = decision.reasons.length                        // 理由
      ? decision.reasons.map((r) => `<li><b>${r.rule_id}</b> ${r.message} <span class="tag">${r.fact_refs.join(",")}</span></li>`).join("")
      : "<li>未命中任何规则</li>";
    $("#x-dispose-row").hidden = decision.level === "pass";              // 放行不需要处置
    $("#x-error").textContent = "";                                     // 清空错误
    loadExec();                                                          // 刷新指标
  } catch (err) { $("#x-error").textContent = err.code + "：" + err.message; } // 错误
}

async function dispose(kind) {
  if (!state.decisionId) return;                                        // 无判定
  const body = {                                                        // 处置载荷
    decision_id: state.decisionId, action: kind,
    operator: $("#x-operator").value.trim(), reason: $("#x-reason").value.trim(),
    confirmed_at: $("#x-confirmed").value.trim(),
  };
  try {
    await api("/exec/dispositions", { method: "POST", body });           // 提交
    $("#x-dispose-msg").textContent = "已记录处置：" + kind;             // 提示
    loadExec();                                                          // 刷新
  } catch (err) { $("#x-dispose-msg").textContent = err.code + "：" + err.message; } // 缺三要素会在此显示
}

// 事件绑定：外壳只绑一次，视图内部用函数调用
document.querySelectorAll(".nav-item").forEach((btn) => {                // 导航
  btn.onclick = () => switchView(btn.dataset.view);                      // 切换
});
$("#role").onchange = (e) => {                                           // 角色切换
  state.role = e.target.value;                                          // 记录
  switchView(state.view);                                               // 重新加载当前视图
};
document.querySelectorAll("#wiki-mode .seg-item").forEach((btn) => {     // 模式切换
  btn.onclick = () => {
    state.wikiMode = btn.dataset.mode;                                   // 记录模式
    document.querySelectorAll("#wiki-mode .seg-item").forEach((b) => b.classList.toggle("active", b === btn)); // 高亮
    loadWiki();                                                          // 重新加载
  };
});
$("#btn-create").onclick = createTask;                                    // 新建任务
$("#btn-run").onclick = runTask;                                          // 执行
$("#btn-refresh").onclick = refreshTask;                                  // 刷新
$("#btn-approve").onclick = () => decideGate("approve");                  // 批准
$("#btn-reject").onclick = () => decideGate("reject");                    // 驳回
$("#btn-wiki-save").onclick = saveDraft;                                  // 保存草稿
$("#btn-mem-write").onclick = writeMemory;                                // 写入记忆
$("#btn-mem-search").onclick = searchMemory;                              // 检索记忆
$("#btn-mem-stats").onclick = loadMemory;                                 // 刷新统计
$("#btn-audit").onclick = loadAudit;                                      // 加载审计
$("#btn-x-scan").onclick = doScan;                                        // 执行判定
document.querySelectorAll("#x-scenes .btn").forEach((btn) => {            // 场景按钮
  btn.onclick = () => applyScene(btn.dataset.scene);                      // 一键填充
});
$("#btn-x-metrics").onclick = loadExec;                                   // 刷新指标
$("#btn-x-accept").onclick = () => dispose("accept");                     // 采纳
$("#btn-x-override").onclick = () => dispose("override");                 // 覆盖闭环

applyScene("similar");                                                    // 默认高亮「相似包装」
switchView("overview");                                                   // 默认进入概览
