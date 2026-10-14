---
name: seo-autopilot
description: 生产级多租户SEO自动化平台，具有真实爬虫、60+文档化问题检测器、GEO审计、llms.txt验证、IndexNow支持、主题权威度分析和AI驱动的修复生成。当用户要求"审计我的网站"、"SEO分析"、"网站爬取"、"生成SEO报告"或提及自动化SEO工具时使用。
---

# SEO Autopilot

**生产级、多租户SEO自动化平台**，具有真实爬虫、60+文档化问题检测器、GEO审计、llms.txt验证、IndexNow支持、主题权威度分析和AI驱动的修复生成。

> 抓取网站，在11个分析维度检测SEO问题，按ROI优先排序，并生成可操作的修复方案——全部来自单个CLI命令。

## 核心功能

SEO Autopilot 将原始网页抓取数据转化为**优先行动方案**：

1. **网站爬取** – httpx + BeautifulSoup，SPAs自动Playwright回退，sitemap.xml发现，解析14+ HTML属性
2. **获取真实数据** – Google Search Console（28天）、PageSpeed Insights（INP/LCP/CLS通过CrUX）、robots.txt
3. **11个维度分析** – 页面、canonical、重定向、schema、GEO、llms.txt/ai.txt、主题权威、重复内容、链接图、CWV、安全
4. **检测60+问题类型** – 从缺失标题到AI爬虫阻止、llms.txt验证、IndexNow、canonical链、薄内容、关键词蚕食
5. **按ROI优先排序** – 快速见效（<30分钟）、本周任务、积压工作——按影响x置信度x易度排序
6. **生成修复** – Claude API编写优化的标题、元描述、JSON-LD代码片段
7. **跟踪回归** – Delta引擎比较审计，检测评分下降的警报
8. **监控算法更新** – 情报源轮询Google Search Central + SEO博客，检测确认的事件
9. **发送HTML报告** – 自包含Jinja2模板与Telegram通知
10. **计划审计** – APScheduler cron作业，多租户隔离，WebSocket事件流

---

## 快速开始

### 1. 配置项目

创建 `projects.yaml`：

```yaml
projects:
  my-website:
    domain: https://example.com
    name: Example.com
    tenant_id: default
    enabled_sources:
      - gsc
      - pagespeed
    source_config:
      gsc:
        property_url: sc-domain:example.com
        credentials_path: /path/to/service-account.json
      pagespeed:
        api_key: ${PAGESPEED_API_KEY}
    enabled: true
    schedule_cron: "0 7 * * 1"  # 周一早上7点
    notifications_enabled: true
    notify_channels:
      - telegram
```

### 2. 设置环境变量

```bash
export CLAUDE_API_KEY="sk-ant-..."
export TELEGRAM_BOT_TOKEN="1234567:ABCdef..."
export TELEGRAM_CHAT_ID="123456789"
export DATABASE_URL="sqlite:///seo.db"
```

### 3. 运行首次审计

```bash
# 列出项目
seo-autopilot config list

# 运行审计
seo-autopilot run --project-id my-website

# 实时查看输出
seo-autopilot run --project-id my-website --verbose
```

### 4. 查看报告

打开 `reports/latest.html` 或通过API访问：

```bash
seo-autopilot api    # 在 http://localhost:8002 启动FastAPI
curl http://localhost:8002/api/health
```

---

## 分析维度

