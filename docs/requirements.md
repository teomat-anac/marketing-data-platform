# Requirements

What the product must do, written without technology choices. The technical plan builds on this document.

**Priority:** **MVP** = in the first working version · **Later** = after the MVP.

---

## 1. Problem and goals

An e-commerce company advertises on several channels. Every week its marketing manager wants to know which channels pay back. Today the data sits in different places: visits and sales in GA4, costs in each ad platform. Someone merges them by hand in a spreadsheet, so it's slow, error-prone, and each person ends up with slightly different numbers.

| # | Goal | Measured by |
|---|---|---|
| G1 | No manual work to get the weekly numbers | KPIs are available without anyone touching a spreadsheet |
| G2 | One version of the numbers | One documented rule decides which channel gets credit, the same for every channel |
| G3 | Move budget to channels that pay back | ROAS and CPA are comparable across paid channels |
| G4 | Numbers anyone can read | A plain-language commentary comes with the KPIs (v2, D31) |
| G5 | The client owns its data | Full history stays in the client's own cloud project |
| G6 | Reusable for the next client | A new client can be set up from configuration and infrastructure code, not by rewriting |

**Data available in this project:** GA4 e-commerce data for one store, **1 Nov 2020 – 31 Jan 2021**. That period includes Black Friday and Christmas. The project uses it up to **24 Jan 2021**, because purchase recording broke in the last week (`architecture.md` D18). There is no real ad-cost data, so it is simulated (FR-2).

**G3 with this data:** the sample has one real paid channel, Paid Search, so the comparison across paid channels has a single entry (Q1). The platform handles any number of paid channels: for a real client, each one is new rows from its ad connector, not new code.

---

## 2. Users

| Persona | Priority | Wants | Doesn't want |
|---|---|---|---|
| **Marketing manager** | Primary | Answers in ~10 minutes on Monday: what changed, why it matters, what to do. Numbers they can trust. | SQL, raw tables, figures that disagree between reports. |
| **Agency consultant** | Secondary | To set the platform up for a new client quickly and the same way every time. | Rebuilding things by hand for each client. |
| **Marketing analyst** | Later | To explore daily data, drill into channels and dates. | — |

---

## 3. User stories

### US-1 — KPIs per channel · Marketing manager · **MVP**
*As a marketing manager, I want spend, revenue, ROAS and CPA per channel for a period I choose, so that I can see which channels pay back.*
- Given a valid date range, I get one row per channel with: sessions, purchases, revenue, spend, ROAS, CPA, conversion rate.
- Unique users are not included in the MVP. They can't be summed over days: a user visiting on two days would count twice. See `architecture.md` D11.
- I can filter by a single channel.
- Channels with no spend show ROAS and CPA as **empty**, not 0.
- Period totals equal the sum of the daily values.

### US-2 — Daily trend · Marketing manager · **MVP**
*As a marketing manager, I want the same KPIs day by day, so that I can spot peaks and drops (e.g. Black Friday).*
- One row per day and channel for the chosen range, with an optional channel filter.
- A day with no activity for a channel shows zeros; the row is never missing, so charts and comparisons have no gaps.

### US-3 — Funnel · Marketing manager · **MVP**
*As a marketing manager, I want to see how many visits reach each step towards a purchase, so that I know where we lose them.*
- Steps: visit → view product → add to cart → begin checkout → purchase.
- For each step: the number of **sessions** that reached it, and the conversion rate from the previous step.
- Open funnel: a session counts at a step if it reached that step, whether or not it went through the earlier steps in order.
- Optional channel filter, e.g. "where do Paid Search visitors drop out?".
- A step that wasn't recorded on some days (a tracking gap) is shown as "not recorded", never as 0.

### US-4 — Comparison with the previous period · Marketing manager · **MVP**
*As a marketing manager, I want each KPI compared with the previous period of the same length, so that I see what changed.*
- For a 7-day range, the previous period is the 7 days before it.
- Each KPI shows the previous value, the absolute change and the % change.
- If the previous period falls outside the available data, the response says so instead of showing zeros.

### US-5 — Commentary · Marketing manager · **Later** (v2, `architecture.md` D31)
*As a marketing manager, I want a short written commentary on the numbers, so that I understand them without analysing tables.*
- 3–5 bullet points covering what changed, why it matters and what to do.
- Written in the configured language (default: Italian).
- Uses **only** numbers present in the data; it never invents figures.
- If the data is too thin to say something useful, it says so.
- Example of the expected tone:
  > • Paid Search: ROAS sceso da 6,8 a 5,1 (−25%) mentre la spesa è salita del 12%. Le vendite non hanno seguito l'aumento di budget: verificare le campagne con CPA più alto.

### US-6 — Reproducible setup · Agency consultant · **MVP**
*As a consultant, I want to create a complete environment from the repository, so that every client gets the same, working setup.*
- Starting from an empty cloud project, documented steps produce a working platform. No manual clicks except the documented one-off ones, such as billing.
- Running the setup again changes nothing.
- Tearing an environment down is a documented single step.

### US-7 — Configure for a new client · Agency consultant · **Later** (partly MVP)
*As a consultant, I want to adapt the platform to a new client by changing configuration only.*
- **v2:** the commentary language is a setting (it moved with the commentary, D31).
- **Later:** client name, channel rules, data sources and paid channels are configuration, not code.

