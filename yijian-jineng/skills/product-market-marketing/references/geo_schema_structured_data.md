# Schema.org结构化数据

## 基本信息
- **英文原名**: geo-schema
- **所属项目**: geo-seo-claude
- **核心能力**: 用于AI可发现性的Schema.org结构化数据审计和生成——检测、验证和生成JSON-LD标记

## 目的

结构化数据是告诉AI系统实体是什么、做什么以及如何与其他实体连接的主要机器可读信号。虽然schema标记传统上是关于获得Google富结果，但其GEO中的作用根本不同：**结构化数据是AI模型理解和信任您实体的方式**。完整的结构化数据实体图显著增加跨所有AI搜索平台的引用概率。

## Schema类型对GEO的重要性

### Organization（必须——每个商业网站）

用于跨所有AI平台的实体识别。

**必需属性：**
- `@type`: "Organization"（或子类型：Corporation、LocalBusiness等）
- `name`: 官方商业名称
- `url`: 官方网站URL
- `logo`: logo图片URL

**GEO推荐属性：**
- `sameAs`: 所有平台URL数组
- `description`: 1-2句组织描述
- `foundingDate`: ISO 8601日期
- `founder`: Person schema
- `address`: PostalAddress schema
- `contactPoint`: ContactPoint
- `knowsAbout`: 组织擅长的主题数组

### Article + Author（发布商必须）

作者schema是AI平台最强的E-E-A-T信号之一。

**Article必需：**
- `@type`: "Article"
- `headline`: 文章标题
- `datePublished`: ISO 8601
- `dateModified`: ISO 8601
- `author`: Person或Organization schema
- `publisher`: Organization schema

**Author必需：**
- `name`: 全名
- `url`: 站内作者页面URL
- `sameAs`: LinkedIn、Twitter、个人网站、Google Scholar、ORCID

### Product（电商）

**必需：**
- `name`, `description`, `image`
- `offers`: Offer含价格、priceCurrency、availability
- `brand`: Brand schema

## sameAs策略（GEO关键）

`sameAs`属性是GEO最重要的结构化数据属性。它告诉AI系统："我网站上的这个实体与这些其他平台上的实体是同一个"。这创建了AI平台用于验证、信任和引用来源的实体图。

### 推荐的sameAs链接（按优先级）

1. Wikipedia文章 — 最高权威实体链接
2. Wikidata项目 — 机器可读实体标识符
3. LinkedIn — 公司页面或个人资料
4. YouTube — 频道URL
5. Twitter/X — 个人资料URL
6. Facebook — 页面URL
7. Crunchbase — 公司资料
8. GitHub — 组织或个人资料
9. Google Scholar — 作者资料
10. ORCID — 研究人员标识符

## 评分规则（0-100）

| 标准 | 分值 | 评分方法 |
|------|------|---------|
| Organization/Person schema存在且完整 | 15 | 完整给15分，基础给10分，无给0分 |
| sameAs链接（5+平台） | 15 | 每个有效sameAs给3分，最高15分 |
| 带作者详情的Article schema | 10 | 完整作者schema给10分，仅姓名给5分，无给0分 |
| 业务类型特定schema存在 | 10 | 完整给10分，部分给5分，缺失给0分 |
| WebSite + SearchAction | 5 | 存在给5分，不存在给0分 |
| BreadcrumbList（内部页面） | 5 | 存在给5分，不存在给0分 |
| JSON-LD格式（不是Microdata/RDFa） | 5 | JSON-LD给5分，混合给3分，仅Microdata给0分 |
| 服务器端渲染（不是JS注入） | 10 | HTML源码中给10分，JS但head中给5分，动态JS给0分 |
| Article上speakable属性 | 5 | 存在给5分，不存在给0分 |
| 有效JSON + 有效Schema.org类型 | 10 | 无错误给10分，轻微问题给5分，重大错误给0分 |
| Organization/Person上knowsAbout属性 | 5 | 3+主题存在给5分，缺失给0分 |
| 无废弃schema存在 | 5 | 干净给5分，发现废弃schema给0分 |

## 工作流程

1. 获取页面HTML
2. 检测所有结构化数据（JSON-LD、Microdata、RDFa）
3. 验证schema与Schema.org规范
4. 识别缺失推荐schema
5. 生成JSON-LD代码块
6. 输出GEO-SCHEMA-REPORT.md

## 扣子部署建议

### 推荐插件
- **网页爬虫**：用于获取页面HTML

### 适用场景
- Schema审计
- 结构化数据验证
- JSON-LD生成
- 实体识别优化

### 核心输出
- Schema评分
- 检测到的schema列表
- 验证结果
- 缺失schema建议
- 生成JSON-LD代码
