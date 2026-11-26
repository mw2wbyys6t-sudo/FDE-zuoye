# -*- coding: utf-8 -*-
"""前端测试：静态挂载、根路径跳转与页面关键节点存在。"""

from fastapi.testclient import TestClient                     # 进程内客户端
from app.main import app                                       # 应用

client = TestClient(app)                                      # 全局客户端


def test_root_redirects_to_ui():                               # 根路径跳转
    """验证访问 / 会跳到控制台。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.get("/", follow_redirects=False)              # 不跟随重定向
    assert resp.status_code in (307, 302)                       # 重定向状态
    assert resp.headers["location"] == "/ui/"                   # 目标地址


def test_ui_index_served():                                    # 首页
    """验证 /ui/ 返回控制台页面。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    resp = client.get("/ui/")                                   # 访问首页
    assert resp.status_code == 200                              # 成功
    assert "FDE Agent Console" in resp.text                     # 标题正确


def test_assets_served():                                      # 静态资源
    """验证样式与脚本可访问。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    for name in ("styles.css", "app.js"):                       # 两个静态文件
        resp = client.get("/ui/" + name)                        # 请求
        assert resp.status_code == 200                          # 成功
        assert len(resp.text) > 200                             # 非空


def test_ui_contains_required_views():                          # 四个视图
    """验证四个视图容器与角色选择器存在。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    html = client.get("/ui/").text                             # 页面源码
    for anchor in ('id="view-overview"', 'id="view-tasks"', 'id="view-wiki"',
                   'id="view-memory"', 'id="role"'):            # 关键节点
        assert anchor in html                                   # 必须存在
