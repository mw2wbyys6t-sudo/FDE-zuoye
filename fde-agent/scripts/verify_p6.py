# -*- coding: utf-8 -*-
"""P6 验证脚本：MVP 前端静态审查 + 与后端接口对齐。"""

import re                                                     # 提取前端调用
import sys                                                    # 退出码
from pathlib import Path                                      # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from fastapi.testclient import TestClient                     # 接口
from app.main import app                                      # 应用

WEB = ROOT / "app" / "web"                                    # 前端目录
RESULTS = []                                                  # 结果
client = TestClient(app)                                      # 客户端


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def main() -> int:                                             # 入口
    """执行 P6 全部验证。

    入参：无。
    出参：0 全通过，1 有失败。
    失败行为：异常向上抛出。
    """
    html = (WEB / "index.html").read_text(encoding="utf-8")     # 首页
    js = (WEB / "app.js").read_text(encoding="utf-8")           # 脚本
    css = (WEB / "styles.css").read_text(encoding="utf-8")      # 样式
    check("三个静态文件存在", all((WEB / n).exists() for n in ("index.html", "app.js", "styles.css")), "files")   # 存在
    ids = re.findall(r'id="([^"]+)"', html)                     # 所有 id
    check("页面 id 无重复", len(ids) == len(set(ids)), str(len(ids)))   # 重复 id 会破坏绑定
    uses = set(re.findall(r'\$\("#([a-z0-9\-]+)"\)', js))       # JS 引用的 id
    missing = [x for x in uses if x not in set(ids)]            # 引用了不存在的 id
    check("JS 引用 id 均存在", not missing, str(missing[:5]))   # 死引用
    check("脚本无未定义 lucide 依赖", "lucide" not in js.lower(), "no-cdn")   # 不依赖 CDN
    check("样式包含响应式断点", "@media" in css, "media")       # 窄屏适配
    scenes = re.findall(r'data-scene="([^"]+)"', html)          # 场景按钮
    check("现场执行提供场景预设", len(scenes) >= 4 and "applyScene" in js, str(scenes))   # 不直白体现
    check("高级字段默认折叠", "<details" in html and "高级字段" in html, "details")   # 渐进披露

    resp = client.get("/ui/")                                   # 首页
    check("GET /ui/ 200", resp.status_code == 200 and "FDE Agent Console" in resp.text, str(resp.status_code))   # 首页
    redirect = client.get("/", follow_redirects=False)          # 根路径
    check("GET / 跳转 /ui/", redirect.status_code in (307, 302) and redirect.headers["location"] == "/ui/", "redirect")   # 跳转

    used = set(re.findall(r'api\("([^"]+)"', js))               # 前端调用的接口
    required = ["/health", "/kb/stats", "/memory/stats", "/tasks", "/wiki/pages", "/wiki/audit",
                "/exec/scan", "/exec/metrics"]                        # 必须存在的前端调用
    check("前端覆盖关键接口", all(any(u.startswith(r) for u in used) for r in required), str(sorted(used)[:6]))   # 覆盖度

    # 角色与权限：前端带 X-Role，后端必须对越权返回 403
    denied = client.get("/v1/wiki/pages?mode=admin", headers={"X-Role": "viewer"})   # 越权
    check("越权访问返回 403 且三键结构", denied.status_code == 403
          and set(denied.json().keys()) == {"ok", "data", "error"}, str(denied.status_code))   # 结构
    health = client.get("/v1/health", headers={"X-Role": "engineer"})   # 正常
    check("正常请求返回 ok", health.status_code == 200 and health.json()["ok"] is True, "health")   # 正常

    failed = [name for name, ok in RESULTS if not ok]           # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
