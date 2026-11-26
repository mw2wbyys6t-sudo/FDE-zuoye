// 演示模式：拦截 /v1 请求，用内置合成数据响应；不连接任何后端
(function () {
  const realFetch = window.fetch.bind(window);   // 先保存原始 fetch，避免被自身覆盖后递归
  // 演示库：全部为合成样例，仅用于界面演示
  const db = {
    tasks: {},                                                       // 任务
    wiki: [{ slug: "cancel-order-rule", title: "取消单拦截说明", summary: "取消状态必须在装车前可见",
             body: "装车前核对取消状态；提示不覆盖原记录；挂起须记录原因、接手人与确认时间。",
             dimension: "rule", fact_refs: ["f11", "f31"], status: "published", version: 2 }],   // 页面
    audit: [{ created_at: "2026-11-19T06:08:31Z", action: "publish", slug: "cancel-order-rule", role: "admin", version: 2 }],   // 审计
    mem: [{ layer: "semantic", text: "取消事件同步延迟 12 分钟，提示需回显数据截止时间", fact_refs: ["f31"], conflict: false }],   // 记忆
    scans: [],                                                        // 判定
    dispositions: [],                                                 // 处置
    dedupes: 0,                                                       // 去重次数
  };

  const ok = (data, status = 200) => ({ ok: true, status, json: async () => ({ ok: true, data, error: null }) });   // 成功响应
  const err = (status, code, msg) => ({ ok: false, status, json: async () => ({ ok: false, data: null, error: { code, msg } }) });   // 失败响应
  const id = (p) => p + "-" + Math.random().toString(16).slice(2, 10);   // 生成编号
  const now = () => new Date().toISOString();                            // 当前时间
  const role = (opts) => (opts.headers && (opts.headers["X-Role"] || opts.headers["x-role"])) || "viewer";   // 读取角色

  function evaluate(ctx) {                                                // 规则判定（对应后端 R1–R4）
    const reasons = [];                                                   // 理由集合
    if (!ctx.system_available) reasons.push({ rule_id: "R4", message: "关键系统不可用，已转人工，请记录原因与接手人", fact_refs: ["f44", "f35"] });
    if (ctx.cancelled) reasons.push({ rule_id: "R2", message: "该单已取消，请暂停并交波次计划员核对（状态可能滞后，截止 " + (ctx.data_asof || "未提供") + "）", fact_refs: ["f11", "f31"] });
    if (ctx.spec && (ctx.neighbor_specs || []).some((s) => s !== ctx.spec)) reasons.push({ rule_id: "R1", message: "同系列相邻货位存在不同规格，请核对包装与规格字段", fact_refs: ["f10"] });
    if (ctx.note_text && !ctx.note_attached) reasons.push({ rule_id: "R3", message: "该单的说明只存在于便签或群消息，未随单据交接", fact_refs: ["f14", "f23"] });
    const holds = reasons.filter((r) => ["R2", "R4"].includes(r.rule_id));   // 需要人处置
    return { decision_id: id("dec"), biz_id: ctx.biz_id, level: !reasons.length ? "pass" : (holds.length ? "hold" : "hint"),
             reasons, requires_human: holds.length > 0,
             human_role: holds.some((r) => r.rule_id === "R2") ? "planner" : (holds.length ? "safety" : ""),
             data_asof: ctx.data_asof || "", rule_version: "exec-v1-demo", dedupe: false };
  }

  function designPayload() {                                             // 演示方案
    return {
      pilot_scope: "单仓区 · 相邻货位相似包装 SKU：拣选扫码解释 + 装车核验错配提醒（只提示，不阻断）",
      why: ["两处损害都发生在装车扫码之前（f11）", "提示不改原记录、可一键撤回（f15）", "同时作用于错发率与复核漏扫两条硬线（f02/f42）"],
      interfaces: ["WMS 拣选流水", "OMS 取消事件", "手持终端扫码事件", "只读接入，不回写业务库（f32）"],
      rules: [
        { rule_id: "R1", trigger: "同货位或相邻货位存在同系列不同规格 SKU", output: "并排展示规格差异字段", fallback: "字段缺失不出卡", fact_refs: ["f10"] },
        { rule_id: "R2", trigger: "业务编号存在取消事件且晚于该单可见状态", output: "提示已取消，暂停建议交波次计划员核对", fallback: "显示数据截止时间", fact_refs: ["f11", "f31"] },
        { rule_id: "R3", trigger: "拣选行存在便签或群消息中的非正式说明", output: "说明结构化进单据并随单流转", fallback: "超期标待刷新", fact_refs: ["f14", "f23"] },
        { rule_id: "R4", trigger: "资料缺依据、版本冲突或系统不可用", output: "转人工并记录三要素", fallback: "三要素缺一不予关闭", fact_refs: ["f44"] }],
      acceptance: ["错发率下降（口径已冻结）", "复核漏扫为零", "高位叉车 / 危险品 / 冷链规程未放宽（f42/f40）"],
      stop_conditions: ["触及停止条件即暂停试点，由负责人复盘（f42）", "出现自动审批或写库动作即终止（f41）"],
      boundary: ["不自动操作叉车、不做盘盈盘亏（f05/f52）", "不写业务库、不改货位与库存（f32）", "阻断型拦截须顾明岚与傅景书面批准（f34）"],
      open_questions: ["错发率存在多个数值，以哪一条口径为准？", "完成时点以出库还是正确收货为准？", "拣选与装车对错发的贡献占比未测"],
      fact_refs: ["f00", "f02", "f05", "f10", "f11", "f14", "f15", "f23", "f31", "f32", "f34", "f42", "f44"],
    };
  }

  function metrics() {                                                   // 演示指标
    const scans = db.scans;                                              // 判定
    const holds = scans.filter((d) => d.level === "hold");                // 挂起
    const closed = new Set(db.dispositions.map((x) => x.decision_id));    // 已处置
    const unresolved = holds.filter((d) => !closed.has(d.decision_id));    // 未闭环
    const byRule = {};                                                   // 分规则
    scans.forEach((d) => d.reasons.forEach((r) => { byRule[r.rule_id] = (byRule[r.rule_id] || 0) + 1; }));
    return { scans: scans.length, pass: scans.filter((d) => d.level === "pass").length,
             hints: scans.filter((d) => d.level === "hint").length, holds: holds.length,
             dispositions: db.dispositions.length, unresolved_holds: unresolved.length,
             overdue_holds: unresolved.length, dedupe_hits: db.dedupes,
             closure_rate: holds.length ? Number(((holds.length - unresolved.length) / holds.length).toFixed(3)) : 1.0,
             by_rule: byRule, rule_version: "exec-v1-demo", sources: { synthetic: scans.length } };
  }

  window.fetch = async function (url, opts = {}) {                        // 拦截入口
    const u = new URL(url, location.origin);                             // 解析地址
    if (!u.pathname.startsWith("/v1")) return realFetch(url, opts);       // 非 API 放行
    const path = u.pathname.slice(3);                                     // 去掉 /v1
    const method = (opts.method || "GET").toUpperCase();                  // 方法
    const body = opts.body ? JSON.parse(opts.body) : {};                  // 请求体
    const r = role(opts);                                                 // 角色

    if (path === "/health") return ok({ status: "up", env: "demo", model_provider: "mock", trace_dir: "不适用" });
    if (path === "/kb/stats") return ok({ facts: 36, dimensions: { fact: 10, rule: 11, indicator: 5, case: 10 } });
    if (path === "/memory/stats") return ok({ total: db.mem.length, layers: { semantic: db.mem.length }, conflicts: 1 });
    if (path === "/memory/search") return ok({ items: db.mem });
    if (path === "/memory/write") {                                       // 写入记忆
      if (r === "viewer") return err(403, "E_PERM", "该角色不允许写入记忆");
      db.mem.push({ layer: body.layer, text: body.text, fact_refs: body.fact_refs || [], conflict: false });
      return ok({ memory_id: id("mem"), conflict: false });
    }
    if (path === "/wiki/pages" && method === "GET") {                      // 页面列表
      const isAdmin = u.searchParams.get("mode") === "admin";             // 模式
      if (isAdmin && !["engineer", "admin", "safety"].includes(r)) return err(403, "E_PERM", "权限不足");
      const pages = isAdmin ? db.wiki : db.wiki.filter((p) => p.status === "published");
      return ok({ count: pages.length, pages });
    }
    if (path === "/wiki/audit") {                                          // 审计
      if (r !== "admin") return err(403, "E_PERM", "仅管理员可查看审计");
      return ok({ entries: db.audit });
    }
    if (path === "/wiki/pages" && method === "POST") {                     // 建草稿
      if (!["engineer", "admin"].includes(r)) return err(403, "E_PERM", "权限不足");
      const page = { slug: body.slug, title: body.title, summary: body.summary || "", body: body.body,
                     dimension: body.dimension, fact_refs: body.fact_refs || [], status: "draft", version: 1 };
      db.wiki.push(page);
      db.audit.push({ created_at: now(), action: "create", slug: page.slug, role: r, version: 1 });
      return ok(page);
    }
    const wikiMatch = path.match(/^\/wiki\/pages\/([^/]+)(?:\/(publish|rollback)\/?(\d+)?)?$/);
    if (wikiMatch) {
      const page = db.wiki.find((p) => p.slug === wikiMatch[1]);
      if (!page) return err(400, "E_SCHEMA", "页面不存在");
      if (!wikiMatch[2]) return ok(page);
      if (r !== "admin") return err(403, "E_PERM", wikiMatch[2] === "publish" ? "签核仅限管理员" : "回滚仅限管理员");
      page.status = wikiMatch[2] === "publish" ? "published" : page.status;
      page.version += 1;
      db.audit.push({ created_at: now(), action: wikiMatch[2], slug: page.slug, role: r, version: page.version });
      return ok(page);
    }
    if (path === "/tasks" && method === "POST") {                          // 建任务
      if (!["engineer", "admin"].includes(r)) return err(403, "E_PERM", "该角色不允许创建任务");
      const taskId = id("task");
      db.tasks[taskId] = { task_id: taskId, state: "created", role: r, payload: {}, done_steps: [], gate: null, history: [] };
      return ok(db.tasks[taskId]);
    }
    const taskMatch = path.match(/^\/tasks\/([^/]+)(?:\/(run|gate\/decide))?$/);
    if (taskMatch) {
      const task = db.tasks[taskMatch[1]];
      if (!task) return err(400, "E_SCHEMA", "任务不存在");
      if (!taskMatch[2]) return ok(task);
      if (taskMatch[2] === "run") {                                        // 执行四步
        if (!["engineer", "admin"].includes(r)) return err(403, "E_PERM", "权限不足");
        task.done_steps = ["conflicts", "baseline", "design", "verify"];
        task.payload = { conflicts: { conflicts: [{ kind: "definition", metric: "完成口径", values: ["仓内出库", "站点正确收货"], fact_refs: ["f50", "f53"], question: "完成时点以哪个为准？" }] },
                         baseline: { rows: [], tbd_count: 10 },
                         design: designPayload(),
                         verify: { passed: true, items: [] } };
        task.state = "awaiting_gate";
        task.gate = { gate_id: id("gate"), reason: "方案审核通过，进入单仓区并行试点需签核",
                      required_roles: ["safety", "admin"], status: "pending", decided_by: "", decided_at: "", note: "" };
        task.history.push({ step: "verify", at: now() });
        return ok(task);
      }
      if (!["safety", "admin"].includes(r)) return err(403, "E_PERM", "签核仅限安全或管理员");   // 签核
      if (!task.gate || task.gate.status !== "pending") return err(403, "E_HUMAN_REQUIRED", "当前没有待签核项");
      const approve = body.decision === "approve";
      task.gate.status = approve ? "approved" : "rejected";
      task.gate.decided_by = r; task.gate.decided_at = now(); task.gate.note = body.note || "";
      task.state = approve ? "approved" : "rejected";
      return ok(task);
    }
    if (path === "/exec/metrics") return ok(metrics());
    if (path === "/exec/events") return ok({ items: db.scans.slice(-Number(u.searchParams.get("limit") || 20)) });
    if (path === "/exec/scan" && method === "POST") {                       // 判定
      if (r === "viewer") return err(403, "E_PERM", "该角色不允许此操作");
      const decision = evaluate(body.ctx || {});
      db.scans.push(decision);
      return ok(decision);
    }
    if (path === "/exec/dispositions" && method === "POST") {               // 处置
      const target = db.scans.find((d) => d.decision_id === body.decision_id);
      if (!target) return err(400, "E_SCHEMA", "判定不存在");
      if (target.requires_human && (!body.operator || !body.reason || !body.confirmed_at)) {
        return err(403, "E_HUMAN_REQUIRED", "挂起单必须提供 operator、reason、confirmed_at");
      }
      db.dispositions.push({ decision_id: body.decision_id, action: body.action });
      return ok({ disposition_id: id("dsp"), decision_id: body.decision_id, action: body.action, closed: true });
    }
    return err(404, "E_NOT_FOUND", "演示模式未实现的接口：" + path);           // 兜底
  };
})();
