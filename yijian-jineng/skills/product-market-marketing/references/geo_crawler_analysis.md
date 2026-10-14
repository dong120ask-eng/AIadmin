# AI爬虫访问分析

## 基本信息
- **英文原名**: geo-crawlers
- **所属项目**: geo-seo-claude
- **核心能力**: 通过检查robots.txt、元标签和HTTP头确定哪些AI爬虫可以访问网站。提供完整的访问地图和最大化AI可见性同时保持适当控制的建议。

## 目的

本技能分析网站对AI爬虫的可访问性——AI公司用于发现、索引和训练网络内容的爬虫。如果AI爬虫被阻止，网站内容将无法出现在AI生成的响应中，无论其质量如何。爬虫访问是GEO的基础技术要求。

## 核心洞察

截至2026年初，许多网站通过过度激进的robots.txt规则无意中阻止AI爬虫，这些规则继承自传统SEO配置。Originality.ai 2025年研究发现，前1000个网站中超过35%阻止至少一个主要AI爬虫，5-10%阻止所有AI爬虫。阻止AI爬虫是成为AI生成搜索结果中不可见的最快方式。

## 完整AI爬虫参考

### 第1层：对AI搜索可见性至关重要（推荐：允许）

这些爬虫为用户提供主动寻找答案的AI搜索产品提供动力。阻止它们直接减少AI生成响应中的可见性。

#### GPTBot
- **运营商：** OpenAI
- **用户代理：** `GPTBot`
- **完整用户代理字符串：** `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)`
- **目的：** 获取ChatGPT网络浏览、插件和搜索功能的内容。GPTBot访问的内容可能用于改进OpenAI模型。
- **阻止的影响：** 内容不会出现在ChatGPT搜索结果中，也不会在用户要求ChatGPT浏览网络时访问。这是影响最高的AI爬虫。
- **建议：** **允许** —— ChatGPT截至2025年有3亿+周活跃用户。阻止GPTBot将内容从最大AI搜索界面之一移除。

#### OAI-SearchBot
- **运营商：** OpenAI
- **用户代理：** `OAI-SearchBot`
- **完整用户代理字符串：** `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; OAI-SearchBot/1.0; +https://docs.openai.com/bots/overview)`
- **目的：** 专门为ChatGPT搜索功能提供动力。与GPTBot不同，OAI-SearchBot访问的内容**不用于模型训练**——仅用于实时搜索结果。
- **阻止的影响：** 即使允许GPTBot，内容也不会出现在ChatGPT搜索结果中。
- **建议：** **允许** —— 这是纯搜索爬虫，没有训练用途。没有战略性理由阻止它。

#### ChatGPT-User
- **运营商：** OpenAI
- **用户代理：** `ChatGPT-User`
- **完整用户代理字符串：** `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ChatGPT-User/1.0; +https://openai.com/bot)`
- **目的：** 当ChatGPT用户明确要求模型访问特定URL时使用。代表用户像浏览器代理一样行为。
- **阻止的影响：** ChatGPT无法在用户要求阅读或总结页面时访问。阻止主动尝试参与内容的用户。
- **建议：** **允许** —— 阻止此爬虫阻止通过ChatGPT主动尝试参与内容的用户。

#### ClaudeBot
- **运营商：** Anthropic
- **用户代理：** `ClaudeBot`
- **完整用户代理字符串：** `ClaudeBot/1.0; +https://www.anthropic.com/claude-bot`
- **目的：** 为Claude的网络搜索、引用和分析工具功能获取网页内容。
- **阻止的影响：** 内容将无法被Claude用于网络搜索或在用户要求Claude分析特定URL时访问。
- **建议：** **允许** —— Claude是市场份额不断增长的主要AI助手。阻止ClaudeBot减少AI搜索覆盖。

#### PerplexityBot
- **运营商：** Perplexity AI
- **用户代理：** `PerplexityBot`
- **完整用户代理字符串：** `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)`
- **目的：** 为Perplexity的AI搜索引擎提供动力，提供带有直接引用和返回源页面链接的来源答案。
- **阻止的影响：** 内容不会出现在Perplexity搜索结果中。Perplexity是AI搜索产品中最好的推荐流量来源之一，因为它始终显示来源链接。
- **建议：** **允许** —— Perplexity推动实际推荐流量并始终归因来源。对发布商和企业来说是高价值AI爬虫。

### 第2层：对更广泛AI生态系统重要（推荐：允许）

