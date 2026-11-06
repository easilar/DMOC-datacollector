# DMOC-datacollector

Example statistics requested by the CMS DMOC for Glance, built on **synthetic data**.
None of the numbers describe real CMS members: the dataset is randomly generated, and some
trends (e.g. fewer nominations for women, a slow rise of women at entry) were added on purpose
so the plots have something to show.

## Contents

| Path | What it is |
|---|---|
| `make_fake_dmoc_data.py` | Generates the synthetic dataset and every plot |
| `dmoc_fake_person_year.csv` | Synthetic data: one row per person per active year, 2008–2026 |
| `plots/` | One PNG per plot |
| `dmoc_fake_plots.pdf` | All plots in one file |

## Running

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python make_fake_dmoc_data.py
```

The random seed is fixed, so a rerun reproduces the same data and plots.

## Data model (`dmoc_fake_person_year.csv`)

One row per person per year in which they were active in CMS.

| Column | Meaning |
|---|---|
| `person_id`, `year` | Member key and calendar year |
| `gender`, `nationality`, `nationality_region` | As recorded |
| `institute`, `institute_region` | Home institute and its region |
| `cms_join_year`, `cms_leave_year` | First and last year in CMS (leave year empty if still active) |
| `phd_year`, `years_since_phd` | PhD year (empty before the PhD) and academic age |
| `glance_category` | What Glance has today: Physicist / Doctoral Student |
| `stage`, `contract`, `stage_contract` | Doctoral student / Postdoc / Staff, permanent or non-permanent |
| `leadership_roles` | Every role held that year, e.g. `L3;L2` (`None` if none) |
| `holds_L3`, `holds_L2`, `holds_L1`, `holds_SP` | One flag per level; a person holding several roles counts at each level |
| `nominations`, `appointments`, `talks` | Counts in that year |
| `left_cms_this_year` | True in the person's last active year if they left |

## Plots

| File | Plot |
|---|---|
| `1a_pipeline_career_stage_by_year` | % women by career stage, one line per year, and per stage over time |
| `1b_pipeline_leadership_by_year` | Same for L3 / L2 / L1 / Spokesperson team |
| `1c_…`, `1d_…` | Pooled 2022–2026 versions of 1a and 1b, with the region mix |
| `1e_…`, `1f_…` | Home-institute region shares, year by year, by career stage and by leadership level |
| `2_glass_ceiling_index` | GCI = % women in eligible pool ÷ % women in role |
| `3_nomination_vs_success` | Nominations per person-year (pool: all members) and success rate |
| `4_time_to_first_role` | Years to first L3 / L2, measured from the PhD and from joining CMS |
| `5_talk_allocation` | Talks per eligible person per year |
| `6_retention_attrition` | Attrition by stage, and general retention since joining CMS by gender and region |
| `6b_retention_by_join_period` | Kaplan-Meier retention per joining period (2009–14, 2015–20, 2021–26) |

## Definitions used

- **L3 eligible pool:** all active members, doctoral students included (L3 has no formal criteria).
- **L2, L1, Spokesperson-team pools:** placeholders until DMOC agrees on them (`eligible_pool()` in the script).
- **Leadership counting:** each role is a separate position; someone holding L3 and L2 counts at both levels.
- **Uncertainties:** 1σ from absolute counts (binomial for shares, Poisson for rates, Greenwood for Kaplan-Meier).