| 模块 | 检查内容 | 问题类型 |
|--------|---------------|-------------|
| **页面** | 标题、元描述、H1、viewport、lang、noindex | 12 |
| **Canonical引擎** | 信号层次、链、与sitemap/hreflang/noindex的冲突 | 7 |
| **重定向审计** | 链、循环、302 vs 301、跨域、软404、5xx集群 | 7 |
| **Schema验证** | 13种类型的JSON-LD必填字段、FAQ/产品/面包屑验证 | 4 |
| **GEO审计** | AI爬虫阻止、答案优先结构、事实密度、实体清晰度 | 7 |
| **主题权威** | 集群检测、主轴页面、覆盖差距、蚕食 | 5 |
| **重复内容** | SimHash近似重复（canonical感知）、薄内容、关键词蚕食 | 3 |
| **链接图** | 孤立页面、点击深度、断链、PageRank分布、权益下沉 | 5 |
| **Core Web Vitals** | 通过CrUX字段数据和Lighthouse实验室数据的INP、LCP、CLS | 6 |
| **安全** | HTTPS、HSTS、X-Frame-Options、X-Content-Type-Options | 2 |
| **LLMs.txt / AI.txt** | llms.txt规范验证、llms-full.txt、ai.txt、IndexNow密钥 | 6 |

**总计：60+跨11个分析维度的文档化问题类型。**

---

## 问题检测示例

### 高优先级问题
| 问题 | 严重性 | 工作量 | 影响 |
|-------|----------|--------|--------|
| 缺失标题 | 高 | 0.25小时 | 80 |
| 缺失h1 | 高 | 0.5小时 | 40 |
| 响应慢（>2.5s） | 高 | 8小时 | 70 |
| LCP差（>2.5s） | 高 | 4小时 | 80 |
| 差的CLS（>0.1） | 中 | 2小时 | 60 |
| 缺失安全头部 | 中 | 1小时 | 35 |

---

## ROI优先排序

- **快速见效**：工作量 ≤ 0.5小时 且 影响 ≥ 40
- **本周**：工作量 ≤ 4小时，按ROI排序
- **积压**：其他所有

---

## Telegram通知示例

```
🚀 SEO审计完成: my-website

📊 评分: 77/100（上次75.5）
问题: 3（0高、1中、2低）
快速见效: 2（30分钟内修复）

📈 GSC（28天）
点击: 15 | 展示: 420 | CTR: 3.6% | 排名: 12.3

🔧 首要行动
1. [高] /products缺失h1
2. [中] 响应慢（2.8秒）
3. [低] 法律页面noindex
```

---

## REST API

### 健康检查
```bash
curl http://localhost:8002/api/health
# { "status": "ok", "version": "1.2.0" }
```

### 运行审计
```bash
curl -X POST http://localhost:8002/api/audits/run/my-website
# { "audit_id": "a1b2c3...", "status": "running", "project_id": "my-website" }
```

### WebSocket事件（实时）
```bash
wscat -c ws://localhost:8002/api/ws/events/my-website

# 实时事件:
# { "type": "crawler_started", "pages_found": 6 }
# { "type": "analyzer_running", "issues_found": 12 }
# { "type": "strategy_complete", "quick_wins": 3 }
# { "type": "audit_complete", "score": 77 }
```

---

## Claude集成（MCP服务器）

将SEO Autopilot用作Claude工具通过模型上下文协议：

```python
from seo_autopilot.mcp.server import SEOAutopilotMCPServer

server = SEOAutopilotMCPServer()

# Claude现在可以调用:
# - list_projects() → 获取可用项目
# - run_audit(project_id="my-website") → 启动完整审计管道
```

---

## 安装

### 从PyPI（推荐）
```bash
pip install seo-autopilot
```

### 从源码
```bash
git clone https://github.com/tentacl-ai/seo-autopilot.git
cd seo-autopilot
pip install -e .
```

### Docker
```bash
docker build -t seo-autopilot .
docker run -p 8002:8002 \
  -e DATABASE_URL="sqlite:///seo.db" \
  -e CLAUDE_API_KEY="sk-..." \
  seo-autopilot
```

---

## 多租户使用

SEO Autopilot专为跨多个客户网站管理SEO而构建：

```yaml
projects:
  client-1:
    domain: https://client1.com
    tenant_id: client-1
  client-2:
    domain: https://client2.com
    tenant_id: client-2
```

每个项目隔离：
- 爬取数据
- GSC凭证
- 数据库记录
- API密钥
- 通知
- 报告