这些爬虫为大型AI平台或搜索引擎提供动力。允许它们增加内容的覆盖范围。

#### Google-Extended
- **运营商：** Google
- **用户代理：** `Google-Extended`
- **目的：** 控制Google是否使用您的内容进行Gemini模型训练和AI Overviews改进。**重要提示：** 阻止Google-Extended不影响您的Google搜索排名或Google搜索结果中的出现。那由标准Googlebot控制。
- **阻止的影响：** 内容可能不用于Gemini训练或改进AI Overviews。但是，您的内容仍可基于标准搜索索引出现在AI Overviews中。
- **建议：** **允许** —— 阻止提供最小的内容保护优势，同时减少Google AI功能的覆盖。由于不影响标准搜索排名，唯一阻止的理由是对训练数据使用有哲学反对。

#### Applebot-Extended
- **运营商：** Apple
- **用户代理：** `Applebot-Extended`
- **目的：** Apple用于训练和改进Apple Intelligence功能、Siri和Apple AI产品。独立于标准Applebot（控制Siri搜索和Spotlight建议）。
- **阻止的影响：** 内容可能不用于Apple Intelligence功能。标准Siri和Spotlight功能不受影响（由Applebot控制）。
- **建议：** **允许** —— Apple Intelligence集成在所有Apple设备上（20亿+活跃设备）。在Apple AI功能中的存在具有不断增长的战略价值。

#### FacebookBot
- **运营商：** Meta
- **用户代理：** `FacebookBot`
- **目的：** Meta用于跨Facebook、Instagram、WhatsApp和Meta AI助手的AI功能。
- **阻止的影响：** 内容可能无法被Meta AI访问。Facebook/Instagram上的链接预览由不同爬虫处理，不受影响。
- **建议：** **允许** —— Meta AI嵌入在30亿+综合用户的应用中。对AI可见性的重要性日益增长。

### 第3层：仅训练爬虫（基于策略允许或阻止）

这些爬虫主要用于AI模型训练而非实时搜索功能。阻止它们不影响AI搜索可见性。

#### CCBot
- **运营商：** Common Crawl（非营利组织）
- **用户代理：** `CCBot`
- **完整用户代理字符串：** `CCBot/2.0 (https://commoncrawl.org/faq/)`
- **目的：** 构建Common Crawl数据集，用于许多AI公司的训练数据（Google、Meta、Stability AI等）。
- **阻止的影响：** 内容不会出现在未来的Common Crawl数据集中。不影响任何实时AI搜索产品。
- **建议：** **基于上下文** —— 如果您希望最大长期AI训练覆盖则允许；如果您想控制训练数据使用则阻止。不影响搜索可见性。

#### anthropic-ai
- **运营商：** Anthropic
- **用户代理：** `anthropic-ai`
- **目的：** Anthropic用于AI安全研究和Claude模型训练。独立于ClaudeBot（控制实时功能）。
- **阻止的影响：** 内容不会用于Claude训练。不影响Claude的实时搜索或网络浏览功能（由ClaudeBot控制）。
- **建议：** **基于上下文** —— 类似于CCBot。允许以获得训练覆盖，阻止以控制训练数据。不影响实时AI搜索。

#### Bytespider
- **运营商：** ByteDance
- **用户代理：** `Bytespider`
- **目的：** ByteDance用于各种AI产品，包括TikTok的AI功能和豆包（他们在中国的ChatGPT竞争对手）。
- **阻止的影响：** 内容不会用于ByteDance AI产品。对西方市场企业影响很小。
- **建议：** **阻止** —— 对于大多数西方企业（报告了激进爬虫行为，低搜索可见性收益）。如果针对中国/亚洲市场则**允许**。

## 建议矩阵摘要

| 爬虫 | 层 | 建议 | 理由 |
|---|---|---|---|
| GPTBot | 1 | **允许** | 为ChatGPT搜索提供动力（3亿+用户） |
| OAI-SearchBot | 1 | **允许** | 纯搜索，无训练用途 |
| ChatGPT-User | 1 | **允许** | 用户发起的浏览 |
| ClaudeBot | 1 | **允许** | Claude网络搜索和分析 |
| PerplexityBot | 1 | **允许** | 最佳推荐流量AI搜索 |
| Google-Extended | 2 | **允许** | Gemini功能；不影响搜索排名 |
| Applebot-Extended | 2 | **允许** | Apple Intelligence（20亿+设备） |
| Amazonbot | 2 | **允许** | Alexa和Amazon AI |
| FacebookBot | 2 | **允许** | Meta AI（30亿+应用用户） |
| CCBot | 3 | 基于上下文 | 仅训练数据 |
| anthropic-ai | 3 | 基于上下文 | 仅训练数据 |
| Bytespider | 3 | **阻止** | 激进爬虫，低收益 |
| cohere-ai | 3 | 基于上下文 | 仅训练数据 |