### US-8 — Alerts · Marketing manager · **Later**
*As a marketing manager, I want to be warned when something looks broken, such as tracking stopping or a campaign spending without selling, so that I can react the same day.*

### US-9 — See it without technical tools · Marketing manager · **Later**
*As a marketing manager, I want the numbers in a dashboard and a weekly report (email/Slack), so that I don't need anyone to call an API for me.*
- In the MVP, access is through the API and its interactive documentation page. That's enough to demo, but not for a real manager.

---

## 4. Functional requirements

### Data
| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Use GA4 e-commerce events (visits, product views, cart, checkout, purchases, revenue) as the source of traffic and sales. | MVP |
| FR-2 | Provide ad cost per day, channel and campaign (spend, impressions, clicks). Here it is **simulated**, standing in for an ad-platform connector. Simulated cost must be plausible: it follows paid traffic, so that **ROAS changes when real sales change** and isn't fixed in advance. It has the same grain and metrics as a real ad-platform export, so a real connector could replace it without changes downstream. Details: [`data-sources.md`](data-sources.md). | MVP |
| FR-3 | Every visit is assigned exactly one channel by a documented rule. Unknown or anonymised values go to a catch-all channel and are never dropped. | MVP |
| FR-4 | One attribution rule, documented and applied to all channels. Decided by data exploration: last non-direct click on sessions (`architecture.md` D16). | MVP |
| FR-5 | Reprocessing the data gives the same result: no duplicates, no drift. | MVP |
| FR-6 | Data is refreshed daily. A manual run is acceptable in the MVP; a scheduled run comes later. | MVP / Later |

### Metrics
| ID | Requirement | Priority |
|---|---|---|
| FR-7 | Metrics follow the definitions in [`glossary.md`](glossary.md): sessions, purchases, revenue, spend, ROAS, CPA, conversion rate. Ratios for a period are computed from period totals, never by averaging daily ratios. | MVP |
| FR-8 | All money is in one currency: USD, the currency of the source data. | MVP |
| FR-9 | Data is stored per day and can be aggregated to any date range. | MVP |

### Access
| ID | Requirement | Priority |
|---|---|---|
| FR-10 | KPIs per channel for a date range, with an optional channel filter (US-1). | MVP |
| FR-11 | Daily KPI series (US-2). | MVP |
| FR-12 | Funnel for a date range (US-3). | MVP |
| FR-13 | Comparison with the previous period (US-4). | MVP |
| FR-14 | Commentary on a date range (US-5). | Later (v2, D31) |
| FR-15 | Date ranges are validated: inside the available data, start ≤ end. Invalid input gets a clear error message. | MVP |
| FR-16 | Only authenticated callers can access the data. | MVP |
| FR-17 | Dashboard and weekly report (US-9). | Later |
| FR-18 | Anomaly alerts (US-8). | Later |

---

## 5. Non-functional requirements

| Area | Requirement |
|---|---|
| **Cost** | Runs for a few euros a month at most, ideally within free tiers. Every data query has a cost cap. A budget alert is active. |
| **Security** | Nothing is publicly accessible. No credentials in the repository. Each component has only the permissions it needs. |
| **Trust** | The commentary (v2) contains no numbers that aren't in the data (US-5). Metric definitions are documented in one place. |
| **Reproducibility** | The whole platform can be recreated from the repository (US-6). |
| **Response time** | Target: KPI and funnel requests under 2 s; commentary (v2) under 30 s. |
| **Language** | Commentary language (v2) is a setting, default Italian. Code and docs are in English. |
| **Data ownership** | All data stays in the client's own cloud project. |

---

## 6. Out of scope (for now)

- Unique users over a period (possible later with BigQuery HyperLogLog sketches; see `architecture.md` D11)
- Dashboard and weekly email/Slack report (US-9)
- Anomaly alerts (US-8)
- A simulated "today", so that "last week" is relative to a moving date and the data is replayed day by day
- Analyst drill-down features
- Multiple clients in one deployment; configuration-only onboarding (US-7, beyond the v2 language setting)
- Real ad-platform connectors (Google Ads, Meta)
- Forecasting, customer segmentation, LTV
- Conversational assistant on the data (chat, MCP)
- A production environment separate from dev

---

## 7. Questions answered by data exploration

These questions were answered by exploring the data; findings are in [`data-sources.md`](data-sources.md) §5.

| # | Question | Why it matters | Status |
|---|---|---|---|
| Q1 | Which paid channels actually exist in the GA4 data? | If there's only Paid Search, "compare channels" becomes "compare campaigns", and the marts need campaign-level rows. | **Closed:** Paid Search only; campaign names are hidden too, so marts stay at day × channel (D15) |
| Q2 | Attribution: credit the channel of the *visit* (last click) or the channel the user *first* came from (first touch)? | Decides which channel gets each sale (FR-4). | **Closed:** last non-direct click on sessions, ignoring self-referrals (D16) |
| Q3 | Revenue definition: does it include tax and shipping? How are refunds handled? | Decides what "revenue", and therefore ROAS, means. | **Closed:** product value without tax, before refunds (none in the data) (D17) |
| Q4 | How to count purchases? GA4 can record the same order more than once. | Purchases should be unique orders (`transaction_id`), not raw purchase events. | **Closed:** one order per (`transaction_id`, user); purchases without an ID count too (D17) |
| Q5 | The final list of channels | Needed for the channel rule (FR-3) and the data tests. | **Closed:** GA4's default channel names, nine channels (D19) |
