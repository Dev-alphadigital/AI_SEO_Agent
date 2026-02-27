# Priority 1 Validation Setup — Complete

All Priority 1 requirements from your checklist have been implemented and enforced.

---

## What Was Created

### 1. **Priority 1 Validation Checklist** 
   📄 `.planning/PRIORITY_1_VALIDATION.md`
   
   Complete documentation of all 9 Priority 1 requirements with:
   - Detailed criteria for each check
   - Verification steps
   - Source/tool identification
   - Failure actions
   - Error handling procedures

### 2. **SEO Brief Workflow**
   📄 `.planning/SEO_BRIEF_WORKFLOW.md`
   
   Step-by-step workflow that enforces Priority 1 checks:
   - Phase 1: Input & Validation
   - Phase 2: Data Collection (scraping)
   - Phase 3: Analysis
   - Phase 4: Brief Generation
   - Phase 5: Quality Assurance
   - Phase 6: Final Validation

### 3. **Validation Script**
   📄 `validate_brief.py`
   
   Automated Python script that validates any SEO brief against Priority 1 requirements.

### 4. **GSC (Google Search Console) Client** — Must Have
   📄 `app/gsc_client.py` — Python module for GSC API
   📄 `fetch_gsc.py` — CLI to fetch GSC performance data
   📄 `.planning/GSC_SETUP.md` — Setup instructions
   
   GSC data (clicks, impressions, avg position, top queries) is required for SEO briefs. Configure per GSC_SETUP.md.

---

## Priority 1 Requirements Enforced

| # | Requirement | Status |
|---|------------|--------|
| 1 | URL Verification | ✅ Enforced |
| 2 | GSC Data Present | ✅ Enforced |
| 3 | Current Metadata Captured | ✅ Enforced |
| 4 | Current Heading Structure Captured | ✅ Enforced |
| 5 | Recommended Title + Description | ✅ Enforced |
| 6 | Heading Comparison Table | ✅ Enforced |
| 7 | Keyword Targets with MSV | ✅ Enforced |
| 8 | No Hallucinations/Guarantees | ✅ Enforced |
| 9 | Tone Alignment | ✅ Enforced |

## Priority 2 Requirements (Consistency)

| # | Requirement | Status |
|---|-------------|--------|
| P2-1 | Current top queries (GSC) vs Target keywords (form) clearly separated | ✅ Enforced |
| P2-2 | Both sections labeled in every brief | ✅ Enforced |
| P2-3 | Consistent section order | ✅ Enforced |

---

## How to Use

### GSC (Must Have for Briefs)

```bash
# 1. Configure GSC — see .planning/GSC_SETUP.md
#    - Add credentials/gsc-service-account.json
#    - Add service account to Search Console

# 2. Verify: python check_gsc.py https://yoursite.com/

# 3. Create brief (always includes GSC data)
python create_brief.py https://yoursite.com/ "your keyword"
```

### For Manual Brief Creation

1. **Follow the workflow:** `.planning/SEO_BRIEF_WORKFLOW.md`
2. **Reference the checklist:** `.planning/PRIORITY_1_VALIDATION.md`
3. **Validate before finalizing:** Run `validate_brief.py`

### For Automated Validation

```bash
# Validate any brief
python validate_brief.py output/brief_sesky_pk_20260219.md

# Output shows:
# - [OK] Passed: X/9
# - [WARN] Warnings: X
# - [FAIL] Errors: X
```

### Example Output

```
============================================================
SEO Brief Validation Report - Priority 1 Checklist
============================================================

Brief: brief_sesky_pk_20260219.md

[OK] Passed: 8/9
[WARN] Warnings: 0
[FAIL] Errors: 1

[ACTION REQUIRED] Brief needs corrections:
  [FAIL] Current metadata not captured (title or meta description missing)
```

---

## Key Requirements for Scraping

**MANDATORY:** When scraping any website for SEO briefs:

1. ✅ **URL must be verified** — Open URL, confirm it matches target
2. ✅ **Metadata must match page source exactly** — Compare scrape output to View Source
3. ✅ **Heading structure must preserve hierarchy** — H1 → H2 → H3, no skipping
4. ✅ **GSC data must be accurate** — Filter by exact URL, verify top queries align
5. ✅ **No placeholder text** — If scraping fails, note "manual verification required"

**Scraping Accuracy is Non-Negotiable** — Incorrect scraped data invalidates the entire brief.

---

## Integration with Existing Workflow

The Priority 1 requirements are now integrated into:

- ✅ SEO brief generation workflow
- ✅ Validation script (automated checks)
- ✅ Documentation (reference guides)

**Next Steps:**
- When building Python scraping backend, ensure it follows Priority 1 validation
- When using n8n workflows, include validation step before finalizing briefs
- Always run `validate_brief.py` before marking brief as complete

---

## Files Created

```
AI_SEO_Agent/
├── app/
│   ├── __init__.py
│   └── gsc_client.py               ← GSC API client (Priority 1)
├── .planning/
│   ├── PRIORITY_1_VALIDATION.md    ← Complete checklist
│   ├── SEO_BRIEF_WORKFLOW.md       ← Workflow with Priority 1 enforcement
│   └── GSC_SETUP.md                ← GSC setup (must complete)
├── fetch_gsc.py                    ← Fetch GSC data for briefs
├── validate_brief.py               ← Automated validation script
└── PRIORITY_1_SETUP.md            ← This file (summary)
```

---

**All Priority 1 requirements are now enforced and documented.**

*Last Updated: 2026-02-19*