### 最大AI可见性配置（robots.txt）

对于希望最大AI搜索可见性的网站：

```
# AI爬虫 - 允许以获得AI搜索可见性
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: GoogleOther
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: FacebookBot
Allow: /

# AI爬虫 - 阻止（激进/低价值）
User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /
```

## 分析程序

### 步骤1：获取并解析robots.txt

1. 使用WebFetch获取`[域名]/robots.txt`。
2. 解析所有用户代理指令及其关联的允许/禁止规则。
3. 对于上述参考列表中的每个AI爬虫：
   - 检查是否有针对该爬虫的特定用户代理块
   - 检查是否有通配符（`User-agent: *`）块将适用
   - 确定有效访问：**允许**、**阻止**或**未提及**（继承通配符规则）
4. 注意任何可能减慢AI爬虫访问的`Crawl-delay`指令。
5. 检查`Sitemap`指令（AI爬虫使用这些进行发现）。

### 步骤2：检查Meta Robots标签

1. 对于5-10个关键页面样本，获取HTML并检查：
   - `<meta name="robots" content="noindex">` -- 阻止所有爬虫
   - `<meta name="robots" content="nofollow">` -- 阻止链接跟随
   - `<meta name="robots" content="noai">` -- 新兴标签阻止AI使用
   - `<meta name="robots" content="noimageai">` -- 阻止AI图片训练
   - 爬虫特定元标签：`<meta name="GPTBot" content="noindex">`
2. 记录robots.txt指令的任何页面级覆盖。

### 步骤3：检查HTTP头

1. 对于相同样本页面，检查响应头中的：
   - `X-Robots-Tag: noindex` -- meta noindex的HTTP头等效
   - `X-Robots-Tag: noai` -- 阻止AI使用的HTTP头
   - `X-Robots-Tag: noimageai` -- 阻止AI图片训练
   - 爬虫特定头：`X-Robots-Tag: GPTBot: noindex`
2. 注意HTTP头覆盖元标签并适用于非HTML资源。

### 步骤4：检查AI特定文件

1. 检查`/llms.txt`（AI爬虫指导的新兴标准）。
2. 检查`/.well-known/ai-plugin.json`（OpenAI插件清单）。
3. 检查`/ai.txt`（提出的标准，类似于用于AI的广告txt）。
4. 记录每个文件的存在/不存在和质量。

### 步骤5：评估JavaScript渲染要求

1. 检查网站是否是单页应用（SPA）或重度JavaScript渲染。
2. AI爬虫的JavaScript渲染能力各异：
   - GPTBot：有限的JS渲染
   - ClaudeBot：有限的JS渲染
   - PerplexityBot：有限的JS渲染
   - Googlebot：完全JS渲染（但Google-Extended继承此能力）
3. 如果关键内容需要JS渲染，标记为潜在问题。
4. 检查服务器端渲染（SSR）或静态站点生成（SSG）作为缓解措施。

## 爬虫访问评分

AI爬虫访问评分计算如下：

| 组件 | 权重 | 评分 |
|---|---|---|
| 允许的第1层爬虫 | 50% | 每个允许的第1层爬虫20分（5个爬虫=最高100分，缩放至50） |
| 允许的第2层爬虫 | 25% | 每个允许的第2层爬虫20分（5个爬虫=最高100分，缩放至25） |
| 无全AI阻止 | 15% | 如果没有`User-agent: * Disallow: /`且无noai元标签则满分 |
| 存在AI特定文件 | 10% | llms.txt得5分，AI爬虫可访问的站点地图得5分 |

最终评分 = 所有加权组件的总和，上限100。

## 扣子部署建议

### 推荐插件
- **网页访问**：用于获取robots.txt和页面内容
- **HTTP头分析**：用于检查响应头

### 适用场景
- 技术SEO团队检查AI爬虫可访问性
- GEO审计的一部分
- 识别阻止AI可见性的技术问题
- 生成AI爬虫配置建议

### 核心输出
- 14个AI爬虫的访问状态
- AI可见性评分（0-100）
- 具体robots.txt配置建议
- 技术发现摘要
