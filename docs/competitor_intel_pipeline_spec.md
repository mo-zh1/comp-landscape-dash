# Competitor Intelligence Pipeline — 实现规范

> 给 Claude Code 的实施文档。目标:搭建一个全自动竞品尽调 pipeline,定时抓取 → LLM 拆解 → 入库 → 可视化,带成熟的去重 / 实体识别 / 字段更新机制。
>
> **设计原则:简单优先。最终形态,但用最简实现。**

---

## 1. 整体架构

```
┌────────────────────────────────────────────────────────┐
│ SCHEDULER (GitHub Actions cron)                        │
│   • daily.yml   — 抓融资 / 收购 / 高管变动新闻        │
│   • weekly.yml  — 抓官网 / 招聘 JD diff               │
│   • monthly.yml — 全量复扫所有字段                    │
└──────────────────┬─────────────────────────────────────┘
                   │ 触发
                   ▼
┌────────────────────────────────────────────────────────┐
│ ORCHESTRATOR (Python, ~150 行)                         │
│   pipeline.py                                          │
│   • 从 DB 读取要跑的公司列表                          │
│   • 按 trigger 类型调对应 skill                        │
│   • 把 skill 输出走完 entity resolution → dedup →     │
│     SCD update → 写库                                  │
│   • 触发 conflict / candidate 进人工队列               │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ SKILLS (4 个,每个独立可调用)                          │
│   1. scrape_competitor    抓公司全量信息              │
│   2. extract_event        从新闻文本抽 event JSON     │
│   3. discover_new_competitors   发现潜在新对手        │
│   4. generate_weekly_digest    生成 CEO 周报          │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ STORAGE (SQLite,单文件)                              │
│   competitors.db                                       │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ VISUALIZATION (Streamlit,~100 行)                     │
│   • 主看板:Companies 表渲染                           │
│   • Timeline 视图:Events 横轴                         │
│   • Investor cross-reference:conflict mapping         │
│   • Conflict queue:人工裁决                           │
│   • Candidate queue:新对手审核                        │
└────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11+ | 生态全 |
| Scheduler | GitHub Actions | 免费 cron,无需部署 |
| Database | SQLite(demo)/ Supabase Postgres(生产) | 单文件够 demo;升级路径清晰 |
| LLM | Claude Sonnet 4.5 via Anthropic API | structured output 最稳 |
| Scraping | `httpx` + `BeautifulSoup` + `markdownify` | 简单页面够用;复杂页面用 Firecrawl |
| Search | Anthropic web search tool / Serper API | 都行 |
| Fuzzy matching | `rapidfuzz` | 比 fuzzywuzzy 快 10x |
| Visualization | Streamlit | 100 行写完看板,免部署烦恼 |

**避免**:n8n、Zapier、Airflow、Temporal、Neo4j、Kafka —— 全是 over-engineering。

---

## 3. 数据库 Schema

完整 SQLite schema。直接执行即可。

```sql
-- ============================================================
-- 1. companies — 主表(SCD Type 4 的 current 部分)
-- ============================================================
CREATE TABLE companies (
    id TEXT PRIMARY KEY,              -- UUID
    canonical_name TEXT NOT NULL,
    website TEXT,
    linkedin_url TEXT,
    hq_city TEXT,
    hq_country TEXT,
    founded_year INTEGER,

    -- Latest 字段(都是从 events 表派生的快照)
    target_customer TEXT,
    core_product TEXT,
    pricing_model TEXT,
    latest_round_type TEXT,           -- 'seed' / 'series_a' / etc
    latest_round_amount_usd REAL,
    latest_round_date DATE,
    business_model_summary TEXT,

    -- 元数据
    status TEXT DEFAULT 'active',     -- active / acquired / pivoted / dead / stealth
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_score REAL DEFAULT 1.0,
    notes TEXT                        -- 自由文本,LLM 维护
);

CREATE INDEX idx_companies_canonical_name ON companies(canonical_name);
CREATE INDEX idx_companies_website ON companies(website);
CREATE INDEX idx_companies_status ON companies(status);


