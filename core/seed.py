"""Seed the database with the 11 known companies from the CSV."""
from .db import Database

COMPANIES = [
    {
        "canonical_name": "Terra AI",
        "website": "https://www.terraai.com",
        "hq_city": "Palo Alto", "hq_country": "US", "founded_year": 2023,
        "target_customer": "Mining and energy majors",
        "core_product": "Generative AI (diffusion models) for 3D subsurface modeling + reasoning agent",
        "pricing_model": "Enterprise SaaS — direct sales + strategic partnerships",
        "stage_focus": "greenfield",
        "latest_round_type": "seed", "latest_round_amount_usd": 3_390_000, "latest_round_date": "2023-10-01",
        "business_model_summary": "Enterprise B2B AI platform (SaaS) — sold via direct sales + strategic partnerships to mining & energy majors",
        "technical": "Diffusion models / generative models (confirmed, multi-source). Generates \"millions of possible 3D subsurface models conditioned to match the signal\" + \"reasoning agent\" for campaign planning. Data = real multimodal: drill cores + geophysics + geochemistry (synthetic data only as model output, not training input).",
        "stage_description": "Multi-stage: Target Screening (greenfield/undercover) + Survey Design + Dynamic Drilling (resource definition)",
        "latest_round_text": "Seed · $3.39M · Oct 2023 (publicly announced 2025 when emerging from stealth)",
        "funding_trajectory": "NSF grants → Seed $3.39M (2023, led by Khosla Ventures) → Rio Tinto strategic investment (2025) → Series A upcoming (announced intent, not closed)",
        "investors_text": "Khosla Ventures (lead), Rio Tinto (strategic, 2025), Storyhouse Ventures, Plug and Play, TomKat Center for Sustainability (Stanford), Climate Capital, US National Science Foundation",
        "valuation": "Undisclosed (Seed $3.4M 2023, Khosla lead; no valuation disclosed)",
        "status": "active", "confidence_score": 0.95,
    },
    {
        "canonical_name": "TerraDX",
        "website": "https://www.linkedin.com/company/terradx-technologies/",
        "hq_city": "Vancouver", "hq_country": "Canada", "founded_year": 2023,
        "target_customer": "Mining sector",
        "core_product": "HORIZON Deep Neural Network for regional ore targeting (98% area reduction)",
        "pricing_model": "B2B SaaS — direct deals & strategic partnerships",
        "stage_focus": "greenfield",
        "latest_round_type": "pre_seed", "latest_round_amount_usd": 1_500_000, "latest_round_date": "2024-04-01",
        "business_model_summary": "B2B AI platform (SaaS) for mining sector — early-stage, GTM via direct deals & strategic partnerships (e.g., Battery X Metals JV)",
        "technical": "HORIZON Deep Neural Network (DNN) + Databricks Mosaic AI platform. Data = real public geological survey data — Geological Survey of New South Wales (Australia, Central Lachlan Orogen) geophysics + exploration data. No diffusion / no synthetic data / no satellite imagery.",
        "stage_description": "Greenfield / regional targeting (HORIZON reduces area of interest by 98% before onsite exploration)",
        "latest_round_text": "Pre-Seed · $1.5M total raised (date not publicly disclosed; per PitchBook)",
        "funding_trajectory": "Spun out of Durendal Resources Inc. → Public launch April 2024 → Pre-Seed $1.5M (Canaccord Genuity, Haywood Securities, Research Capital) → NVIDIA Inception (July 2024, non-equity accelerator)",
        "investors_text": "Canaccord Genuity, Haywood Securities Inc., Research Capital",
        "valuation": "Undisclosed (Pre-Seed $1.5M; investors are Canadian investment banks/brokers, no valuation disclosed)",
        "status": "active", "confidence_score": 0.85,
    },
    {
        "canonical_name": "GeologicAI",
        "website": "https://www.geologicai.com",
        "hq_city": "Calgary", "hq_country": "Canada", "founded_year": 2013,
        "target_customer": "Mining majors",
        "core_product": "AI core scanning trailers (on-site) + AI software subscription for resource characterization",
        "pricing_model": "Hardware + software subscription + services hybrid",
        "stage_focus": "resource_def",
        "latest_round_type": "series_b", "latest_round_amount_usd": 44_000_000, "latest_round_date": "2025-07-17",
        "business_model_summary": "B2B hardware + software + services hybrid for mining majors — on-site core-scanning trailers (operated by GeologicAI) + AI software subscription, expanding via M&A (RMS, Lumo Analytics)",
        "technical": "Convolutional Neural Networks (CNN) — \"trained on millions of validated mineral samples\". Data = real multi-sensor core scan data: XRF (X-ray fluorescence) + hyperspectral (SWIR + VNIR) + magnetic susceptibility + LiDAR + RGB imagery + LIBS (via Lumo acquisition). No diffusion / no synthetic data / no satellite imagery.",
        "stage_description": "Resource definition + characterization + production optimization (scans already-drilled cores, does NOT do greenfield prediction)",
        "latest_round_text": "Series B · $44M USD / $60.5M CAD · Jul 17, 2025 (all-equity, led by Blue Earth Capital)",
        "funding_trajectory": "Bootstrapped/early grants → Series A $30M USD (Jul 2023, led by Breakthrough Energy Ventures $20M + Export Development Canada $10M) → Series B $44M USD (Jul 2025, led by Blue Earth Capital). Total raised: ~$74M USD",
        "investors_text": "Series A: Breakthrough Energy Ventures (lead, Bill Gates-backed), Export Development Canada. Series B: Blue Earth Capital (lead, Swiss impact investor), BHP Ventures, Rio Tinto, Breakthrough Energy Ventures (follow-on), other undisclosed returning investors",
        "valuation": "Undisclosed (Series B $44M USD Jul 2025 — BetaKit confirmed Segal declined to disclose valuation)",
        "status": "active", "confidence_score": 0.98,
        "notes": '{"prior_name": "Enersoft (oil & gas, pivoted to mining 2021)"}',
    },
    {
        "canonical_name": "Datarock",
        "website": "https://www.imdex.com/software/datarock",
        "linkedin_url": "https://www.linkedin.com/company/datarock/",
        "hq_city": "Melbourne", "hq_country": "Australia", "founded_year": 2018,
        "target_customer": "Mining companies (full mining cycle)",
        "core_product": "Computer vision for core/chip imagery analytics (CNN-based, Detectron2/PyTorch)",
        "pricing_model": "Software subscription + Applied Science consulting (wholly owned by IMDEX)",
        "stage_focus": "greenfield,resource_def,production",
        "latest_round_type": "acquired", "latest_round_amount_usd": None, "latest_round_date": "2026-02-01",
        "business_model_summary": "Wholly-owned AI/geoscience software subsidiary of IMDEX Limited (ASX:IMD) — production-ready, explainable AI core/chip imagery analytics + Applied Science consulting; ~64 employees; consolidated into IMDEX's Digital Earth Knowledge portfolio",
        "technical": "Computer vision / image segmentation — CNN-based (Detectron2 framework on PyTorch), including ResNet34-based mask models, instance + semantic segmentation, OCR. Data = real core photography (RGB) + airborne + satellite data; expert annotations supervised training (177+ manually annotated image tiles). No diffusion claim.",
        "stage_description": "Multi-stage: exploration + resource definition + production (full mining cycle)",
        "latest_round_text": "N/A — 100% acquired by IMDEX. Most recent event: Feb 1, 2026 IMDEX completed remaining 49% acquisition ~A$31M (USD $21.5M), achieving 100% ownership",
        "funding_trajectory": "2018: Solve+Dius JV origin → Nov 2021: IMDEX acquires initial 30% (A$5.5M) → Nov 2021–Jul 2024: increased to 51% (incremental investments) → Feb 1, 2026: acquired remaining 49% completing 100% ownership (A$31M). Cumulative IMDEX paid: est. A$60M+",
        "investors_text": "IMDEX Limited (ASX:IMD) — sole owner. IMDEX is Perth-headquartered, founded 1980, ASX-listed company, CEO Paul House. No external shareholders beyond IMDEX.",
        "valuation": "Implied ~A$63M / USD ~$45M (IMDEX 2026/2/1 acquired remaining 49% for A$31M, implied 100% valuation ~A$63M) — acquisition-implied, not market valuation",
        "status": "acquired", "confidence_score": 0.98,
    },
    {
        "canonical_name": "4Point Geophysical AI",
        "website": "https://4point.ai",
        "hq_city": None, "hq_country": "Canada", "founded_year": 2024,
        "target_customer": "Mining + government (DoE, KSA)",
        "core_product": "SIIM (Spatially Informed Intelligence Model) — GNN + RL + Physics-Informed Inversion for predictive ore mapping",
        "pricing_model": "SaaS + possible royalty/success-fee hybrid",
        "stage_focus": "greenfield",
        "latest_round_type": "pre_seed", "latest_round_amount_usd": None, "latest_round_date": "2024-01-01",
        "business_model_summary": "Pre-Seed AI/ML predictive ore mapping platform — GTM via government procurement (DoE, KSA) + accelerators (Techstars, CDL, Google for Startups); possible hybrid SaaS + royalty/success-fee model",
        "technical": "GNN-Hybrid (Graph Neural Networks) + Reinforcement Learning (RL) + Physics-Informed Inversion (explicit multi-technology stack). SIIM = Spatially Informed Intelligence Model. Outputs \"physics-informed realizations\" with uncertainty volumes. Data types not clearly publicly disclosed (language implies real geophysics + drill data, but not officially confirmed).",
        "stage_description": "Multi-stage: Target Screening (greenfield) + Survey Design + Drill Prioritization",
        "latest_round_text": "Pre-Seed · amount not publicly disclosed · 2024 (Techstars FW24 cohort)",
        "funding_trajectory": "Pre-Seed (2024, via Techstars FW24 LA accelerator, JPM-sponsored cohort) — that's the only round on record",
        "investors_text": "Techstars (Techstars LA Fall/Winter 2024 cohort, lead), Google for Startups Accelerator Canada, J.P. Morgan (sponsor of Techstars LA cohort). Website also lists Spatial Capital and ID3 Ventures as investors (not on Crunchbase/PitchBook)",
        "valuation": "Undisclosed (Pre-Seed, amount not disclosed)",
        "status": "active", "confidence_score": 0.80,
    },
    {
        "canonical_name": "VERAI",
        "website": "https://ver-ai.com",
        "hq_city": "Tel Aviv", "hq_country": "Israel", "founded_year": 2020,
        "target_customer": "Mineral explorers and developers",
        "core_product": "AI Discovery Platform — identifies concealed deposits, owns/optionizes mineral licenses, monetizes via JVs",
        "pricing_model": "Equity stakes + royalties via JVs (not a SaaS vendor)",
        "stage_focus": "greenfield",
        "latest_round_type": "series_b", "latest_round_amount_usd": 24_000_000, "latest_round_date": "2025-02-26",
        "business_model_summary": "B2B AI-driven mineral asset portfolio generator — uses proprietary AI Discovery Platform to identify concealed deposits, owns/optionizes mineral licenses, monetizes via equity stakes + royalties through JVs with explorers/developers (not a SaaS vendor)",
        "technical": "AI/ML + \"Defense Intelligence search & find methodologies\" (founder background). \"AI Search Profiles\" library, trained on different classes of economic orebodies + geological settings. Data = real multimodal geophysics: magnetic + gravimetric + electromagnetic + seismic. No diffusion claim / no specific architecture disclosed / no synthetic data (explicitly states \"pure machine learning\").",
        "stage_description": "Greenfield / concealed deposits in covered terrains (explicitly does NOT do brownfield — focused on \"undiscovered deposits beneath cover\")",
        "latest_round_text": "Series B · $24M (first closing) · Feb 26, 2025 (led by Insight Partners)",
        "funding_trajectory": "Seed/Series A early rounds (2020–2023, specifics not fully disclosed) → Series B $24M first closing (Feb 2025, Insight Partners lead). Total raised ~$39.4–39.6M (per PitchBook & CBInsights)",
        "investors_text": "Insight Partners (Series B lead, Jeff Horing on board), Blumberg Capital (Stanton Green on board), Chrysalix Venture Capital (Charles Haythornthwaite on board), Orion Industrial Ventures / Orion Resource Partners (OIV), funds advised by T. Rowe Price Associates",
        "valuation": "Undisclosed (Series B first closing $24M Feb 2025, Insight Partners lead; total raised $39.6M; no public valuation)",
        "status": "active", "confidence_score": 0.93,
    },
    {
        "canonical_name": "Fleet Space Technologies",
        "website": "https://www.fleetspace.com",
        "hq_city": "Adelaide", "hq_country": "Australia", "founded_year": 2015,
        "target_customer": "Mining majors (Rio Tinto, Barrick Gold, Ma'aden)",
        "core_product": "ExoSphere — multimodal AI + proprietary LEO satellite network + Geode smart seismic sensors",
        "pricing_model": "Exploration-as-a-service (end-to-end, not SaaS)",
        "stage_focus": "greenfield",
        "latest_round_type": "series_d", "latest_round_amount_usd": 100_000_000, "latest_round_date": "2024-12-12",
        "business_model_summary": "Vertically-integrated exploration-as-a-service platform — proprietary LEO satellite network + smart seismic sensors (Geode) + multimodal AI (ExoSphere); end-to-end service delivery model (not SaaS); Series D $100M @ $525M valuation, 130+ employees globally",
        "technical": "Multimodal AI foundation model (company claims \"world-first multimodal foundation model for critical mineral discovery\"). Building: Full Waveform Inversion (FWI) accelerated by Fourier Neural Operators (FNO) — claims 100× faster than traditional methods. Data = real multi-physics: 3D Ambient Noise Tomography (ANT) + Magnetotelluric (MT) + Gravity + HVSR + Active Seismic + IP + drilling data, collected via proprietary Geode sensors + LEO satellite telemetry. No diffusion claim; satellites used for data transmission not imaging.",
        "stage_description": "Multi-stage: focus on pre-drill targeting + survey + full exploration lifecycle",
        "latest_round_text": "Series D · USD $100M (A$150M) · Dec 11–12, 2024 · at USD $525M (A$800M+) valuation (led by Teachers' Venture Growth)",
        "funding_trajectory": "Early Seed/A/B (specifics not fully disclosed) → Series C A$50M (May 2023, led by Blackbird Ventures) → Series D A$150M (Dec 2024, led by TVG) at A$800M+ valuation (valuation doubled in 19 months)",
        "investors_text": "Series D Lead: Teachers' Venture Growth (TVG, Ontario Teachers' Pension Plan growth arm). Returning: Blackbird Ventures (Australia, prior Series C lead), Hostplus (Australian superannuation), Horizons Ventures (Hong Kong, Li Ka-shing), Artesian Venture Partners (Australia), Alumni Ventures (US). Earlier: Grok Ventures (Mike Cannon-Brookes family office)",
        "valuation": "✅ USD $525M (A$800M+) (Series D Dec 11–12, 2024 — only company in cohort with disclosed valuation)",
        "status": "active", "confidence_score": 0.99,
    },
    {
        "canonical_name": "Mineral Forecast",
        "website": "https://www.mineralforecast.com",
        "hq_city": "Santiago", "hq_country": "Chile", "founded_year": 2014,
        "target_customer": "Mining & exploration companies (LATAM-focused: Chile, Peru, Mexico)",
        "core_product": "Multi-model ML SaaS for greenfield and brownfield mineral discovery",
        "pricing_model": "SaaS — public 3-tier pricing",
        "stage_focus": "greenfield,brownfield",
        "latest_round_type": "seed", "latest_round_amount_usd": 3_310_000, "latest_round_date": "2023-09-12",
        "business_model_summary": "B2B SaaS for mining & exploration — most product-mature in cohort (public 3-tier pricing, full SaaS GTM motion, named customers like First Majestic / SQM); deep LATAM lock-in (Chile + Peru + Mexico) via 10-year operating history",
        "technical": "Multi-model ML approach (no single architecture claim) — supervised learning (e.g. predicting copper grade using drillhole data) + unsupervised learning (identifying alteration zones). Data = real multi-source: satellite imagery + geochemical surveys + drilling logs + geophysics + public geological data. No diffusion / no foundation model claim.",
        "stage_description": "Explicitly multi-stage: greenfield (claim staking) + brownfield + existing mine optimization (\"supports each greenfield and brownfield drilling target\")",
        "latest_round_text": "$20K Seed (Techstars Boston F23 cohort, Sep 12, 2023) ⚠️ This is standard Techstars cohort investment only; additional ~$3.3M from other investors, specific rounds not clearly disclosed",
        "funding_trajectory": "Harvard Innovation Labs incubation → Harvard Venture Incubation Program → Launch Lab X → Techstars Boston F23 ($20K, Sep 2023) → subsequent unattributed VC rounds → total raised $3.31–3.32M (PitchBook / CBInsights)",
        "investors_text": "Techstars (Boston F23), Alumni Ventures, Spider Capital Partners, Launch Lab X, Harvard Venture Incubation Program + 4 undisclosed investors (CBInsights / PitchBook list 9 total investors)",
        "valuation": "Undisclosed (total raised ~$3.31M; no valuation disclosed)",
        "status": "active", "confidence_score": 0.90,
    },
    {
        "canonical_name": "Material Difference",
        "website": "https://materialdifference.earth",
        "hq_city": "London", "hq_country": "UK", "founded_year": 2024,
        "target_customer": "Critical mineral explorers",
        "core_product": "Uncertainty-aware + explainable AI for critical mineral exploration",
        "pricing_model": None,
        "stage_focus": "resource_def",
        "latest_round_type": "pre_seed", "latest_round_amount_usd": None, "latest_round_date": "2026-03-31",
        "business_model_summary": "Stealth-mode Pre-Seed startup — uncertainty-aware + explainable AI for critical mineral exploration; backed by Entrepreneurs First (talent investor) + Founders Factory/Rio Tinto accelerator; 2 founders, recruiting founding engineer, no public product yet",
        "technical": "Publicly stated differentiation = uncertainty quantification + explainable AI + value-of-information (decision theory); specific ML architecture not public (not diffusion, no GNN / foundation model claim — still in stealth)",
        "stage_description": "Resource delineation + ore body knowledge (language implies brownfield / resource definition stage, not pure greenfield)",
        "latest_round_text": "Pre-Seed via Entrepreneurs First (EF) — standard EF talent investment, amount not separately disclosed (EF typically £100K for ~10% equity)",
        "funding_trajectory": "EF Pre-Seed (talent investor, amount not disclosed) → Founders Factory + Rio Tinto Mining Tech Accelerator selected (March 2026 cohort, publicly announced March 31, 2026)",
        "investors_text": "Entrepreneurs First (EF) — London-based \"talent investor\", invests in founders before company formation, typical deal $100K for ~10%. Founders Factory + Rio Tinto accelerator (2026 spring cohort, 1 of 6 companies) — not traditional VC, but provides funding + Rio Tinto operational pilot access",
        "valuation": "Undisclosed (Pre-Seed via Entrepreneurs First — EF standard ~£100K; amount + valuation both not publicly disclosed)",
        "status": "stealth", "confidence_score": 0.60,
    },
    {
        "canonical_name": "Stratum AI",
        "website": "https://stratum.gs",
        "hq_city": "Toronto", "hq_country": "Canada", "founded_year": 2019,
        "target_customer": "Production-stage mines globally",
        "core_product": "SAIGE (Stratum AI Geospatial Estimator) — AI resource modeling + block models for grade control",
        "pricing_model": "SaaS + Forward Deployed Engineers (Palantir-style)",
        "stage_focus": "production,brownfield",
        "latest_round_type": "seed", "latest_round_amount_usd": 150_000, "latest_round_date": "2020-08-26",
        "business_model_summary": "B2B AI resource modeling SaaS + Forward Deployed Engineer services for production-stage mines — Palantir-style GTM (embed engineers + custom deployment), funded minimally via YC seed but operating at unusual scale (18 mines globally; funding history likely incomplete)",
        "technical": "Deep Learning (per Mining Beacon: \"proprietary Machine Learning technology (Deep Learning)\"). SAIGE = Stratum AI Geospatial Estimator. Outputs block models (resource + grade control). Data = real mine site data: diamond/RC drillholes + grade control + blasthole samples + rock-chip samples. No diffusion / no synthetic data / no satellite imagery.",
        "stage_description": "Production-stage mines + brownfield exploration (explicitly NOT greenfield — this is a core positioning differentiator)",
        "latest_round_text": "Seed · $150K · Aug 26, 2020 (led by Y Combinator)",
        "funding_trajectory": "Seed undisclosed (Jun 2019) → YC Seed $150K (Aug 2020) → undisclosed subsequent funding rounds. Total public funding only $150K",
        "investors_text": "Y Combinator (lead, S20 batch), Builders VC, Two Small Fish Ventures, Soma Capital, J Seventeen Capital (1 undisclosed investor, 6 total institutional investors per Tracxn)",
        "valuation": "Undisclosed (YC public $150K seed; remaining funding not in public databases; no valuation disclosed)",
        "status": "active", "confidence_score": 0.88,
    },
    {
        "canonical_name": "Octavia",
        "website": "https://www.octaviatech.com",
        "hq_city": None, "hq_country": None, "founded_year": None,
        "target_customer": None, "core_product": None, "pricing_model": None,
        "stage_focus": None,
        "latest_round_type": None, "latest_round_amount_usd": None, "latest_round_date": None,
        "business_model_summary": "Stealth-mode — no public information available.",
        "technical": None, "stage_description": None, "latest_round_text": None,
        "funding_trajectory": None, "investors_text": None, "valuation": None,
        "status": "stealth", "confidence_score": 0.30,
    },
]

