# 技术SEO审计

## 基本信息
- **英文原名**: geo-technical
- **所属项目**: geo-seo-claude
- **核心能力**: 技术SEO审计，包含GEO特定检查——可爬取性、索引性、安全性、性能、SSR和AI爬虫访问。

## 目的

技术SEO是传统搜索可见性和AI搜索引用的基础。技术故障的网站无法被任何平台爬取、索引或引用。本技能审计8个类别的技术健康状况，特别关注GEO要求——最重要的是**服务器端渲染**（AI爬虫不执行JavaScript）和**AI爬虫访问**（许多网站无意中在robots.txt中阻止AI爬虫）。

## 审计类别

### 类别1：可爬取性（15分）

#### 1.1 robots.txt有效性
- 获取`https://[域名]/robots.txt`
- 检查语法有效性：正确的`User-agent`、`Allow`、`Disallow`指令
- 检查常见错误：缺少User-agent、通配符阻止重要路径、Disallow: /阻止整个网站
- 验证XML站点地图被引用：`Sitemap: https://[域名]/sitemap.xml`

#### 1.2 AI爬虫访问（GEO关键）
检查robots.txt中针对这些AI爬虫的指令：

| 爬虫 | 用户代理 | 平台 |
|---|---|---|
| GPTBot | GPTBot | ChatGPT / OpenAI |
| Google-Extended | Google-Extended | Gemini / Google AI训练 |
| Googlebot | Googlebot | Google搜索 + AI Overviews |
| Bingbot | bingbot | Bing Copilot + ChatGPT（通过Bing） |
| PerplexityBot | PerplexityBot | Perplexity AI |
| ClaudeBot | ClaudeBot | Anthropic Claude |
| Amazonbot | Amazonbot | Alexa / Amazon AI |
| CCBot | CCBot | Common Crawl（被许多AI模型使用） |

**AI爬虫访问评分：**
- 所有主要AI爬虫允许：5分
- 部分阻止但Googlebot + Bingbot允许：3分
- GPTBot或PerplexityBot阻止：1分（GEO影响重大）
- Googlebot阻止：0分（致命）

#### 1.3 XML站点地图
- 获取站点地图（从robots.txt检查位置，或尝试`/sitemap.xml`、`/sitemap_index.xml`）
- 验证XML语法
- 检查`<lastmod>`日期（应存在且准确）
- 统计URL——与预期的可索引页面数量比较
- 检查大型网站的站点地图索引（每站点地图最多50,000个URL）
- 验证所有站点地图URL返回200状态码（抽样检查）

#### 1.4 爬取深度
- 首页 = 深度0。检查所有重要页面在**3次点击**内可达
- 深度4+的页面接收显著更少的爬取预算，被AI引用的可能性更低
- 检查内部链接：关键内容页面是否从首页或主导航链接？

### 类别2：索引性（12分）

#### 2.1 规范标签
- 每个可索引页面必须有`<link rel="canonical" href="...">`标签
- 规范必须指向自身（自引用）作为权威版本
- 检查冲突规范（HTML vs HTTP头的规范）
- 检查规范链（A规范到B，B规范到C——应该是A到C）

#### 2.2 重复内容
- 检查www vs非www（两者都应解析，一个应该重定向）
- 检查HTTP vs HTTPS（HTTP应重定向到HTTPS）
- 检查尾部斜杠一致性（选择一种模式并重定向另一种）
- 检查参数重复（`?sort=price`创建重复页面）

### 类别3：安全性（10分）

#### 3.1 HTTPS强制
- 网站必须通过HTTPS加载
- HTTP必须重定向到HTTPS（301重定向）
- 无混合内容警告（HTTPS页面上的HTTP资源）
- SSL/TLS证书必须有效且未过期

#### 3.2 安全头
检查HTTP响应头：

