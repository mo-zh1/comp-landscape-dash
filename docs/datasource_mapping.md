# 📁 skills.md: 竞争情报采集与校验方法论

## 1. 核心定位 (Mission)
作为一名高级商业情报分析师，在执行“竞争对手调研”与自动化 Pipeline 构建时，必须严格遵循 **“官网优先、多源交叉、动态监控”** 的原则，拒绝盲目采信第三方数据库。

---

## 2. 信息源映射表 (Data Source Mapping)
这是自动化的基础。没有这张表，后续的 Pipeline 将无法运行。

| 字段 (Fields) | Primary Source (第一信源) | Secondary Source (第二信源) | 数据特性 (Data Characteristics) |
| :--- | :--- | :--- | :--- |
| **Company Name / Website** | 公司官网 | LinkedIn company page | 静态，几乎不变 |
| **Founders + Background** | 官网 /team /about 页 | LinkedIn personal + Crunchbase founder list | 半静态，founder 变动是大事件 |
| **Founded Year** | Crunchbase + LinkedIn + 公司官网 | PitchBook (常有冲突，见 Terra AI 案例) | 静态 |
| **Target Customer + Core Product** | 官网 /product /solutions 页 | TechCrunch / PR 报道 | 半静态 |
| **Pricing Model** | 官网 /pricing 页 (极少披露) | 行业访谈 (BNamericas / Canadian Mining Journal) | 大多不公开 |
| **Latest Round / Funding** | TechCrunch + PR Newswire + BusinessWire + BetaKit | Crunchbase + PitchBook + Tracxn + CBInsights | 事件驱动，新闻爆发后 24-48h 落库 |
| **Investors** | 公司 PR + Lead 投资人 Portfolio 页 + TechCrunch | Crunchbase + PitchBook | 事件驱动 |
| **Partners / Customers** | 公司官网 Logo 墙 + Press Releases | 行业新闻 (Mining.com / Australian Mining / Global Mining Review) + 客户 PR | 高频更新，信号最密集 |
| **Team Size / Headcount** | LinkedIn company page (自动统计) | RocketReach / LeadIQ / ZoomInfo | 每月-每季度变化 |
| **Tech Architecture** | 公司 Blog / Medium / arXiv 论文 + 公开 Podcast 访谈 | TechCrunch / 行业杂志 (Canadian Mining Journal) | 半年-一年大变动 |
| **Valuation** | TechCrunch + PR (披露时) | PitchBook / Crunchbase Pro (付费) | 多数公司主动不披露 |
| **HQ / Geography** | LinkedIn + 官网 Footer | Crunchbase (常错——见 Mineral Forecast 案例) | 静态 |

---

## 3. 实操 SOP 核心规则 (Operational Rules)

### Rule 1: 权限等级 (The "Truth" Hierarchy)
**永远以“公司官网 + 公司 PR”为 Source of Truth。**
* Crunchbase / PitchBook 经常出错（例如：Terra AI 2016 vs 2023 / Mineral Forecast Cambridge vs Santiago 都是教训）。
* 第三方数据库仅作为 **Fallback**，绝非 Primary Source。

### Rule 2: 实时性策略 (Latency Management)
**主流科技媒体与行业垂直媒体是融资事件的最快通道。**
* TechCrunch / BetaKit 的更新通常比 Crunchbase 早 1-7 天。
* 若要构建“接近实时”的看板，**RSS 监听**这些媒体比轮询数据库 API 更快、更高效。

### Rule 3: 隐形信号挖掘 (The "Hidden" Signal)
**LinkedIn 的招聘 JD (Job Description) 是免费的战略情报。**
* 团队在哪里扩张、招什么岗位，比公司公开的公关声明要“诚实”得多（参考 Durin、4Point AI 案例）。

### Rule 4: 行业垂直媒体覆盖度 (Industry-Specific Media)
**行业垂直媒体的深度高于通用型科技媒体。**
* 必须固定监听以下 6-8 个核心媒体：
    1.  Mining.com
    2.  Australian Mining
    3.  International Mining
    4.  Canadian Mining Journal
    5.  Global Mining Review
    6.  Mining Beacon