# Relations: (company canonical_name, entity_name, entity_type, subtype, partner, board_seat, source_url)
RELATIONS = [
    # Terra AI
    ("Terra AI", "Khosla Ventures", "investor", "lead", None, False, "https://techcrunch.com"),
    ("Terra AI", "Rio Tinto", "investor", "strategic", None, False, "https://www.terraai.com"),
    ("Terra AI", "Storyhouse Ventures", "investor", "follow", None, False, None),
    ("Terra AI", "Plug and Play", "investor", "follow", None, False, None),
    # TerraDX
    ("TerraDX", "Canaccord Genuity", "investor", "lead", None, False, None),
    ("TerraDX", "Haywood Securities", "investor", "follow", None, False, None),
    ("TerraDX", "NVIDIA Inception", "partner", "accelerator", None, False, None),
    # GeologicAI
    ("GeologicAI", "Breakthrough Energy Ventures", "investor", "lead", None, False, "https://betakit.com"),
    ("GeologicAI", "Blue Earth Capital", "investor", "lead", None, False, "https://betakit.com"),
    ("GeologicAI", "Export Development Canada", "investor", "follow", None, False, None),
    ("GeologicAI", "BHP Ventures", "investor", "strategic", None, False, None),
    ("GeologicAI", "Rio Tinto", "investor", "strategic", None, False, None),
    # Datarock
    ("Datarock", "IMDEX Limited", "acquirer", "full_acquisition", None, False, "https://www.imdex.com"),
    # 4Point
    ("4Point Geophysical AI", "Techstars", "investor", "accelerator", None, False, None),
    ("4Point Geophysical AI", "Google for Startups", "partner", "accelerator", None, False, None),
    ("4Point Geophysical AI", "J.P. Morgan", "investor", "cohort_sponsor", None, False, None),
    # VERAI
    ("VERAI", "Insight Partners", "investor", "lead", "Jeff Horing", True, "https://www.businesswire.com"),
    ("VERAI", "Blumberg Capital", "investor", "follow", "Stanton Green", True, None),
    ("VERAI", "Chrysalix Venture Capital", "investor", "follow", "Charles Haythornthwaite", True, None),
    ("VERAI", "Orion Resource Partners", "investor", "strategic", None, False, None),
    # Fleet Space
    ("Fleet Space Technologies", "Teachers' Venture Growth", "investor", "lead", None, False, "https://www.fleetspace.com"),
    ("Fleet Space Technologies", "Blackbird Ventures", "investor", "follow", None, False, None),
    ("Fleet Space Technologies", "Horizons Ventures", "investor", "follow", None, False, None),
    ("Fleet Space Technologies", "Hostplus", "investor", "follow", None, False, None),
    ("Fleet Space Technologies", "Rio Tinto", "customer", "anchor", None, False, None),
    ("Fleet Space Technologies", "Barrick Gold", "customer", "anchor", None, False, None),
    # Mineral Forecast
    ("Mineral Forecast", "Techstars", "investor", "accelerator", None, False, None),
    ("Mineral Forecast", "Alumni Ventures", "investor", "follow", None, False, None),
    ("Mineral Forecast", "First Majestic", "customer", "named", None, False, None),
    ("Mineral Forecast", "SQM", "customer", "named", None, False, None),
    # Material Difference
    ("Material Difference", "Entrepreneurs First", "investor", "lead", None, False, None),
    ("Material Difference", "Founders Factory", "partner", "accelerator", None, False, None),
    ("Material Difference", "Rio Tinto", "partner", "strategic", None, False, None),
    # Stratum AI
    ("Stratum AI", "Y Combinator", "investor", "lead", None, False, None),
    ("Stratum AI", "Soma Capital", "investor", "follow", None, False, None),
    ("Stratum AI", "Builders VC", "investor", "follow", None, False, None),
]

