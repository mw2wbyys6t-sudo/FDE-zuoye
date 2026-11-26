# 静态演示包

把 `fde-agent/app/web` 的前端与浏览器内 mock 拦截层组装成可直接发布的静态站点。用于在没有 Python 运行时的环境下演示控制台界面。

## 构建

```bash
python deploy/static-demo/build_demo.py
# 输出：deploy/static-demo/dist/public/{index.html,styles.css,app.js,mock.js}
```

打开 `dist/public/index.html` 即可离线浏览（`file://` 亦可，因为没有任何网络请求）。

## 它做了什么

| 文件 | 作用 |
|---|---|
| `mock.js` | 拦截 `/v1` 的 fetch，用内存数据实现概览、任务编排、Wiki 双模式、记忆审计、现场执行五组接口 |
| `build_demo.py` | 复制前端资源，在 `app.js` 前注入 `mock.js`，插入演示横幅与对应样式 |
| `dist/public/` | 构建产物，可直接上传到任意静态托管 |

## 边界（必须保留）

- **数据是内存里的合成样例**，刷新页面即重置，不落库、不落盘。
- 顶部横幅明确标注"演示模式"，不得删除后再对外展示。
- 规则判定与后端 `app/execution/rules.py` 的 R1–R4 对齐，但**不含真实数据校验**，不能用于验收。
- 这是演示外壳，不是系统本体；真实系统需运行 `fde-agent`（Python/FastAPI）。

## 已部署实例

`https://37ko78czrou73h0ul8b.traesite.cn`（仅自己可见），内容与本目录构建产物一致。