-- ============================================================
-- 2. events — 事件表(SCD Type 4 的 history 部分,append-only)
-- ============================================================
CREATE TABLE events (
    id TEXT PRIMARY KEY,              -- UUID
    company_id TEXT NOT NULL REFERENCES companies(id),
    event_type TEXT NOT NULL,         -- 见下方 enum
    event_date DATE NOT NULL,
    payload TEXT NOT NULL,            -- JSON,事件类型不同字段不同
    fingerprint TEXT UNIQUE NOT NULL, -- 去重核心
    source_url TEXT,
    source_tier INTEGER DEFAULT 3,    -- 1=最高,4=最低
    cross_references TEXT,            -- JSON array,其他报道同一事件的 source
    extracted_by TEXT,                -- 模型名 e.g. 'claude-sonnet-4.5'
    confidence REAL DEFAULT 0.5,
    raw_text TEXT,                    -- 保留 LLM 抽取时的原文(归档)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_company_id ON events(company_id);
CREATE INDEX idx_events_event_type ON events(event_type);
CREATE INDEX idx_events_event_date ON events(event_date);
CREATE INDEX idx_events_fingerprint ON events(fingerprint);

-- event_type enum (软约束,代码层维护):
--   funding_round       新融资轮次
--   acquisition         被收购 / 收购别人
--   leadership_change   高管入职 / 离职
--   product_launch      新产品 / 大版本发布
--   partnership         新合作伙伴
--   customer_win        新客户 / 案例
--   customer_loss       失去客户
--   pivot               业务方向转变
--   rebrand             改名
--   facility_open       新办公室 / 新地区扩张
--   pricing_change      定价变化
--   tech_disclosure     技术架构披露(论文 / blog / 演讲)
--   hiring_signal       招聘聚集(某岗位密集招)


-- ============================================================
-- 3. company_relations — 关联实体(SCD Type 2)
-- ============================================================
CREATE TABLE company_relations (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    related_entity_name TEXT NOT NULL,
    related_entity_type TEXT NOT NULL,    -- investor / customer / partner / acquirer / advisor
    relation_subtype TEXT,                -- lead / follow / strategic / pilot / paying / etc
    partner_name TEXT,                    -- e.g. 投资人具体合伙人姓名
    board_seat BOOLEAN,                   -- 仅 investor 用
    valid_from DATE,
    valid_to DATE,                        -- NULL = 仍生效
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_relations_company_id ON company_relations(company_id);
CREATE INDEX idx_relations_entity ON company_relations(related_entity_name);
CREATE INDEX idx_relations_type ON company_relations(related_entity_type);


-- ============================================================
-- 4. conflicts — 待人工裁决冲突
-- ============================================================
CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    field_name TEXT NOT NULL,
    existing_value TEXT,                  -- JSON
    new_value TEXT,                       -- JSON
    existing_source TEXT,
    new_source TEXT,
    existing_source_tier INTEGER,
    new_source_tier INTEGER,
    reason TEXT,                          -- 为什么 flag 出来
    status TEXT DEFAULT 'pending',        -- pending / resolved / dismissed
    resolution TEXT,                      -- accept_new / keep_existing / merge / other
    resolved_value TEXT,                  -- JSON
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conflicts_status ON conflicts(status);
CREATE INDEX idx_conflicts_company_id ON conflicts(company_id);


-- ============================================================
-- 5. candidate_companies — 待人工审核的新发现对手
-- ============================================================
CREATE TABLE candidate_companies (
    id TEXT PRIMARY KEY,
    discovered_name TEXT NOT NULL,
    discovered_url TEXT,
    discovery_source TEXT NOT NULL,       -- 哪个 skill 发现的 / 哪个 URL
    discovery_reason TEXT,                -- LLM 解释为何认为是对手
    initial_evidence TEXT,                -- JSON,首次抓到的部分字段
    status TEXT DEFAULT 'pending',        -- pending / approved / rejected / duplicate
    rejection_reason TEXT,
    merged_into_company_id TEXT,          -- 如果 status=duplicate,指向已有公司
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_candidates_status ON candidate_companies(status);


-- ============================================================
-- 6. raw_signals — 所有原始抓取归档(3 年保留)
-- ============================================================
CREATE TABLE raw_signals (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    source_type TEXT,                     -- techcrunch / company_website / linkedin / etc
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_content TEXT,                     -- 原始 markdown / text
    extracted_events TEXT,                -- JSON array,这次抽取出来的 event IDs
    related_company_ids TEXT              -- JSON array
);

CREATE INDEX idx_signals_url ON raw_signals(source_url);
CREATE INDEX idx_signals_fetched_at ON raw_signals(fetched_at);
```

---

## 4. 核心算法

### 4.1 Entity Resolution(公司去重)

新公司或新 signal 进来时,判断"这家是否已经在 DB 里"。

```python
def resolve_company(name: str, url: str | None, linkedin: str | None,
                    hq: str | None, founders: list[str] | None,
                    db) -> tuple[str | None, float, str]:
    """
    Returns: (matched_company_id, confidence, match_method)
    """

    # === Layer 1: Deterministic match ===
    if url:
        domain = extract_domain(url)
        match = db.query("SELECT id FROM companies WHERE website LIKE ?",
                         f"%{domain}%")
        if match:
            return (match.id, 1.0, "domain_match")

    if linkedin:
        match = db.query("SELECT id FROM companies WHERE linkedin_url = ?",
                         linkedin)
        if match:
            return (match.id, 1.0, "linkedin_match")

    # === Layer 2: Fuzzy match ===
    candidates = db.query("SELECT id, canonical_name, hq_city FROM companies")

    from rapidfuzz import fuzz
    best_score = 0
    best_match = None
    for c in candidates:
        # 名字相似度
        name_score = fuzz.token_sort_ratio(name.lower(),
                                            c.canonical_name.lower()) / 100

        # 名字相似度 > 0.85 + HQ 一致 → 高置信
        if name_score > 0.85 and hq and c.hq_city and \
           fuzz.ratio(hq.lower(), c.hq_city.lower()) > 80:
            score = (name_score + 0.95) / 2
            if score > best_score:
                best_score = score
                best_match = c.id

        # 仅名字相似度 > 0.90 → 中置信
        elif name_score > 0.90:
            if name_score > best_score:
                best_score = name_score
                best_match = c.id

    if best_score > 0.85:
        return (best_match, best_score, "fuzzy_match")

    # === Layer 3: LLM tiebreaker (可选,只在 fuzzy 0.7-0.85 之间)===
    # 如果 fuzzy 给了 0.75 的中等分数,让 LLM 看两条 record 判断
    # 这里省略实现,需要时让 Claude 判断

    return (None, 0.0, "no_match")
```

**实操规则**:
- confidence > 0.95 → 自动 merge
- 0.85 ≤ confidence ≤ 0.95 → 自动 merge 但 flag review
- 0.7 ≤ confidence < 0.85 → 推到 conflicts 表,人工裁决
- confidence < 0.7 → 视为新公司,进 candidate_companies

### 4.2 Event Fingerprint(事件去重)

```python
import hashlib
from datetime import date, timedelta

def event_fingerprint(company_id: str, event_type: str,
                      event_date: date, payload: dict) -> str:
    """
    生成 event fingerprint,同一事件多 source 报道时哈希相同。
    """

    # date_bucket:不同事件类型用不同时间窗
    date_bucket_days = {
        "funding_round": 7,        # 同一周内同类型 = 同一事件
        "acquisition": 7,
        "leadership_change": 30,   # 同一月内同人 = 同一事件
        "product_launch": 1,       # 同一天
        "partnership": 7,
        "customer_win": 30,
        "hiring_signal": 30,
    }
    bucket_size = date_bucket_days.get(event_type, 7)
    bucket = event_date.toordinal() // bucket_size

    # key_value:从 payload 抽出最 distinctive 的字段
    if event_type == "funding_round":
        # 融资金额取整到 100K + 轮次类型
        amount = payload.get("amount_usd", 0)
        amount_bucket = round(amount / 100_000) if amount else 0
        round_type = payload.get("round_type", "unknown")
        key = f"{round_type}_{amount_bucket}"
    elif event_type == "acquisition":
        target = payload.get("target_name", "")
        key = target.lower().strip()
    elif event_type == "leadership_change":
        person = payload.get("person_name", "").lower().strip()
        role = payload.get("role", "").lower().strip()
        key = f"{person}_{role}"
    else:
        # 其他类型用 payload 关键字段拼接
        key = str(sorted(payload.items()))

    fingerprint_input = f"{company_id}|{event_type}|{bucket}|{key}"
    return hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]
```

**入库时使用**:

```python
def insert_event(company_id, event_type, event_date, payload, source_url, source_tier, db):
    fp = event_fingerprint(company_id, event_type, event_date, payload)

    existing = db.query("SELECT id, source_tier, cross_references FROM events WHERE fingerprint = ?", fp)

    if not existing:
        # 新事件,直接写
        db.insert("events", {
            "id": uuid4(),
            "company_id": company_id,
            "event_type": event_type,
            "event_date": event_date,
            "payload": json.dumps(payload),
            "fingerprint": fp,
            "source_url": source_url,
            "source_tier": source_tier,
            "cross_references": "[]",
        })
    else:
        # 已存在 → 合并
        if source_tier < existing.source_tier:
            # 新 source 优先级更高(数字越小越高),覆盖主字段
            db.update("events", existing.id, {
                "payload": json.dumps(payload),
                "source_url": source_url,
                "source_tier": source_tier,
            })

        # 把当前 source 加入 cross_references
        refs = json.loads(existing.cross_references)
        refs.append({"url": source_url, "tier": source_tier})
        db.update("events", existing.id, {"cross_references": json.dumps(refs)})
```

### 4.3 Source 优先级

```python
SOURCE_TIERS = {
    # Tier 1 - 最高
    "company_official_pr": 1,
    "company_website": 1,
    "investor_portfolio": 1,
    "sec_filing": 1,
    "asx_announcement": 1,

    # Tier 2 - 高
    "techcrunch": 2,
    "betakit": 2,
    "capital_brief": 2,
    "mining_com": 2,
    "globalminingreview": 2,
    "businesswire": 2,
    "prnewswire": 2,
    "globenewswire": 2,
    "crunchbase_funding": 2,    # Crunchbase 仅在 funding 字段算 Tier 2

    # Tier 3 - 中
    "pitchbook": 3,
    "linkedin": 3,
    "industry_interview": 3,
    "crunchbase_other": 3,      # Crunchbase 其他字段

    # Tier 4 - 低,仅交叉验证
    "tracxn": 4,
    "cbinsights": 4,
    "zoominfo": 4,
    "rocketreach": 4,
    "leadiq": 4,
    "golden_wiki": 4,
}

def classify_source(url: str) -> tuple[str, int]:
    """从 URL 推断 source 类型 + tier"""
    domain = extract_domain(url)
    # ... 简单 if/else mapping
```

### 4.4 SCD 字段更新规则

每个字段的更新策略:

```python
SCD_STRATEGY = {
    # Type 1: 直接覆盖,不留历史
    "founded_year": "type1",
    "last_updated": "type1",
    "hq_city": "type1",         # 搬家算 Type 1,只关心当前
    "hq_country": "type1",

    # Type 2: 字段变化生成新 event,旧值进 events history
    "canonical_name": "type2",          # 改名是大事
    "website": "type2",
    "target_customer": "type2",
    "core_product": "type2",
    "pricing_model": "type2",
    "business_model_summary": "type2",
    "status": "type2",

    # Type 4: companies 表只存 latest;events 表存所有
    "latest_round_type": "type4",
    "latest_round_amount_usd": "type4",
    "latest_round_date": "type4",

    # 关联表(本身就是 Type 2)
    "founders": "relations",
    "investors": "relations",
    "customers": "relations",
    "partners": "relations",
}
```

更新决策树:

```python
def update_field(company_id, field_name, new_value, new_source_url,
                 new_source_tier, new_confidence, db):
    strategy = SCD_STRATEGY[field_name]
    existing = db.get_company(company_id)
    existing_value = getattr(existing, field_name)

    # 值相同,无需更新
    if existing_value == new_value:
        return "no_change"

    # 决策:自动 vs 人工
    auto_accept = False

    # Rule 1: 现值为空 → 直接填
    if existing_value is None:
        auto_accept = True

    # Rule 2: 新 source 优先级更高 → 自动接受
    elif new_source_tier < existing.source_tier_for_field(field_name):
        auto_accept = True

    # Rule 3: 同 tier,新数据更新 + confidence 高 → 自动
    elif new_source_tier == existing.source_tier_for_field(field_name) \
         and new_confidence > 0.85:
        auto_accept = True

    # 其他 → flag 人工
    if not auto_accept:
        db.insert_conflict(company_id, field_name, existing_value,
                          new_value, new_source_url, new_source_tier,
                          reason="auto-resolve rules unmet")
        return "conflict_flagged"

    # 执行更新
    if strategy == "type1":
        db.update_company(company_id, {field_name: new_value})
    elif strategy in ("type2", "type4"):
        # 旧值进 events history
        db.insert_event(company_id, f"{field_name}_change", today(),
                       {"old": existing_value, "new": new_value},
                       new_source_url, new_source_tier)
        db.update_company(company_id, {field_name: new_value})

    return "updated"
```

### 4.5 Human-in-the-Loop Gates

**Gate 1 — 新公司加入**:`candidate_companies` 表 → 人工确认 → 转 `companies`

**Gate 2 — 字段冲突**:`conflicts` 表(上面 4.4 中触发)

**Gate 3 — 重大事件提醒**:funding / acquisition / leadership_change 三类事件,即使自动入库,也写入 Slack/Email 通知

**Gate 4 — LLM confidence 低**:event 的 confidence < 0.7 → 写入 conflicts 表

---

## 5. Skill 设计

每个 skill 一个目录,含 `SKILL.md` + Python helper。

### Skill 1: `scrape_competitor`

**目标**:输入公司名 + URL,输出该公司 13 个字段的最新 raw evidence。

**SKILL.md 内容**:

```markdown
# Scrape Competitor

抓取一家公司的全量信息,产出结构化 JSON。

## Inputs
- company_name (str)
- website_url (str, optional)
- linkedin_url (str, optional)
- last_scraped_at (datetime, optional) — 若提供,只抓增量

## Workflow

1. 抓官网首页 + /about + /team + /pricing + /careers (如果存在)
2. 搜索:`{company} funding round site:techcrunch.com OR site:betakit.com`
3. 搜索:`{company} CEO OR founder LinkedIn`
4. 抓 Crunchbase / PitchBook 公开页(若存在)
5. 把所有 raw text 喂给 LLM,按 schema 提取

## Output Schema (JSON)

{
  "company_name": str,
  "canonical_name": str,         # 标准化后的名字
  "website": str,
  "linkedin_url": str,
  "hq_city": str | null,
  "hq_country": str | null,
  "founded_year": int | null,
  "founders": [{"name": str, "role": str, "background": str, "linkedin": str}],
  "target_customer": str,
  "core_product": str,
  "pricing_model": str,
  "business_model_summary": str,  # 一句话
  "latest_round": {
    "type": str | null,           # seed / series_a / etc
    "amount_usd": float | null,
    "date": str | null,           # ISO date
    "lead_investors": [str],
    "other_investors": [str],
    "valuation_usd": float | null,
    "source_url": str | null
  },
  "funding_history": [...],       # 同上结构,所有轮次
  "investors": [{"name": str, "partner": str | null, "role": "lead"|"follow"|"strategic"}],
  "customers": [{"name": str, "evidence_url": str, "type": "anchor"|"pilot"|"named"}],
  "partners": [{"name": str, "type": str}],
  "tech_disclosure": {
    "architecture_claims": [str],
    "data_type": str,
    "stage_focus": str           # greenfield / brownfield / resource_def / production
  },
  "confidence_per_field": {field_name: float},  # 每字段自评 0-1
  "sources": [{"url": str, "tier": int, "fields_covered": [str]}]
}

## Rules

- 找不到 → null,不要编
- 多 source 冲突 → 优先 Tier 1(官网/PR)
- confidence 自评务必诚实:从单一来源 + 间接表述 = 0.5;多 source 一致 = 0.95
- 引用 source URL 必须真实存在,绝不编造
```

**Helper script** (`skills/scrape_competitor/run.py`):
- 实现 5 步抓取
- 调用 Claude API 做提取
- 返回结构化 JSON

### Skill 2: `extract_event`

**目标**:输入一段新闻文本,输出 event JSON。

**SKILL.md**:

```markdown
# Extract Event

从一段非结构化文本(新闻 / 公告)抽取一个或多个 event。

## Inputs
- text (str)
- source_url (str)
- source_type (str)        # techcrunch / company_pr / etc

## Output Schema

{
  "events": [
    {
      "event_type": str,    # 见 SQL schema 中的 enum
      "company_mentioned": str,    # 公司名(用于 entity resolution)
      "event_date": str,    # ISO date,文章发布或事件实际日期
      "payload": {...},     # 按 event_type 定制的字段
      "confidence": float,  # 0-1
      "raw_quote": str      # 文本中支持判断的关键句
    }
  ]
}

## Payload 字段定义(按 event_type)

funding_round:
  round_type, amount_usd, currency, lead_investors[], other_investors[],
  valuation_usd, valuation_disclosed (bool)

acquisition:
  target_name, acquirer_name, amount_usd, ownership_pct (e.g. 100 for full)

leadership_change:
  person_name, role, change_type ("join"|"leave"|"promote"), previous_company

partnership:
  partner_name, partnership_type, description (1 sentence)

customer_win:
  customer_name, deal_size_usd (optional), use_case (1 sentence)

product_launch:
  product_name, version, key_features[]

## Rules

- 一段文本里可能有多个 events,全部抽出
- raw_quote 必须是原文,不要改写
- 找不到日期 → 用 source URL 推断或留 null
```

### Skill 3: `discover_new_competitors`

**目标**:发现潜在新对手,进 candidate_companies 表。

**SKILL.md**:

```markdown
# Discover New Competitors

发现尚未在看板上的潜在竞品。

## Inputs
- known_companies (list[str])  — 已在看板上的公司列表
- industry_keywords (list[str]) — e.g. ["mineral exploration AI", "AI mining", "subsurface AI"]
- since_date (date)             — 只看这之后的信号

## Workflow

1. **Accelerator cohorts**:搜 YC / Techstars / EF / Founders Factory + Rio Tinto 等
   过去一年的 cohort 公告,筛矿业相关公司
2. **Funding announcements**:搜 industry_keywords + "raises" / "Series"
3. **arXiv**:`physics.geo-ph + cs.LG` 过去 6 个月论文,看作者所属机构里有无 startup
4. **Investor portfolio**:Khosla / a16z / Lux / 8090 等矿业 AI 活跃投资人最新投的 portfolio
5. **行业大会**:PDAC / IMARC / CESCO 演讲嘉宾名单
6. **M&A 信号**:监听 IMDEX 类 ASX-listed mining tech 公司的财报里 M&A 段落

## Output

{
  "candidates": [
    {
      "discovered_name": str,
      "discovered_url": str | null,
      "discovery_source": str,          # 哪个 workflow step 找到的
      "discovery_reason": str,          # 1-2 句解释为什么是对手
      "initial_evidence": {...},        # 部分已知字段
      "deduplication_check": {
        "matched_known": bool,          # 是否撞到已知公司
        "matched_id": str | null,
        "match_confidence": float
      }
    }
  ]
}

## Rules

- 撞到已知公司 → 仍然报告(标 matched_known=true),不要丢弃
- 必须给出 discovery_reason,空泛理由(e.g. "found on Crunchbase")无效
```

### Skill 4: `generate_weekly_digest`

**目标**:生成 CEO 周报。

**SKILL.md**:

```markdown
# Generate Weekly Digest

把过去 7 天的 events 总结成 CEO 周报 markdown。

## Inputs
- events (list[Event])           — 过去 7 天的事件
- companies (list[Company])      — 看板上的公司
- conflicts_pending (int)        — 待裁决冲突数
- candidates_pending (int)       — 待审核新对手数

## Output

Markdown 文档,结构:

# Competitive Intelligence Weekly — Week N, YYYY

## 🚨 High-Priority Events (融资 / 收购 / 高管变动)
(每条:公司名 + 事件简述 + source link + so what)

## 📊 New Partnerships / Customers
(列表)

## 👥 Team Changes
(列表)

## 📡 New Competitors Discovered
(进 candidate_companies 队列的)

## 📋 Action Items
- N conflicts pending review → [link]
- N candidate companies pending → [link]

## Rules

- "so what" 必须具体,e.g. "Terra AI Series A → 估值若超 $50M,
  接近 GeologicAI 估值梯队,可能加速 BD 攻势"
- 不编 so what;数据不足 → "so what: 信号待进一步观察"
```

---

## 6. Orchestrator(主调度逻辑)

`pipeline.py` 主结构:

```python
# pipeline.py
import argparse
from skills import scrape_competitor, extract_event, discover_new_competitors, generate_weekly_digest
from db import Database
from resolver import resolve_company, event_fingerprint, update_field

def daily_run():
    """每日:扫融资 / 收购 / 高管变动新闻"""
    db = Database("competitors.db")
    sources = [
        "https://techcrunch.com/category/startups/feed/",
        "https://betakit.com/feed/",
        # ... RSS feeds
    ]
    for source_url in sources:
        articles = fetch_rss(source_url)
        for article in articles:
            if article.published < yesterday():
                continue
            result = extract_event.run(article.text, article.url, classify_source(article.url))
            for event in result["events"]:
                company_id, conf, method = resolve_company(
                    event["company_mentioned"], None, None, None, None, db
                )
                if company_id is None:
                    db.insert_candidate(event)
                    continue
                if conf < 0.7:
                    db.insert_candidate(event)
                    continue
                insert_event_with_dedup(db, company_id, event)

def weekly_run():
    """每周:对每家公司跑 scrape_competitor 抓官网 + 招聘 JD diff"""
    db = Database("competitors.db")
    companies = db.get_companies(status="active")
    for c in companies:
        result = scrape_competitor.run(c.canonical_name, c.website, c.linkedin_url, c.last_updated)
        merge_scrape_into_db(db, c.id, result)

def monthly_run():
    """每月:全量复扫 + 发现新对手"""
    db = Database("competitors.db")
    # 1. 全量复扫
    companies = db.get_companies(status="active")
    for c in companies:
        result = scrape_competitor.run(c.canonical_name, c.website, c.linkedin_url, None)
        merge_scrape_into_db(db, c.id, result)
    # 2. 发现新对手
    known_names = [c.canonical_name for c in companies]
    new_cands = discover_new_competitors.run(
        known_companies=known_names,
        industry_keywords=["mineral exploration AI", "AI mining", "subsurface AI"],
        since_date=last_month()
    )
    for cand in new_cands["candidates"]:
        if not cand["deduplication_check"]["matched_known"]:
            db.insert_candidate(cand)

def digest_run():
    """每周生成 digest"""
    db = Database("competitors.db")
    events = db.get_events_since(days=7)
    companies = db.get_companies()
    conflicts = db.count_conflicts(status="pending")
    candidates = db.count_candidates(status="pending")
    digest_md = generate_weekly_digest.run(events, companies, conflicts, candidates)
    save_to_file(f"digests/week_{this_week()}.md", digest_md)
    # 可选:推送 Slack / Email


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("trigger", choices=["daily", "weekly", "monthly", "digest"])
    args = parser.parse_args()
    {"daily": daily_run, "weekly": weekly_run,
     "monthly": monthly_run, "digest": digest_run}[args.trigger]()
```

---

## 7. GitHub Actions Cron

`.github/workflows/daily.yml`:

```yaml
name: Daily Pipeline
on:
  schedule:
    - cron: '0 14 * * *'  # 每日 UTC 14:00 = 北京时间 22:00
  workflow_dispatch:        # 手动触发

jobs:
  daily:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python pipeline.py daily
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SERPER_API_KEY: ${{ secrets.SERPER_API_KEY }}
      - name: Commit DB updates
        run: |
          git config user.name "pipeline-bot"
          git config user.email "bot@example.com"
          git add competitors.db
          git diff --staged --quiet || git commit -m "daily update $(date +%Y-%m-%d)"
          git push
```

`.github/workflows/weekly.yml` 同结构,cron `0 14 * * 0`(周日),命令 `python pipeline.py weekly && python pipeline.py digest`。

`.github/workflows/monthly.yml` 同,cron `0 14 1 * *`(每月 1 号),命令 `python pipeline.py monthly`。

**注**:把 SQLite db 文件提交回 git 是 demo 阶段的偷懒做法,数据量大后必须切 Supabase / Postgres。

---

## 8. Streamlit 可视化

`app.py`:

```python
import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(layout="wide", page_title="Competitor Intel")

conn = sqlite3.connect("competitors.db")

tabs = st.tabs(["📊 Companies", "🕐 Timeline", "💰 Investor Map",
                "⚠️ Conflicts", "🔍 Candidates", "📰 Latest Events"])

with tabs[0]:
    df = pd.read_sql("SELECT * FROM companies WHERE status='active'", conn)
    st.dataframe(df, use_container_width=True)

with tabs[1]:
    # 时间轴视图:横轴时间,每行一家公司,点标记 events
    ...

with tabs[2]:
    # Investor cross-reference 视图
    rel = pd.read_sql("""
        SELECT r.related_entity_name as investor, r.partner_name,
               c.canonical_name as company, r.relation_subtype, r.board_seat
        FROM company_relations r
        JOIN companies c ON r.company_id = c.id
        WHERE r.related_entity_type = 'investor'
          AND (r.valid_to IS NULL)
    """, conn)
    # 透视:行=投资人,列=公司,值=role
    st.dataframe(rel.pivot_table(index="investor", columns="company",
                                  values="relation_subtype", aggfunc="first"))

with tabs[3]:
    pending = pd.read_sql("SELECT * FROM conflicts WHERE status='pending'", conn)
    st.dataframe(pending)
    # 每行加 "Accept new / Keep existing / Custom" 按钮
    ...

with tabs[4]:
    candidates = pd.read_sql(
        "SELECT * FROM candidate_companies WHERE status='pending'", conn)
    st.dataframe(candidates)
    # 每行加 "Approve / Reject / Mark duplicate" 按钮
    ...

with tabs[5]:
    events = pd.read_sql("""
        SELECT e.*, c.canonical_name FROM events e
        JOIN companies c ON e.company_id = c.id
        ORDER BY e.event_date DESC LIMIT 100
    """, conn)
    st.dataframe(events)
```

---

## 9. 实施顺序

按这个顺序 build,每步可验证:

** 1**:
- [ ] 建 SQLite db,跑 schema
- [ ] 手动插入 12 家已知公司(用之前查的数据)
- [ ] 起 Streamlit app,确认主看板能渲染

** 2**:
- [ ] Build `scrape_competitor` skill + Python runner
- [ ] 跑一遍,把 12 家公司的字段刷一次,验证 LLM 抽取质量

** 3**:
- [ ] Build `extract_event` skill
- [ ] Build `resolver.py`(entity resolution + fingerprint + SCD update)
- [ ] Build `pipeline.py daily` 命令,跑通一次

** 4**:
- [ ] Build `discover_new_competitors` skill
- [ ] Build `pipeline.py monthly` 命令
- [ ] 完善 Streamlit 的 Conflicts / Candidates 审核 tab

** 5**:
- [ ] Build `generate_weekly_digest` skill
- [ ] 配置 GitHub Actions 三个 cron
- [ ] 跑一周观察实际效果

---

## 10. 关键检查清单

实施时务必确认:

- [ ] 每个 LLM extract 都有 schema validation(Pydantic),失败重跑一次,二次失败进 dead letter
- [ ] 每个 event 都带 source_url,绝不允许"无 source 的事实"入库
- [ ] confidence 字段必填,从 LLM 自评得到,< 0.7 自动进 conflict
- [ ] event_fingerprint 必须 UNIQUE 索引,DB 层防重复
- [ ] 新公司加入主表必须经过 human approval(候选队列 → 审核 → 转入)
- [ ] 重大事件(funding / acquisition / leadership_change)即使自动入库也推送通知
- [ ] raw_signals 表保留所有原始抓取,3 年内不删,出问题可追溯
- [ ] 名字相似的公司(Octavia / Stratum 等)在 resolver 测试中显式 cover 到

---

## 11. 已知陷阱(我帮你查 12 家公司时遇到过的)

| 陷阱 | 应对 |
|---|---|
| Crunchbase / PitchBook 数据错(Terra AI 2016 vs 2023) | 永远以官网 / 官方 PR 为 Tier 1 |
| 同名公司混淆(Octavia AI vs Octavia Energy) | resolver 必须用 domain + HQ + founder 三因子验证 |
| 公司改名 / 收购后实体变化(Enersoft → GeologicAI;Datarock 被 IMDEX 收购) | status 字段 + Type 2 SCD,旧名进 history |
| Funding 数据冲突($150K Tracxn vs 实际规模) | flag 但保留两边数据,等其他 source 来 |
| Stealth 公司无公开信息(Octavia / Material Difference) | scrape_competitor 容忍 null,confidence 标 0.3 |
| Founders 数量不一致(官网 3 人 vs Crunchbase 2 人) | 关联表 + Type 2,每个 founder 独立记录,差异在 conflict 表 |
| 投资人混淆(Techstars cohort vs 官网列的 a16z) | 关联表 relation_subtype 区分;sponsor vs direct invest |
| 加拿大资源行业 private placement(TerraDX 的 Canaccord) | 投资人类型字段补一个 "investment_bank_pp",区分 VC |

---

## 12. 后续扩展路径(本期不做,留接口)

- 切 Postgres + pgvector(语义检索"找类似对手")
- 加双 LLM 交叉验证(只对融资 / 收购事件)
- 加 RSS feed manager(目前 hard-code,后期独立配置)
- 加 Slack / Email 集成(推送 high-priority events)
- 加 Notion / Airtable 双向同步(让非技术同事也能 review)
- LLM 升级到 agentic workflow(发现新对手时主动多轮调查)

---

**完。**

这份文档可直接交给 Claude Code,按 Section 9 顺序实施。每个 section 编号清晰,代码骨架可直接复用,SQL schema 拷贝即用,Skill 的 SKILL.md 直接当文件保存。