# Founder relations
FOUNDERS = [
    ("Terra AI", "John Mern", "founder", "CEO", "https://www.terraai.com/about"),
    ("Terra AI", "Anthony Corso", "founder", "CTO", "https://www.terraai.com/about"),
    ("TerraDX", "Colby Mintram", "founder", "CEO", None),
    ("GeologicAI", "Grant Sanden", "founder", "CEO", "https://www.geologicai.com"),
    ("GeologicAI", "Yannai Segal", "founder", "CSO", "https://www.geologicai.com"),
    ("4Point Geophysical AI", "Cody Zazulak", "founder", "CEO", "https://4point.ai"),
    ("4Point Geophysical AI", "Jordan Zazulak", "founder", "CTO", "https://4point.ai"),
    ("VERAI", "Yair Frastai", "founder", "CEO", "https://ver-ai.com"),
    ("VERAI", "Amitai Axelrod", "founder", "COO", "https://ver-ai.com"),
    ("Fleet Space Technologies", "Flavia Tata Nardini", "founder", "CEO", "https://www.fleetspace.com"),
    ("Fleet Space Technologies", "Matt Pearson", "founder", "CXO", "https://www.fleetspace.com"),
    ("Mineral Forecast", "Javier Muñoz González", "founder", "CEO", "https://www.mineralforecast.com"),
    ("Mineral Forecast", "Arturo Rochefort Rojas", "founder", "COO", "https://www.mineralforecast.com"),
    ("Material Difference", "Gabriel Yoong", "founder", "Co-founder", "https://materialdifference.earth"),
    ("Material Difference", "Luke Cullen", "founder", "Co-founder", "https://materialdifference.earth"),
    ("Stratum AI", "Farzi Yusufali", "founder", "CEO", "https://stratum.gs"),
    ("Stratum AI", "Danial Hasan", "founder", "CTO", "https://stratum.gs"),
]

