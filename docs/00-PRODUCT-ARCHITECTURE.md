# Skillected Jobs — Product Architecture

**Verified IT Opportunities. Direct Company Applications.**
Positioning: **Skillected Jobs Intelligence Platform** — not a job portal.

---

## 1. Product loop

```
IT JOB MARKET → JOB DISCOVERY → JOB VERIFICATION → JOB INTELLIGENCE
→ CANDIDATE MATCHING → SKILL GAP ANALYSIS → SKILLECTED LEARNING
→ DIRECT APPLICATION → INTERVIEW → PLACEMENT OUTCOME
```

The platform connects **MARKET → OPPORTUNITIES → SKILLS → CANDIDATES → TRAINING →
APPLICATIONS → INTERVIEWS → PLACEMENTS → MARKET INSIGHTS**.

---

## 2. Core differentiator (non-negotiable rules)

1. **Direct application first.** Every published job links to the company's own career
   page / ATS application URL. Never redirect to aggregators (Naukri, Indeed, LinkedIn,
   Glassdoor, Foundit, Shine, TimesJobs, Internshala, …) when a legitimate direct
   application exists.
2. **Verification before publication.** Jobs below the admin-configured authenticity
   threshold are never auto-published (§54).
3. **Truth over spectacle.** Never fabricate statistics, posting dates, salaries,
   applicant counts, or hiring trends. Unknown ⇒ "Not specified" / "Unable to verify" (§86).
4. **Freshness honesty.** `Posted X ago` only when the company posting date is verified;
   otherwise `First seen X ago` (§7).
5. **AI assists, deterministic systems decide** (§56): AI never owns application URL,
   posting date, job status, company identity, duplicates, verification, or expiry.

---

## 3. Module map (§80)

| Module | Responsibility | Phase |
|---|---|---|
| auth | sessions, RBAC, CSRF, rate limiting | 1 |
| users / candidates | accounts, profiles, preferences | 1 (minimal), 4–5 |
| companies | company registry + profiles | 1 |
| sources | career source registry + health | 1 (registry), 2 (health) |
| jobs | job repository, listings, detail | 1 |
| job-ingestion | crawler orchestration, normalization | 2 |
| verification | authenticity score, expiry, fraud flags | 2 |
| classification | domain/role/skill tagging | 2 |
| matching | resume ↔ job scoring | 4 |
| recommendations | feeds, alerts | 5 |
| notifications / whatsapp / posters / qr | content + distribution automation | 3 |
| analytics | event tracking, placement radar, trends | 2 (radar), 7 (trends) |
| placement | pipeline, outcomes | 6 |
| courses / skills | taxonomy + Skillected course bridge | 4–7 |
| search | full-text + semantic | 1 (FTS), later semantic |
| alerts | personal job alerts | 5 |
| admin | dashboards, review queue, automation settings | 1+ |

---

## 4. Key scoring systems

### 4.1 Freshness engine (§7)

| Age | Label |
|---|---|
| 0–30 min | 🔥 JUST POSTED |
| 30 min–2 h | ⚡ VERY FRESH |
| 2–6 h | 🟢 NEW |
| 6–12 h | 🔵 RECENT |
| 12–24 h | 🟣 TODAY |
| 1–3 days | RECENT |
| 3+ days | OLDER |

Sort priority: **freshness → relevance → verification score**.

### 4.2 Live/recent status (§8)

🟢 Open — verified < 1 h ago · 🟡 Open — last verified < 24 h ago · 🔴 Application closed.

### 4.3 Authenticity score (§9), 0–100

Deterministic signals: official company domain match, official career page, valid
requisition ID, working application URL, company identity match, posting-date
verification, job availability, redirect safety, source reliability, suspicious-content
detection.

| Band | Meaning |
|---|---|
| 90–100 | Highly Trusted |
| 75–89 | Verified |
| 60–74 | Needs Review |
| < 60 | Do Not Publish |

### 4.4 Source tiers (§10)

Tier 1 official careers site · Tier 2 official ATS (Workday, Greenhouse, Lever,
SmartRecruiters, SuccessFactors, Oracle, Ashby, iCIMS, Taleo — company verified) ·
Tier 3 other permitted public source. Each source has a reliability score; admin can
override.

### 4.5 Application Opportunity Score (§21, §90)

Inputs only from real data: freshness, fresher eligibility, skill alignment, location
alignment, application still open, verification. **Never claims applicant counts.**

### 4.6 AI match (§32, Phase 4)

skills 35% · experience 20% · title similarity 15% · education 10% · location 10% ·
tech stack 5% · domain 5% → bands EXCELLENT/STRONG/GOOD/POSSIBLE/LOW, always with a
plain-language explanation and stretch opportunities (§33–34).

---

## 5. Geographic focus (§3)

Primary: Pune + PCMC micro-markets (Hinjewadi, Wakad, Baner, Kharadi, Viman Nagar,
Magarpatta, Hadapsar, Yerwada, Kalyani Nagar, Koregaon Park, Shivajinagar, Aundh,
Balewadi, Talegaon, Chakan, Ranjangaon).
Secondary: Mumbai, Navi Mumbai, Thane, Nashik, Nagpur, Chhatrapati Sambhajinagar,
Kolhapur. Work modes: On-site / Hybrid / Remote.

---

## 6. Career domain taxonomy (§1, extensible)

Full Stack · Data Science & AI/ML · Data Analytics · Business Analysis · DevOps & Cloud ·
Cybersecurity · Embedded Systems & IoT · QA & Testing · Other IT (Mobile, DevSecOps, DBA,
Network, IT Support, Product, UI/UX, SAP, Salesforce, ServiceNow, RPA, Blockchain, Game
Dev, Technical Writing). Stored in `domains` table; seed data covers all of the above.

---

## 7. Trust model (§87)

Every published job displays: ✓ company ✓ title ✓ location ✓ experience ✓ source ✓
direct application URL ✓ verification status ✓ last-verified time. This block is the
product's central trust mechanism.

---

## 8. Non-goals for Phase 1

Live crawling (Phase 2), resume AI (Phase 4), WhatsApp/poster/QR automation (Phase 3),
placement pipeline (Phase 6), market trends (Phase 7). The architecture reserves their
seams (source registry, event outbox, taxonomy, provider layer) so they bolt on without
redesign (§89).
