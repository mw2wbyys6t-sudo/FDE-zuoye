# -*- coding: utf-8 -*-
"""打包静态演示版：把 app/web 与 mock.js 组装成可直接发布的 public 目录。"""

import argparse                                              # 参数
import shutil                                                # 复制
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[2]                    # 仓库根
WEB = ROOT / "fde-agent" / "app" / "web"                      # 源前端
MOCK = Path(__file__).resolve().parent / "mock.js"             # 演示拦截脚本
ASSETS = ("index.html", "styles.css", "app.js")               # 必需资源
BANNER = ('<div class="demo-banner">演示模式 · 数据为合成样例，不连接后端，'
          '不代表真实业务结果</div>')                          # 顶部横幅
BANNER_CSS = ("\n/* 演示横幅：置于页面顶部，明确数据性质 */\n"
              ".demo-banner{background:#fff8e1;color:#7a5b00;border-bottom:1px solid #f0d98a;"
              "padding:8px 16px;font-size:12px;text-align:center}\n")   # 横幅样式


def build(out_dir: Path) -> int:                              # 构建
    """组装演示包并返回文件数。

    入参：out_dir 输出目录。
    出参：写入文件数。
    失败行为：源文件缺失时抛 FileNotFoundError。
    """
    public = out_dir / "public"                                # 发布目录
    if public.exists():                                        # 清理旧产物
        shutil.rmtree(public)                                  # 删除
    public.mkdir(parents=True)                                 # 新建
    for name in ASSETS:                                        # 复制前端资源
        src = WEB / name                                       # 源
        if not src.exists():                                   # 缺文件
            raise FileNotFoundError(str(src))                  # 直接失败
        shutil.copy2(src, public / name)                       # 复制
    shutil.copy2(MOCK, public / "mock.js")                      # 复制拦截脚本

    index = public / "index.html"                              # 首页
    html = index.read_text(encoding="utf-8")                    # 读取
    html = html.replace('<script src="app.js"></script>',
                        '<script src="mock.js"></script>\n<script src="app.js"></script>')   # 先 mock 后业务
    if BANNER not in html:                                     # 避免重复插入
        html = html.replace('<div class="app">', BANNER + "\n<div class=\"app\">")   # 插入横幅
    html = html.replace("<title>FDE Agent Console</title>",
                        "<title>FDE Agent Console · 演示</title>")   # 标题标注演示
    index.write_text(html, encoding="utf-8")                    # 写回

    css = public / "styles.css"                                # 样式
    text = css.read_text(encoding="utf-8")                      # 读取
    if ".demo-banner" not in text:                              # 避免重复
        css.write_text(text + BANNER_CSS, encoding="utf-8")      # 追加横幅样式
    return len(list(public.rglob("*")))                         # 返回条目数


def main() -> int:                                             # 入口
    """命令行入口。

    入参：--out 输出目录，默认 deploy/static-demo/dist。
    出参：0 成功。
    失败行为：异常转为非零退出码。
    """
    parser = argparse.ArgumentParser(description="构建静态演示包")   # 参数
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "dist"))   # 输出
    args = parser.parse_args()                                  # 解析
    out = Path(args.out)                                        # 路径
    try:                                                        # 构建
        count = build(out)                                      # 执行
    except FileNotFoundError as exc:                            # 缺文件
        print("FAIL 缺少源文件：%s" % exc)                       # 提示
        return 2                                                # 退出
    index = out / "public" / "index.html"                       # 校验入口
    ok = index.exists() and index.stat().st_size > 0             # 非空
    print("%s 输出 %s，条目 %d，index=%d 字节"
          % ("PASS" if ok else "FAIL", out / "public", count,
             index.stat().st_size if index.exists() else 0))     # 结果
    return 0 if ok else 1                                        # 退出码


if __name__ == "__main__":                                      # 直接运行
    sys.exit(main())                                            # 返回退出码