# Seed funding events (fingerprint generated from payload)
FUNDING_EVENTS = [
    ("Terra AI", "seed", 3_390_000, "2023-10-01", ["Khosla Ventures"], "https://techcrunch.com", 2),
    ("Terra AI", "strategic", None, "2025-01-01", ["Rio Tinto"], "https://www.terraai.com", 1),
    ("TerraDX", "pre_seed", 1_500_000, "2024-04-01", ["Canaccord Genuity", "Haywood Securities"], None, 3),
    ("GeologicAI", "series_a", 30_000_000, "2023-07-01", ["Breakthrough Energy Ventures", "Export Development Canada"], "https://betakit.com", 2),
    ("GeologicAI", "series_b", 44_000_000, "2025-07-17", ["Blue Earth Capital", "BHP Ventures", "Rio Tinto"], "https://betakit.com", 2),
    ("VERAI", "series_b", 24_000_000, "2025-02-26", ["Insight Partners"], "https://www.businesswire.com", 2),
    ("Fleet Space Technologies", "series_c", 37_000_000, "2023-05-01", ["Blackbird Ventures"], "https://www.fleetspace.com", 2),
    ("Fleet Space Technologies", "series_d", 100_000_000, "2024-12-12", ["Teachers' Venture Growth"], "https://www.fleetspace.com", 1),
    ("Mineral Forecast", "seed", 3_310_000, "2023-09-12", ["Techstars", "Alumni Ventures"], None, 3),
    ("Stratum AI", "seed", 150_000, "2020-08-26", ["Y Combinator"], None, 2),
]


