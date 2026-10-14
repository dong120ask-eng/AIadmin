---
name: ai-seo-code-audit
description: AI-SEO代码审计技能 - 分析网站源代码以识别SEO问题，专注于影响AI爬虫和搜索引擎正确读取内容的渲染逻辑和实现模式。当用户要求"审计代码SEO"、"检查我的网站代码"、"AI友好性检查"或"代码级别SEO分析"时使用。
---

# AI-SEO代码审计技能

## 目的

分析网站源代码以识别可通过代码检查检测到的SEO问题。专注于影响AI爬虫和搜索引擎正确读取内容的问题。

## 审计范围

- 检查源文件（组件、模板、视图、控制器）
- 分析路由配置和URL生成
- 审查数据获取模式和渲染方法
- 检查影响SEO的构建/编译设置

---

## 关键分析领域

### 1. HTML标题标签结构（H1-H6）

**检查以下具体问题：**

| 问题 | 说明 | 严重性 |
|------|------|--------|
| 缺失H1标签 | 每个页面必须只有一个H1标签 | 高 |
| 多个H1标签 | 标记有多个H1的页面 | 高 |
| 跳过标题级别 | H1后应跟H2，而非H3 | 中 |
| 标题层次结构 | 确保逻辑嵌套（H2在H1下，H3在H2下等） | 中 |
| 空标题 | 没有文本内容的标题 | 中 |
| 用于样式的标题 | 仅用于字体大小的非语义标题标签使用 | 低 |
| 动态标题生成 | 检查标题是硬编码还是动态生成 | 中 |

**代码模式检查：**

```javascript
// 坏模式：
<h1></h1>  // 空
<h1>{title || ""}</h1>  // 可能为空
<h3>副标题</h3>  // 缺失H1和H2
<h1>页面标题</h1>
<h1>另一个标题</h1>  // 多个H1

// 好模式：
<h1>{title || "默认标题"}</h1>
<h2>章节标题</h2>
<h3>子章节标题</h3>
```

---

### 2. 元标签和SEO元素

#### 标题标签
- 每个页面存在
- 长度50-60个字符
- 每个页面唯一标题
- 动态 vs 静态实现
- 动态页面的回退/默认标题
- 检查空或重复标题

#### 元描述
- 每个页面存在
- 长度150-160个字符
- 每个页面唯一描述
- 有意义的内容（不只是重复标题）
- 动态生成模式

#### 规范URL
- 规范标签存在
- 自我引用canonical
- 正确处理分页
- 动态路由canonical生成

#### Open Graph标签
- og:title（必需）
- og:description（必需）
- og:image（必需）
- og:url（必需）
- og:type
- twitter:card及相关标签

#### 其他重要元标签
- viewport元标签（移动）
- robots元标签（index/noindex指令）
- HTML标签上的lang属性
- charset声明

---

### 3. 关键内容依赖关系

**识别以下渲染方法：**
- 页面标题和标题
- 主要正文内容
- 导航菜单
- 产品/文章描述
- 图片alt文本
- 内部链接

**标记这些反模式：**

```javascript
// 坏：SEO内容在客户端加载
useEffect(() => {
  fetch('/api/product/' + id)
    .then(res => res.json())
    .then(data => {
      setTitle(data.title);       // SEO关键
      setDescription(data.description);  // SEO关键
      setContent(data.content);  // SEO关键
    });
}, []);

// 坏：内容在用户交互后面
<button onClick={() => setShowContent(true)}>
  显示描述
</button>
{showContent && <div>{productDescription}</div>}

// 好：服务器端渲染的内容
export async function getServerSideProps({ params }) {
  const data = await fetchProduct(params.id);
  return {
    props: {
      title: data.title,
      description: data.description,
      content: data.content
    }
  };
}
```

**关键洞察：** AI平台正在不执行JavaScript的情况下抓取网站。通过Supabase调用或从其他客户端API请求获取的内容来渲染内容，对AI爬虫将是空白的。如果AI看不到你的内容，你的网站在AI搜索时代将变得不可见。

---

### 4. URL结构和路由

