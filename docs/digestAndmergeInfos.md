# 实体数据合并与演化方案 (Entity Merge & Field Evolution)

## 1. 参考对象 — 这件事谁做得好
按行业接近程度排列：

### 1.1 CRM 行业 — Salesforce / HubSpot / Clay
* **解决问题**：“同一个人 / 同一家公司在多个 source 出现，怎么 merge”。
* **推荐参考**：**Clay** (逻辑最现代的 CRM enrichment 工具)。
* **关键概念**：Master Record（主记录） + Source Records（源记录） + Merge Rules（合并规则）。

### 1.2 新闻聚合 — Google News / Memorang / Feedly
* **解决问题**：“同一个事件被 100 家媒体报道，怎么去重 + 聚合”。
* **关键概念**：Event clustering（事件聚类） + Canonical source ranking（权威源排序）。

### 1.3 Entity Resolution / Data Engineering 领域 — Dedupe.io / Splink / Zingg
* **学科名称**：Entity Resolution (ER) 或 Record Linkage（记录链接）。
* **学术资源**：搜索以上关键词可获得大量算法模型。

### 1.4 ML 监控 / Data Versioning — DVC / lakeFS / Dolt
* **解决问题**：“数据随时间变，怎么做版本控制”。
* **关键概念**：**Slowly Changing Dimensions (SCD) Type 2**（缓慢变化维第二类）。

---

## 2. 问题的标准抽象：三个独立子问题
不要混为一谈，必须拆解：

1.  **子问题 1：实体识别 / Entity Resolution**
    * “两条 raw signal 说的是不是同一家公司？”
2.  **子问题 2：事件去重 / Event Deduplication**
    * “两条新闻报道的是不是同一个事件？”
3.  **子问题 3：字段更新 / Field Evolution**
    * “同一个字段，新值进来了，旧值怎么办？”

---

## 3. 子问题 1：实体识别 (公司层)
**标准做法：Deterministic（确定性） + Fuzzy（模糊） 双层匹配**

### 匹配流程：
1.  **第一层：Deterministic (精确匹配)**
    * URL domain (最准)
    * LinkedIn handle
    * 法律实体名 + 国家
2.  **第二层：Fuzzy (模糊匹配 — Score > 0.85)**
    * 公司名 Levenshtein 距离
    * 名字 + 总部城市 (HQ city)
    * 名字 + 创始人 (Founder)

**推荐工具**：Python 库 `recordlinkage`、`dedupe`、`splink`。或利用 **LLM** 进行最后一步 fuzzy matching。

---

## 4. 子问题 2：事件去重
**标准做法：Event Fingerprint（事件指纹） + 时间窗 Clustering（聚类）**

### Fingerprint 生成公式：
`hash(company_id + event_type + date_bucket + key_value_hash)`

* **date_bucket 策略**：
    * 融资/收购：同一周内 = 同一事件
    * 招聘：同一月内同一岗位 = 同一事件
    * 产品发布：同一天 = 同一事件

---

## 5. 子问题 3：字段更新 (SCD 模型)
采用数据仓库领域的 **Slowly Changing Dimensions (SCD)** 理论：

| 字段名 | SCD 模式 | 理由 |
| :--- | :--- | :--- |
| **Company Name** | Type 2 | 改名是大事，要留历史（如 Enersoft → GeologicAI）。 |
| **Founders** | Type 2 | 创始人离开/加入要记录。 |
| **Founded Year** | **Type 1** | 事实修正，改了就是修正错误。 |
| **Target Customer** | Type 2 | Pivot 是重大事件。 |
| **Latest Round** | **Type 4** | Current 表存最新，History 存所有轮次。 |
| **Investors** | Type 2 | 关联表，每轮投资人不同。 |
| **Last Updated** | **Type 1** | 始终记录最新时间戳。 |

---

## 6. 冲突处理决策树与优先级
### Source 优先级定义：
* **Tier 1 (最高)**：官方 PR、投资人 Portfolio、官网。
* **Tier 2 (高)**：主流媒体 (TechCrunch等)、Crunchbase (仅限融资)。
* **Tier 3 (中)**：PitchBook、LinkedIn。
* **Tier 4 (低)**：ZoomInfo、各类自动抓取工具。

---

## 7. 数据库 Schema 设计 (Demo 版)

```sql
-- 1. 公司主表 (Current View)
CREATE TABLE companies (
    id UUID PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    website TEXT,
    last_updated TIMESTAMP,
    confidence_score FLOAT
);

-- 2. 事件历史表 (Append-only)
CREATE TABLE events (
    id UUID PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    event_type TEXT,
    event_date DATE,
    payload JSONB,
    fingerprint TEXT UNIQUE,
    source_url TEXT,
    source_tier INT,
    cross_references JSONB,
    confidence FLOAT
);

-- 3. 关联关系表 (投资人/客户/合作伙伴)
CREATE TABLE company_relations (
    id UUID PRIMARY KEY,
    company_id UUID,
    related_entity TEXT,
    relation_type TEXT, 
    valid_from DATE,
    valid_to DATE,      -- NULL 表示当前有效
    source_url TEXT
);