def run():
    db = Database()
    db.init_schema()

    name_to_id: dict[str, str] = {}

    # insert or update companies (upsert by canonical_name)
    upsert_fields = [
        "website", "hq_city", "hq_country", "founded_year",
        "target_customer", "core_product", "pricing_model", "stage_focus",
        "latest_round_type", "latest_round_amount_usd", "latest_round_date",
        "business_model_summary", "technical", "stage_description",
        "latest_round_text", "funding_trajectory", "investors_text", "valuation",
        "status", "confidence_score",
    ]
    for c in COMPANIES:
        existing = db._one(
            "SELECT id FROM companies WHERE canonical_name = ?", (c["canonical_name"],)
        )
        if existing:
            cid = existing["id"]
            update_data = {f: c.get(f) for f in upsert_fields if f in c}
            db.update_company(cid, update_data)
            print(f"  updated: {c['canonical_name']}")
        else:
            cid = db.insert_company(c)
            print(f"  inserted: {c['canonical_name']} → {cid}")
        name_to_id[c["canonical_name"]] = cid

    # insert relations (investors/customers/partners)
    for comp_name, entity, etype, subtype, partner, board, src in RELATIONS:
        cid = name_to_id.get(comp_name)
        if not cid:
            continue
        exists = db._one(
            """SELECT id FROM company_relations
               WHERE company_id=? AND related_entity_name=? AND related_entity_type=?""",
            (cid, entity, etype),
        )
        if not exists:
            db.insert_relation(
                {
                    "company_id": cid,
                    "related_entity_name": entity,
                    "related_entity_type": etype,
                    "relation_subtype": subtype,
                    "partner_name": partner,
                    "board_seat": board,
                    "source_url": src,
                    "confidence": 0.9,
                }
            )

    # insert founders
    for comp_name, person, etype, role, src in FOUNDERS:
        cid = name_to_id.get(comp_name)
        if not cid:
            continue
        exists = db._one(
            """SELECT id FROM company_relations
               WHERE company_id=? AND related_entity_name=? AND related_entity_type='founder'""",
            (cid, person),
        )
        if not exists:
            db.insert_relation(
                {
                    "company_id": cid,
                    "related_entity_name": person,
                    "related_entity_type": "founder",
                    "relation_subtype": role,
                    "source_url": src,
                    "confidence": 0.95,
                }
            )

    # insert funding events
    from resolver import event_fingerprint
    from datetime import date as _date

    for comp_name, round_type, amount, ev_date_str, investors, src, tier in FUNDING_EVENTS:
        cid = name_to_id.get(comp_name)
        if not cid:
            continue
        try:
            ev_date = _date.fromisoformat(ev_date_str)
        except Exception:
            continue
        payload = {
            "round_type": round_type,
            "amount_usd": amount,
            "lead_investors": investors[:1],
            "other_investors": investors[1:],
        }
        fp = event_fingerprint(cid, "funding_round", ev_date, payload)
        if not db.get_event_by_fingerprint(fp):
            db.insert_event(
                {
                    "company_id": cid,
                    "event_type": "funding_round",
                    "event_date": ev_date_str,
                    "payload": payload,
                    "fingerprint": fp,
                    "source_url": src,
                    "source_tier": tier,
                    "confidence": 0.9,
                    "extracted_by": "seed",
                }
            )

    print(f"\nDone. {len(COMPANIES)} companies, {len(RELATIONS)+len(FOUNDERS)} relations, {len(FUNDING_EVENTS)} events.")
    db.close()


if __name__ == "__main__":
    run()