**检查：**
- 清洁URL，无过多参数（/products/shoes而非/products?category=shoes&id=123）
- 描述性slug（/blog/seo-best-practices而非/blog/12345）
- 一致的URL模式
- 正确处理尾部斜杠
- 大小写敏感性
- 动态URL生成模式

**标记这些模式：**

```
// 坏：
/page?id=123&cat=456&sort=new&filter=true
/Product/DETAIL/12345
/blog/post.php?postid=789

// 好：
/products/running-shoes
/blog/2024/seo-guide
/category/electronics/laptops
```

---

### 5. 结构化数据（Schema.org）

**检查实现：**
- Organization schema
- Article/BlogPosting schema
- Product schema（含必填字段）：
  - name
  - description
  - image
  - offers（price, availability）
  - review/aggregateRating
- BreadcrumbList schema
- FAQPage schema（适用时）
- LocalBusiness schema（适用时）

**验证：**
- 首选JSON-LD格式而非微数据
- 有效的schema语法
- 必填属性存在
- 结构化数据的服务器端渲染

---

### 6. 图片SEO实现

**检查所有图片元素：**
- alt文本存在和质量
- 描述性文件名（product-name.jpg而非IMG_12345.jpg）
- 适当的title属性
- 加载策略（懒加载实现）
- 适当的srcset/sizes用于响应式图片
- 图片sitemap引用

**代码模式：**

```javascript
// 坏：
<img src="IMG_12345.jpg" />
<img src={product.image} alt="" />
<img src={url} alt="image" />

// 好：
<img 
  src="/products/red-running-shoes.jpg"
  alt="红色耐克跑鞋，白色鞋底"
  loading="lazy"
  srcset="..."
/>
```

---

### 7. 内部链接结构

**分析：**
- 锚文本多样性（不只是"点击这里"）
- 正确使用rel属性
- 链接分布（确保重要页面有足够内部链接）
- 孤立页面（无内部链接指向的页面）

---

## 问题严重性分类

### 危急（立即修复）
- 所有AI爬虫在robots.txt中被阻止
- 所有SEO关键内容通过客户端API调用加载
- 缺失H1或多个H1
- 无规范URL
- 缺失viewport元标签

### 高优先级（1周内修复）
- 主要页面缺失标题或元描述
- 产品/文章描述通过客户端API加载
- 标题标签过长或过短
- URL结构混乱（过多参数）
- 缺失Open Graph标签

### 中等优先级（1月内修复）
- 部分页面缺失alt文本
- 部分页面标题层次结构不优
- 缺少一些结构化数据
- 内部链接不充分

### 低优先级（优化时）
- 图片文件名不描述性
- 次要schema验证错误
- 缺少一些面包屑导航

---

## 输出格式

```markdown
# AI-SEO代码审计报告

## 执行摘要
[网站概述和整体健康状况]

## 危急问题

### 问题1：[标题]
- **文件：** [位置]
- **严重性：** 危急
- **当前代码：**
```[代码]```
- **问题：** [描述]
- **建议修复：**
```[修复代码]```

## 高优先级问题

[按文件分组的问题列表]

## 中等优先级问题

[按文件分组的问题列表]

## 低优先级问题

[按文件分组的问题列表]

## 总结

| 类别 | 发现数 |
|------|--------|
| 危急 | X |
| 高 | X |
| 中 | X |
| 低 | X |
| **总计** | **X** |

## 修复优先级
1. [最紧急的修复]
2. [次紧急的修复]
...
```

---

## 最佳实践建议

### SSR/ISR优先
对于Next.js、Nuxt等框架，确保关键SEO内容使用服务器端渲染（SSR）或增量静态再生成（ISR）。

### API数据预取
在服务器端预取API数据并将其传递给页面，而不是在客户端useEffect中获取。

### 建立规范URL
为所有页面建立正确的规范URL，包括分页和过滤参数。

### 实施结构化数据
为所有内容类型实施完整的JSON-LD结构化数据。

### 优化图片
使用描述性文件名和alt文本，实施懒加载和响应式图片。
