# 新闻模块 API 参考（`open/ai/article/`）

> 基础路径：`{BASE}/open/ai/article/...`

用于拉取栏目树、按源站 ID 去重判断、推送新闻、编辑已推送新闻。

---

## 前置约定

### 栏目 ID 来源

推送前**必须先调用 `categories`** 获取栏目树，从中选择节点 **`id`** 填入 `categoryIds`，不可凭空编造栏目编号。

### 正文完整性

`pushArticle` 和 `updateArticle` 的 **`content` 必须推送完整全文**，与来源稿件保持一致。**禁止**因模型上下文限制、话术长度或摘要习惯对正文做**截断、删节或只传片段**。

若原文过长导致单次请求困难，应在技术侧分段组包或加大超时，**不得**用不完整内容代替完整 `content`。

---

## 接口一览

| 方法 | 路径 | 参数 |
|------|------|------|
| `GET` | `.../categories` | `appKey`（Query） |
| `GET` | `.../getArticleByOldHtmlId` | `appKey`、`oldHtmlId`（Query） |
| `POST` | `.../pushArticle` | `appKey`（Query）+ JSON Body |
| `POST` | `.../updateArticle` | `appKey`（Query）+ JSON Body |

---

## 1. 栏目树 `GET .../categories`

### 响应 `data`

根栏目组成的数组，可带多级子节点。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | number | 栏目 ID，**写入 `categoryIds` 时使用** |
| `categoryName` | string | 栏目名称 |
| `list` | array \| null | 子节点，结构递归 |

---

## 2. 去重查询 `GET .../getArticleByOldHtmlId`

### 响应 `data`

| 值 | 含义 |
|----|------|
| `true` | 该 `oldHtmlId` 已存在（已推送 / 已抓取），**跳过** |
| `false` | 不存在，可以继续推送 |

---

## 3. 推送新闻 `POST .../pushArticle`

- **Header**：`Content-Type: application/json`
- **成功响应**：`errno === 0`，`data` 为新建文章的整数 `id`
- `content` 非空时由服务端存储并生成 `contentUrl`；调用方通常**不要**传 `contentUrl`
- 组织信息与 `appKey` 绑定，**不要**在 Body 中自行传递组织类字段来切换主体

### Body 字段

| 字段 | 必填 | 类型 | 说明 |
|------|:--:|------|------|
| `title` | 是 | string | 文章标题 |
| `content` | 是 | string | 正文（HTML 等），**须完整，不得截取** |
| `categoryIds` | 是 | number[] | 至少一个栏目 ID（来自 `categories`） |
| `thumbImg` | 否 | string | 缩略图 URL |
| `publishTime` | 否 | string | 格式 `yyyy-MM-dd HH:mm:ss`，如 `2026-04-01 10:00:00` |
| `oldHtmlId` | 否 | string | 源站 ID，用于去重 |
| `openOuterLink` | 否 | boolean | 默认 `false` |
| `remoteUrl` | 否 | string | 原文链接 |
| `contentUrl` | 否 | string | 一般**勿传**，由服务端自动生成 |

### 校验提示

- `文章标题不能为空！`
- `文章内容不能为空！`
- `文章栏目不能为空！`

### 推荐流程

```
categories →（可选）getArticleByOldHtmlId → pushArticle
```

---

## 4. 编辑新闻 `POST .../updateArticle`

用于在推送后修正文章正文或元数据。与 `pushArticle` 规则一致：正文内图片会走 COS 替换，`content` 会重新上传并生成 `contentUrl`（调用方不要自行填充 `contentUrl`）。

- **Header**：`Content-Type: application/json`
- **Query**：`appKey`（必填）
- **校验**：`id` 和 `content` 均不能为空
- **权限约束**：文章须已存在，且 `commitUser` 须与创建时一致。创建时的提交人来自 `appKey` 对应的管理员，因此**只有用同一个 `appKey`（同一集成身份）推送的文章才能修改**，否则会返回 `非文章创建人，无法修改！`
- **成功响应**：`errno === 0`，`data` 为文章 `id`（通常与请求的 `id` 一致）

### Body 字段

| 字段 | 必填 | 类型 | 说明 |
|------|:--:|------|------|
| `id` | **是** | number | `pushArticle` 成功响应中的 `data`（文章编号） |
| `content` | **是** | string | 正文，**须完整**，规则同"正文完整性" |
| `title` | 建议 | string | 若修改标题则传入新标题 |
| `categoryIds` | 建议 | number[] | 若修改栏目则传入（须为有效栏目 ID） |
| `thumbImg` | 否 | string | 缩略图 URL |
| `publishTime` | 否 | string | 格式 `yyyy-MM-dd HH:mm:ss` |
| `oldHtmlId` | 否 | string | 与 `pushArticle` 含义一致 |
| `openOuterLink` | 否 | boolean | 与 `pushArticle` 含义一致 |
| `remoteUrl` | 否 | string | 与 `pushArticle` 含义一致 |

### 禁止传递的字段

- `shId`、`commitUser` — 由服务端根据 `appKey` 自动解析和校验

### 典型错误

- `id/内容不能为空！`
- 文章不存在
- `非文章创建人，无法修改！`

### 推荐流程

```
pushArticle（记下返回的 data → id）→ 用户确认修改 → updateArticle（同一 appKey）
```

---

## 请求示例

### 去重查询

```http
GET {BASE}/open/ai/article/getArticleByOldHtmlId?appKey=...&oldHtmlId=site-123
```

### 推送新闻

```http
POST {BASE}/open/ai/article/pushArticle?appKey=...
Content-Type: application/json
```

```json
{
  "title": "协会动态标题",
  "content": "<p>正文 HTML</p>",
  "categoryIds": [101, 102],
  "oldHtmlId": "site-123",
  "publishTime": "2026-04-01 10:00:00",
  "thumbImg": "https://example.com/cover.jpg",
  "openOuterLink": false
}
```

**推送成功响应**（`data` 为新建文章 id）：

```json
{
  "errno": 0,
  "errmsg": "成功",
  "data": 12345
}
```

### 编辑新闻

```http
POST {BASE}/open/ai/article/updateArticle?appKey=...
Content-Type: application/json
```

```json
{
  "id": 12345,
  "title": "调整后的标题",
  "content": "<p>全文 HTML（规则同 push，禁止截断）</p>",
  "categoryIds": [101, 102]
}
```

**编辑成功响应**：

```json
{
  "errno": 0,
  "errmsg": "成功",
  "data": 12345
}
```

---

> **通用响应约定**：`errno` / `errmsg` / `data` 结构见 `SKILL.md`。