| 头 | 要求值 | 目的 |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | 强制HTTPS |
| `Content-Security-Policy` | 适当策略 | 防止XSS |
| `X-Content-Type-Options` | `nosniff` | 防止MIME嗅探 |
| `X-Frame-Options` | `DENY` 或 `SAMEORIGIN` | 防止点击劫持 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` 或更严格 | 控制引用数据 |

### 类别4：URL结构（8分）

#### 4.1 清洁URL
- URL应人类可读：`/blog/seo-guide` 而非 `/blog?id=12345`
- URL中无会话ID
- 仅小写
- 单词分隔使用连字符（不是下划线）
- 无特殊字符或编码空格

#### 4.2 逻辑层次
- URL路径应反映网站架构：`/category/subcategory/page`
- 适当扁平化——避免不必要的深层嵌套
- 全站一致的URL模式

#### 4.3 重定向链
- 检查重定向链（A重定向到B重定向到C——建议最大1跳）
- 检查重定向循环
- 所有重定向应为301（永久），而非302（临时），除非故意临时

### 类别5：移动优化（10分）

#### 5.1 响应式设计
- 检查`<meta name="viewport" content="width=device-width, initial-scale=1">`
- 内容不得在移动设备上需要水平滚动
- 无大于视口宽度的固定宽度布局

#### 5.2 点击目标
- 交互元素（按钮、链接）必须至少48x48 CSS像素
- 点击目标之间至少8px间距
- 检查导航在移动设备上是否可用

### 类别6：Core Web Vitals（15分）

#### 2026年指标和阈值
Core Web Vitals使用真实用户数据的**第75百分位**作为基准。实验室数据对调试有用，但字段数据决定排名信号。

| 指标 | 良好 | 需要改进 | 较差 |
|---|---|---|---|
| **LCP**（最大内容绘制） | < 2.5s | 2.5s - 4.0s | > 4.0s |
| **INP**（交互到下一绘制） | < 200ms | 200ms - 500ms | > 500ms |
| **CLS**（累积布局偏移） | < 0.1 | 0.1 - 0.25 | > 0.25 |

### 类别7：服务器端渲染（15分）— GEO关键

#### 为什么SSR对AI可见性至关重要
AI爬虫（GPTBot、PerplexityBot、ClaudeBot等）**不执行JavaScript**。它们获取原始HTML并解析。如果您的内容由React、Vue、Angular或任何其他JavaScript框架客户端渲染，AI爬虫看到空页面。

#### 检测方法
1. 使用curl获取页面（无JavaScript执行）：`curl -s [URL]`
2. 与渲染DOM比较（通过浏览器）
3. 如果关键内容（标题、段落、产品信息、文章文本）在curl输出中**缺失**，网站依赖客户端渲染

#### 检查内容
- **主要内容文本**：文章正文/产品描述/页面内容在原始HTML中吗？
- **标题**：H1、H2、H3标签在原始HTML中吗？
- **导航**：主导航在服务器端渲染吗？
- **结构化数据**：JSON-LD在原始HTML中还是由JavaScript注入？
- **元标签**：title、description、canonical、OG标签在原始HTML中吗？
- **内部链接**：导航和内容链接在原始HTML中吗？（对可爬取性至关重要）

### 类别8：页面速度与服务器性能（15分）

#### 8.1 首字节时间（TTFB）
- 目标：**< 800ms**（理想< 200ms）
- 用curl测量：`curl -o /dev/null -s -w 'TTFB: %{time_starttransfer}s\n' [URL]`

#### 8.2 资源优化
- 总页面权重目标：**< 2MB**（关键页面< 1MB）
- 检查未压缩资源（应启用gzip/brotli压缩）
- 检查未压缩的CSS和JavaScript

#### 8.3 图片优化
- 检查图片格式：WebP或AVIF优于JPEG/PNG
- 检查过大图片（图片大于显示尺寸）
- 检查延迟加载：折叠下方图片应有`loading="lazy"`
- 检查显式尺寸（width/height属性防止CLS）

## 总体评分

| 类别 | 最高分 | 说明 |
|---|---|---|
| 可爬取性 | 15 | 核心基础 |
| 索引性 | 12 | 核心基础 |
| 安全性 | 10 | 信任信号 |
| URL结构 | 8 | 爬取效率 |
| 移动优化 | 10 | Google要求 |
| Core Web Vitals | 15 | 排名信号 |
| 服务器端渲染 | 15 | GEO关键 |
| 页面速度与服务器 | 15 | 性能 |
| **总计** | **100** | |

### 评分解读
- **90-100**：优秀——传统SEO和GEO技术上都健全
- **70-89**：良好——有轻微问题但基本健全
- **50-69**：需要改进——影响可见性的重大技术债务
- **30-49**：较差——阻碍爬取、索引或AI可见性的重大问题
- **0-29**：危急——需要立即关注的根本性技术故障

## 扣子部署建议

### 推荐插件
- **网页爬虫**：用于获取原始HTML
- **HTTP分析**：用于检查响应头

### 适用场景
- 技术SEO审计
- 网站迁移前检查
- GEO审计的技术部分
- 识别阻碍AI可见性的技术问题

### 核心输出
- 技术评分（0-100）
- 8个类别的详细评分
- 危急/高/中/低优先级问题清单
- 具体可操作的修复建议
