"""
FAKE CMS membership data + example DMOC plots for the Glance requirements ticket.

Everything here is synthetic. Built-in biases are invented so the plots show
something; they are NOT estimates of real CMS numbers.

Output (next to this script):
  dmoc_fake_person_year.csv   one row per person per active year
  plots/*.png                 one figure per requested plot category
  dmoc_fake_plots.pdf         all figures in one file

Run:  python make_fake_dmoc_data.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

rng = np.random.default_rng(2026)
HERE = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(HERE, "plots")
os.makedirs(PLOTS, exist_ok=True)

Y0, Y1 = 2008, 2026

# ----------------------------------------------------------------------------
# Fake attribute catalogues
# ----------------------------------------------------------------------------
REGIONS = {
    # region: (share of new members, fake nationalities)
    "Western Europe": (0.34, ["Italy", "Germany", "France", "Spain", "Belgium", "Switzerland", "UK"]),
    "Eastern Europe": (0.14, ["Poland", "Hungary", "Bulgaria", "Croatia", "Greece", "Serbia"]),
    "North America":  (0.24, ["USA", "Canada", "Mexico"]),
    "Asia":           (0.16, ["China", "India", "Korea", "Pakistan", "Taiwan", "Thailand"]),
    "Latin America":  (0.06, ["Brazil", "Colombia", "Chile", "Ecuador"]),
    "Africa & Middle East": (0.06, ["Egypt", "Iran", "Turkey", "Lebanon", "South Africa"]),
}
REGION_NAMES = list(REGIONS)
REGION_P = np.array([REGIONS[r][0] for r in REGION_NAMES])
REGION_P /= REGION_P.sum()
INSTITUTES = {r: [f"{r[:3].upper()}-Inst-{i:02d}" for i in range(1, 9)] for r in REGION_NAMES}

# Invented effects (multipliers) that the plots will "reveal"
TALK_REGION_MULT = {"Western Europe": 1.1, "Eastern Europe": 0.85, "North America": 1.15,
                    "Asia": 0.8, "Latin America": 0.75, "Africa & Middle East": 0.7}
NOMINATION_W = 0.8          # women nominated less often...
SUCCESS_W = 1.0             # ...but succeed at the same rate once nominated

N_ROLES = {"L3": 300, "L2": 80, "L1": 22, "Spokesperson team": 3}
TERM = {"L3": 2, "L2": 2, "L1": 2, "Spokesperson team": 2}
LEVELS = ["L3", "L2", "L1", "Spokesperson team"]
HOLD = {"L3": "holds_L3", "L2": "holds_L2", "L1": "holds_L1", "Spokesperson team": "holds_SP"}


def new_person(pid, year, stage):
    p_w = {"Doctoral student": 0.33, "Postdoc": 0.28, "Staff": 0.20}[stage]
    p_w += 0.005 * (year - 2017)      # invented slow improvement over time at entry
    nat_region = REGION_NAMES[rng.choice(len(REGION_NAMES), p=REGION_P)]
    # 25% work at an institute in another region (mostly W. Europe / N. America)
    if rng.random() < 0.25:
        inst_region = rng.choice(["Western Europe", "North America", nat_region], p=[0.5, 0.35, 0.15])
    else:
        inst_region = nat_region
    if stage == "Doctoral student":
        phd_year = np.nan
    elif stage == "Postdoc":
        phd_year = year - rng.integers(0, 4)
    else:
        phd_year = year - rng.integers(4, 20)
    return dict(
        person_id=f"P{pid:05d}",
        gender="Woman" if rng.random() < p_w else "Man",
        nationality=rng.choice(REGIONS[nat_region][1]),
        nationality_region=nat_region,
        institute=rng.choice(INSTITUTES[inst_region]),
        institute_region=inst_region,
        cms_join_year=year,
        cms_leave_year=np.nan,
        phd_year=phd_year,
        stage=stage,
        permanent=(stage == "Staff" and rng.random() < 0.7) or (stage == "Postdoc" and rng.random() < 0.08),
        years_in_stage=0,
        student_years=rng.integers(3, 6),
        roles={},                      # level -> last year of mandate; several levels at once allowed
        ever={l: None for l in LEVELS},   # year of first appointment per level
        active=True,
    )


def eligible(p, level, year):
    if level == "L3":                 # no formal criteria: every member, doctoral students included
        return True
    if p["stage"] == "Doctoral student":
        return False
    age = year - p["phd_year"]
    if level == "L2":
        return p["ever"]["L3"] is not None or (p["stage"] == "Staff" and age >= 8)
    if level == "L1":
        return p["ever"]["L2"] is not None
    return p["ever"]["L1"] is not None


# ----------------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------------
people, rows, pid = [], [], 0
for stage, n in [("Doctoral student", 1100), ("Postdoc", 900), ("Staff", 1300)]:
    for _ in range(n):
        p = new_person(pid, Y0, stage)
        p["cms_join_year"] = Y0 - rng.integers(0, 10)
        people.append(p); pid += 1

for year in range(Y0, Y1 + 1):
    # newcomers
    if year > Y0:
        for stage, n in [("Doctoral student", 260), ("Postdoc", 90), ("Staff", 40)]:
            for _ in range(rng.poisson(n)):
                people.append(new_person(pid, year, stage)); pid += 1
    active = [p for p in people if p["active"]]
    for p in active:
        p["nominations"] = p["appointments"] = 0

    # leadership: free expired mandates, then fill vacancies via nominations.
    # Roles at different levels are separate positions: one person can hold e.g. L3 and L2 at once.
    for level in reversed(LEVELS):
        for p in active:
            if p["roles"].get(level, year) < year:
                del p["roles"][level]
        holders = [p for p in active if level in p["roles"]]
        vacancies = N_ROLES[level] - len(holders)
        pool = [p for p in active if eligible(p, level, year) and level not in p["roles"]]
        for _ in range(max(vacancies, 0)):
            if len(pool) < 3:
                break
            w = np.array([NOMINATION_W if p["gender"] == "Woman" else 1.0 for p in pool])
            w *= np.array([{"Staff": 1.3, "Postdoc": 1.0, "Doctoral student": 0.3}[p["stage"]] for p in pool])
            k = min(len(pool), rng.integers(2, 5))
            idx = rng.choice(len(pool), size=k, replace=False, p=w / w.sum())
            cands = [pool[i] for i in idx]
            for c in cands:
                c["nominations"] += 1
            s = np.array([SUCCESS_W if c["gender"] == "Woman" else 1.0 for c in cands])
            win = cands[rng.choice(len(cands), p=s / s.sum())]
            win["appointments"] += 1
            win["roles"][level] = year + TERM[level] - 1
            if win["ever"][level] is None:
                win["ever"][level] = year
            pool.remove(win)

    # talks (Poisson, rate per person-year)
    for p in active:
        base = {"Doctoral student": 0.9, "Postdoc": 1.3, "Staff": 0.8}[p["stage"]]
        rate = base * (0.85 if p["gender"] == "Woman" else 1.0) * TALK_REGION_MULT[p["institute_region"]]
        p["talks"] = rng.poisson(rate)

    # record the year
    for p in active:
        rows.append(dict(
            person_id=p["person_id"], year=year, gender=p["gender"],
            nationality=p["nationality"], nationality_region=p["nationality_region"],
            institute=p["institute"], institute_region=p["institute_region"],
            cms_join_year=p["cms_join_year"],
            phd_year=p["phd_year"],
            years_since_phd=(year - p["phd_year"]) if not np.isnan(p["phd_year"]) else np.nan,
            glance_category="Doctoral Student" if p["stage"] == "Doctoral student" else "Physicist",
            stage=p["stage"],
            contract="Permanent" if p["permanent"] else "Non-permanent",
            leadership_roles=";".join(l for l in LEVELS if l in p["roles"]) or "None",
            **{HOLD[l]: l in p["roles"] for l in LEVELS},
            nominations=p["nominations"], appointments=p["appointments"], talks=p["talks"],
            left_cms_this_year=False,
        ))

    # transitions at the end of the year (no leaving in the final year: censored)
    if year == Y1:
        break
    for p in active:
        w = p["gender"] == "Woman"
        p["years_in_stage"] += 1
        if p["roles"]:
            leave = 0.01
        elif p["stage"] == "Doctoral student":
            leave = 0.03
        elif p["stage"] == "Postdoc":
            leave = 0.17 if w else 0.13
        else:
            leave = 0.02 if p["permanent"] else (0.08 if w else 0.06)
        if p["stage"] == "Doctoral student" and p["years_in_stage"] >= p["student_years"]:
            # PhD obtained: leave the field or continue as postdoc
            p["phd_year"] = year + 1
            if rng.random() < (0.55 if w else 0.45):
                leave = 1.0
            else:
                p["stage"], p["years_in_stage"] = "Postdoc", 0
                p["permanent"] = rng.random() < 0.08
                leave = 0.0
        if rng.random() < leave:
            p["active"], p["cms_leave_year"] = False, year
            rows[-1 - (len(active) - 1 - active.index(p))]["left_cms_this_year"] = True
            p["roles"] = {}
            continue
        if p["stage"] == "Postdoc" and rng.random() < (0.07 if w else 0.10):
            p["stage"], p["years_in_stage"] = "Staff", 0
            p["permanent"] = rng.random() < 0.7
        elif p["stage"] == "Staff" and not p["permanent"] and rng.random() < 0.10:
            p["permanent"] = True

df = pd.DataFrame(rows)
leave = {p["person_id"]: p["cms_leave_year"] for p in people}
df.insert(df.columns.get_loc("phd_year"), "cms_leave_year", df["person_id"].map(leave).astype("Int64"))
df["phd_year"] = df["phd_year"].astype("Int64")
df["years_since_phd"] = df["years_since_phd"].astype("Int64")
df["stage_contract"] = np.where(df["stage"] == "Doctoral student", "Doctoral student",
                                df["stage"] + " (" + df["contract"].str.lower() + ")")
LEAD = pd.concat([df[df[HOLD[l]]].assign(leadership_level=l) for l in LEVELS], ignore_index=True)
csv_path = os.path.join(HERE, "dmoc_fake_person_year.csv")
df.to_csv(csv_path, index=False)
print(f"wrote {csv_path}: {len(df):,} rows, {df.person_id.nunique():,} people")

# ----------------------------------------------------------------------------
# Plot styling (reference palette, light mode)
# ----------------------------------------------------------------------------
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GCOL = {"Woman": CAT[0], "Man": CAT[1]}
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "lines.linewidth": 2,
    "lines.markersize": 7, "legend.frameon": False,
})
FIGS = []


def finish(fig, name, note):
    fig.text(0.99, 0.01, "FAKE DATA - illustration only", ha="right", va="bottom",
             fontsize=9, color="#e34948", weight="bold")
    fig.text(0.01, 0.01, note, ha="left", va="bottom", fontsize=8, color=INK2, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(os.path.join(PLOTS, name), dpi=160)
    FIGS.append(fig)


def binom_err(k, n):
    p = k / n
    return p, np.sqrt(p * (1 - p) / n)


STAGES = ["Doctoral student", "Postdoc (non-permanent)", "Postdoc (permanent)",
          "Staff (non-permanent)", "Staff (permanent)", "L3", "L2", "L1", "Spokesperson team"]


SHORT = {"Doctoral student": "PhD\nstudent", "Postdoc (non-permanent)": "Postdoc\nnon-perm.",
         "Postdoc (permanent)": "Postdoc\nperm.", "Staff (non-permanent)": "Staff\nnon-perm.",
         "Staff (permanent)": "Staff\nperm.", "Spokesperson team": "Spokes-\nperson\nteam"}
short = lambda labels: [SHORT.get(s, s) for s in labels]


def pipeline_table(d):
    """Stage membership; leadership levels counted on top of the career stage."""
    parts = [d.assign(pstage=d["stage_contract"])]
    for lvl in LEVELS:
        parts.append(d[d[HOLD[lvl]]].assign(pstage=lvl))
    return pd.concat(parts)


# ---------------------------------------------------------------- 1 leaky pipeline
# Two separate figures: career stages (PhD / postdoc / staff) and leadership levels (L3 ... SP team)
last = df[df.year >= Y1 - 4]                         # pool 5 years: SP team has only 3 seats
pipe = pipeline_table(last).drop_duplicates(["person_id", "pstage"])   # count people, not person-years
PIPES = [
    ("1c_pipeline_career_stage_pooled.png", "career stage", STAGES[:5],
     "Career stage from contract type (non-permanent / permanent)."),
    ("1d_pipeline_leadership_pooled.png", "leadership level", LEVELS,
     "Anyone holding the role in the window, whatever their career stage."),
]
for fname, what, stages, extra in PIPES:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.3), gridspec_kw={"width_ratios": [1, 1.2]})
    g = pipe.groupby("pstage").agg(n=("gender", "size"), k=("gender", lambda s: (s == "Woman").sum())).reindex(stages)
    p, e = binom_err(g.k, g.n)
    x = np.arange(len(stages))
    a1.errorbar(x, 100 * p, yerr=100 * e, color=GCOL["Woman"], marker="o", capsize=3)
    for xi, pi, ei, ki, ni in zip(x, p, e, g.k, g.n):
        a1.annotate(f"{ki}/{ni}", (xi, 100 * (pi + ei)), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=8, color=INK2)
    a1.set_xticks(x, short(stages), fontsize=9); a1.set_xlim(-0.5, len(stages) - 0.5)
    a1.set_ylabel("% women"); a1.set_ylim(0, 45)
    a1.set_title(f"Leaky pipeline - % women by {what}")

    reg = pd.crosstab(pipe.pstage, pipe.institute_region, normalize="index").reindex(stages)[REGION_NAMES] * 100
    bottom = np.zeros(len(stages))
    for i, r in enumerate(REGION_NAMES):
        a2.bar(x, reg[r], bottom=bottom, color=CAT[i], label=r, width=0.7, edgecolor=SURF, linewidth=1)
        bottom += reg[r].values
    a2.set_xticks(x, short(stages), fontsize=9)
    a2.set_ylabel("% of people"); a2.set_ylim(0, 100); a2.grid(axis="x", visible=False)
    a2.legend(loc="upper left", bbox_to_anchor=(1, 1), title="Institute region")
    a2.set_title(f"Region of home institute by {what}")
    finish(fig, fname,
           f"Distinct people active {Y1-4}-{Y1}. Error bars: binomial 1σ. Labels: women / total (absolute counts). " + extra)

# ---------------------------------------------------------------- 1a / 1b per-year monitoring
from matplotlib.colors import LinearSegmentedColormap, Normalize
ramp = LinearSegmentedColormap.from_list("blue", ["#b7d3f6", "#5598e7", "#1c5cab", "#0d366b"])
norm = Normalize(2010, Y1)


def per_year_pipeline(col, CAREER, fname, what, data=None):
    data = df if data is None else data
    yr = data[data.year >= 2010]
    t = yr.groupby(["year", col]).agg(n=("gender", "size"), k=("gender", lambda s: (s == "Woman").sum()))
    t["p"], t["e"] = binom_err(t.k, t.n)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1, 1]})
    x = np.arange(len(CAREER))
    for y in range(2010, Y1 + 1):
        ty = t.loc[y].reindex(CAREER).fillna(0)
        last_year = y == Y1
        a1.plot(x, 100 * ty.p, color=ramp(norm(y)), lw=2.6 if last_year else 1.4, marker="o",
                ms=7 if last_year else 4, zorder=3 if last_year else 2)
        if last_year:
            a1.errorbar(x, 100 * ty.p, yerr=100 * ty.e, fmt="none", ecolor=ramp(norm(y)), capsize=3, zorder=3)
            for xi, pi, ei, ki, ni in zip(x, ty.p, ty.e, ty.k, ty.n):
                a1.annotate(f"{ki}/{ni}", (xi, 100 * (pi + ei)), xytext=(0, 5), textcoords="offset points",
                            ha="center", fontsize=8, color=INK, weight="bold")
    sm = plt.cm.ScalarMappable(cmap=ramp, norm=norm)
    cb = fig.colorbar(sm, ax=a1, pad=0.02, ticks=[2010, 2014, 2018, 2022, Y1])
    cb.set_label("Year", color=INK2); cb.outline.set_visible(False)
    a1.set_xticks(x, short(CAREER), fontsize=9); a1.set_xlim(-0.3, len(CAREER) - 0.7)
    a1.set_ylabel("% women"); a1.set_ylim(0, 50)
    a1.set_title(f"% women by {what}, one line per year")

    ends = []
    for i, st in enumerate(CAREER):
        ts = t.xs(st, level=col)
        a2.fill_between(ts.index, 100 * (ts.p - ts.e), 100 * (ts.p + ts.e), color=CAT[i], alpha=0.15, lw=0)
        a2.plot(ts.index, 100 * ts.p, color=CAT[i], marker="o", ms=4, label=st)
        ends.append([100 * ts.p.iloc[-1], SHORT.get(st, st).replace("-\n", "").replace("\n", " ")])
    ends.sort()                                   # spread end labels at least 2.6 points apart
    for j in range(1, len(ends)):
        ends[j][0] = max(ends[j][0], ends[j - 1][0] + 2.6)
    for yv, lab in ends:
        a2.text(Y1 + 0.6, yv, lab, va="center", fontsize=8, color=INK)
    a2.set_xlabel("Year"); a2.set_ylabel("% women"); a2.set_ylim(0, 50)
    a2.set_xlim(2009.5, Y1 + 4); a2.set_xticks(range(2010, Y1 + 1, 4))
    a2.set_title(f"% women per {what} over time")
    finish(fig, fname,
           f"Snapshot per year: distinct people active in that year. Latest year ({Y1}) highlighted with binomial 1σ error bars "
           "and women / total; bands on the right = 1σ.")


per_year_pipeline("stage_contract", STAGES[:5], "1a_pipeline_career_stage_by_year.png", "career stage")
per_year_pipeline("leadership_level", LEVELS, "1b_pipeline_leadership_by_year.png", "leadership level", LEAD)


def per_year_region(col, stages, fname, what, data=None):
    """Share of each home-institute region per stage, year by year: one panel column per region."""
    data = df if data is None else data
    yr = data[data.year >= 2010]
    n = yr.groupby(["year", col]).size()
    k = yr.groupby(["year", col, "institute_region"]).size()
    fig, axes = plt.subplots(2, len(REGION_NAMES), figsize=(20, 8.6))
    x = np.arange(len(stages))
    for c, reg in enumerate(REGION_NAMES):
        top, bot = axes[0, c], axes[1, c]
        kk = k.xs(reg, level="institute_region").reindex(n.index, fill_value=0)
        p, e = binom_err(kk, n)
        ymax = 0
        for y in range(2010, Y1 + 1):
            py, ey = p.loc[y].reindex(stages), e.loc[y].reindex(stages)
            last_year = y == Y1
            top.plot(x, 100 * py, color=ramp(norm(y)), lw=2.4 if last_year else 1.2, marker="o",
                     ms=6 if last_year else 3, zorder=3 if last_year else 2)
            if last_year:
                top.errorbar(x, 100 * py, yerr=100 * ey, fmt="none", ecolor=ramp(norm(y)), capsize=3, zorder=3)
            ymax = max(ymax, np.nanmax(100 * (py + ey)))
        top.set_xticks(x, short(stages), fontsize=7.5)
        top.set_title(reg, fontsize=11)
        for i, st in enumerate(stages):
            ps, es = p.xs(st, level=col), e.xs(st, level=col)
            bot.fill_between(ps.index, 100 * (ps - es), 100 * (ps + es), color=CAT[i], alpha=0.15, lw=0)
            bot.plot(ps.index, 100 * ps, color=CAT[i], marker="o", ms=3, lw=1.6,
                     label=SHORT.get(st, st).replace("-\n", "").replace("\n", " "))
            ymax = max(ymax, np.nanmax(100 * (ps + es)))
        bot.set_xticks([2010, 2018, Y1]); bot.set_xlabel("Year")
        for ax in (top, bot):
            ax.set_ylim(0, min(100, ymax * 1.1))
    axes[0, 0].set_ylabel(f"% of people at {what}\n(one line per year)")
    axes[1, 0].set_ylabel(f"% of people at {what}\n(over time)")
    sm = plt.cm.ScalarMappable(cmap=ramp, norm=norm)
    cb = fig.colorbar(sm, ax=axes[0, :], pad=0.01, fraction=0.015, ticks=[2010, 2018, Y1])
    cb.set_label("Year", color=INK2); cb.outline.set_visible(False)
    axes[1, -1].legend(loc="upper left", bbox_to_anchor=(1.02, 1), title=what.capitalize(), fontsize=9)
    fig.suptitle(f"Region of home institute by {what}, year by year", x=0.01, ha="left",
                 fontsize=13, weight="bold")
    fig.text(0.99, 0.01, "FAKE DATA - illustration only", ha="right", va="bottom",
             fontsize=9, color="#e34948", weight="bold")
    fig.text(0.01, 0.01, f"% = people from the region ÷ all people at that {what} in the year. Each region has its own "
             f"y-scale. Top: latest year ({Y1}) with binomial 1σ error bars. Bottom: bands = 1σ.",
             ha="left", va="bottom", fontsize=8, color=INK2)
    fig.subplots_adjust(left=0.05, right=0.88, top=0.9, bottom=0.1, hspace=0.45, wspace=0.28)
    fig.savefig(os.path.join(PLOTS, fname), dpi=160)
    FIGS.append(fig)


per_year_region("stage_contract", STAGES[:5], "1e_region_career_stage_by_year.png", "career stage")
per_year_region("leadership_level", LEVELS, "1f_region_leadership_by_year.png", "leadership level", LEAD)

# ---------------------------------------------------------------- 2 glass ceiling index
FIRST_ROLE = LEAD.groupby(["person_id", "leadership_level"]).year.min().unstack()


def eligible_pool(d, lvl):
    """Approximate eligible pool from the CSV (to be replaced by DMOC's agreed definitions)."""
    first = FIRST_ROLE      # history from the full table, not just the slice `d`
    def had(level):  # year of first appointment at `level`, per row
        hist = first[level].dropna() if level in first else pd.Series(dtype=float)
        return d.person_id.map(hist)
    if lvl == "L3":                   # no formal criteria: every active member
        return d
    prev = {"L2": "L3", "L1": "L2", "Spokesperson team": "L1"}[lvl]
    m = had(prev) < d.year
    if lvl == "L2":
        m |= (d.stage == "Staff") & (d.years_since_phd >= 8)
    return d[m.fillna(False) | d[HOLD[lvl]]]


def gci(d, lvl):
    pool, role = eligible_pool(d, lvl), d[d[HOLD[lvl]]]
    n1, k1 = len(pool), (pool.gender == "Woman").sum()
    n2, k2 = len(role), (role.gender == "Woman").sum()
    if k1 == 0 or k2 == 0:
        return np.nan, np.nan, k2, n2
    r = (k1 / n1) / (k2 / n2)
    se_log = np.sqrt((1 - k1 / n1) / k1 + (1 - k2 / n2) / k2)
    return r, r * se_log, k2, n2


fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2))
years = list(range(Y0 + 2, Y1 + 1))
for i, lvl in enumerate(LEVELS[:3]):
    vals = np.array([gci(df[df.year == y], lvl)[:2] for y in years])
    a1.errorbar(years, vals[:, 0], yerr=vals[:, 1], color=CAT[i], marker="o", capsize=2, label=lvl)
a1.axhline(1, color=INK2, lw=1, ls="--")
a1.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
a1.set_yscale("log"); a1.set_ylim(0.25, 4)
a1.set_yticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"]); a1.minorticks_off()
a1.text(years[-1], 0.95, "parity (GCI = 1)", fontsize=8, color=INK2, va="top", ha="right")
a1.set_xlabel("Year"); a1.set_ylabel("GCI = % women in pool / % women in role")
a1.set_title("Glass Ceiling Index by year (gender)")
a1.legend(loc="upper left", ncols=3); a1.set_xlim(years[0] - 0.5, years[-1] + 0.5)

windows = [(2010, 2014), (2015, 2020), (2021, 2026)]
xl = np.arange(len(LEVELS))
for i, (w0, w1) in enumerate(windows):
    d = df[(df.year >= w0) & (df.year <= w1)]
    vals = np.array([gci(d, lvl) for lvl in LEVELS])
    a2.errorbar(xl + (i - 1) * 0.12, vals[:, 0], yerr=vals[:, 1], color=CAT[i], marker="o",
                capsize=3, label=f"{w0}-{w1}")
    for lvl_i, v in enumerate(vals):
        if np.isnan(v[0]):
            a2.annotate("no women\nin role", (lvl_i + (i - 1) * 0.12, 1.0), fontsize=7,
                        color=INK2, ha="center", xytext=(0, -26), textcoords="offset points")
a2.axhline(1, color=INK2, lw=1, ls="--")
a2.set_xticks(xl, LEVELS); a2.set_xlabel("Leadership level")
a2.set_ylabel("GCI"); a2.set_title("Glass Ceiling Index by leadership level")
a2.legend(title="Person-years pooled")
finish(fig, "2_glass_ceiling_index.png",
       "GCI > 1: women under-represented in the role vs the eligible pool. Error bars: 1σ (log-ratio).\n"
       "Pools: L3 = all members (no formal criteria). Placeholders: L2 = ex-L3 or staff PhD+8y; L1 = ex-L2; SP team = ex-L1.")

# ---------------------------------------------------------------- 3 nomination vs success rate
def nom_table(d, by):
    elig = eligible_pool(d, "L3")
    t = elig.groupby(by).agg(person_years=("person_id", "size"), nom=("nominations", "sum"),
                             app=("appointments", "sum"))
    t["nom_rate"], t["nom_err"] = t.nom / t.person_years, np.sqrt(t.nom) / t.person_years
    t["succ"], t["succ_err"] = binom_err(t.app, t.nom)
    return t


fig, axes = plt.subplots(2, 2, figsize=(13, 7.5), gridspec_kw={"height_ratios": [1, 2.4]})
for row, by in enumerate(["gender", "institute_region"]):
    t = nom_table(df, by).sort_values("nom_rate")
    y = np.arange(len(t))
    col = [GCOL.get(i, CAT[0]) for i in t.index] if by == "gender" else CAT[0]
    for ax, val, err, lab in [(axes[row, 0], "nom_rate", "nom_err", "Nominations per eligible person-year"),
                              (axes[row, 1], "succ", "succ_err", "Success rate (appointed / nominated)")]:
        scale = 100 if val == "succ" else 1
        ax.errorbar(t[val] * scale, y, xerr=t[err] * scale, fmt="none", ecolor=INK2, capsize=3, lw=1)
        ax.scatter(t[val] * scale, y, color=col, s=60, zorder=3, edgecolor=SURF, linewidth=1.5)
        ax.set_yticks(y, t.index); ax.set_xlabel(lab + (" (%)" if val == "succ" else ""))
        for yi, (_, r) in enumerate(t.iterrows()):
            txt = f"n={r.nom:.0f} nom." if val == "nom_rate" else f"{r.app:.0f}/{r.nom:.0f}"
            ax.annotate(txt, (r[val] * scale, yi), xytext=(0, 8), textcoords="offset points",
                        ha="center", fontsize=7, color=INK2)
        ax.grid(axis="y", visible=False)
        ax.margins(x=0.25, y=0.25 if by == "gender" else 0.08)
axes[0, 0].set_title("Nomination rate (all levels)"); axes[0, 1].set_title("Success rate once nominated")
finish(fig, "3_nomination_vs_success.png",
       f"All leadership nominations {Y0}-{Y1}, normalised to person-years of all members (L3 pool). "
       "Error bars: Poisson (nominations) / binomial (success), 1σ. Labels: absolute counts.")

# ---------------------------------------------------------------- 4 median time to first L3 / L2
# Two clocks: years since PhD (needs PhD year) and years since joining CMS (everyone)
CLOCKS = [("phd", "Years from PhD to first appointment"),
          ("join", "Years from joining CMS to first appointment")]
rows4 = []
info = df.drop_duplicates("person_id").set_index("person_id")
for lvl in ["L3", "L2"]:
    f = LEAD[LEAD.leadership_level == lvl].groupby("person_id").agg(first_year=("year", "min"))
    f = f.join(info[["gender", "institute_region", "cms_join_year"]])
    f["phd"] = df.groupby("person_id").phd_year.max().reindex(f.index)
    f = f[f.first_year > Y0]                          # first role observed inside the window
    f["dt_phd"] = (f.first_year - f.phd).astype(float)   # NaN when no PhD (yet)
    f["dt_join"] = (f.first_year - f.cms_join_year).astype(float)
    for clock, _ in CLOCKS:
        g = f.dropna(subset=[f"dt_{clock}"])
        for by in ["gender", "institute_region"]:
            for gname, gdf in g.groupby(by):
                v = gdf[f"dt_{clock}"]
                rows4.append(dict(level=lvl, clock=clock, group=gname, n=len(v), med=v.median(),
                                  q1=v.quantile(0.25), q3=v.quantile(0.75)))
t4 = pd.DataFrame(rows4)
fig, axes = plt.subplots(2, 2, figsize=(13, 10.5), sharey=True)
order = ["Woman", "Man"] + REGION_NAMES
xmax = t4.q3.max() + 6
for r_i, (clock, xlabel) in enumerate(CLOCKS):
    for c_i, (lvl, c) in enumerate(zip(["L3", "L2"], [CAT[0], CAT[2]])):
        ax = axes[r_i, c_i]
        t = t4[(t4.level == lvl) & (t4.clock == clock)].set_index("group").reindex(order)
        y = np.arange(len(order))[::-1]
        ax.hlines(y, t.q1, t.q3, color=c, lw=3, alpha=0.35)
        ax.scatter(t.med, y, color=c, s=60, zorder=3, edgecolor=SURF, linewidth=1.5)
        for yi, (_, r) in zip(y, t.iterrows()):
            ax.annotate(f"{r.med:.0f} y (n={r.n:.0f})", (r.q3, yi), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8, color=INK2)
        ax.axhline(len(REGION_NAMES) - 0.5, color=GRID, lw=1)
        ax.set_yticks(y, order); ax.set_xlabel(xlabel)
        since = "PhD" if clock == "phd" else "joining CMS"
        ax.set_title(f"First {lvl} role - years since {since}"); ax.grid(axis="y", visible=False)
        ax.set_xlim(min(-1, t4.q1.min() - 1), xmax)
        ax.axvline(0, color=INK2, lw=1, ls="--")
finish(fig, "4_time_to_first_role.png",
       "Dot = median, bar = interquartile range, n = people. Only first appointments inside the data window; never-appointed people are censored "
       "(a Kaplan-Meier\ncurve would include them). PhD clock: people without a PhD year are left out; negative = appointed before the PhD. "
       "Joining clock: everyone.")

# ---------------------------------------------------------------- 5 talk allocation
elig5 = df[df.stage != "Doctoral student"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1.3, 1]})
for gname in ["Woman", "Man"]:
    t = elig5[elig5.gender == gname].groupby("year").agg(talks=("talks", "sum"), n=("talks", "size"))
    a1.errorbar(t.index, t.talks / t.n, yerr=np.sqrt(t.talks) / t.n, color=GCOL[gname], marker="o",
                capsize=2, label=gname)
    a1.annotate(gname, (t.index[-1], (t.talks / t.n).iloc[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9)
a1.set_xlabel("Year"); a1.set_ylabel("Talks per eligible person per year")
a1.set_title("Talk allocation rate by gender"); a1.legend(); a1.set_xlim(Y0 - 0.5, Y1 + 2)
a1.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
t = elig5.groupby("institute_region").agg(talks=("talks", "sum"), n=("talks", "size"))
t["rate"] = t.talks / t.n
t = t.sort_values("rate")
y = np.arange(len(t))
a2.barh(y, t.rate, xerr=np.sqrt(t.talks) / t.n, color=CAT[0], height=0.6, capsize=3,
        error_kw=dict(ecolor=INK2, lw=1))
for yi, (_, r) in enumerate(t.iterrows()):
    a2.text(0.02, yi, f"{r.talks:,.0f} talks / {r.n:,.0f} p-y", va="center", fontsize=8, color="white")
a2.set_yticks(y, t.index); a2.set_xlabel("Talks per eligible person-year")
a2.set_title("Talk allocation rate by institute region"); a2.grid(axis="y", visible=False)
finish(fig, "5_talk_allocation.png",
       f"Eligible = Physicists (postdoc + staff). Region panel pools {Y0}-{Y1}. Error bars: Poisson 1σ.")

# ---------------------------------------------------------------- 6 retention / attrition
d6 = df[df.year < Y1]
stages6 = ["Doctoral student", "Postdoc (non-permanent)", "Postdoc (permanent)",
           "Staff (non-permanent)", "Staff (permanent)"]
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(19, 5.6), gridspec_kw={"width_ratios": [1.15, 1, 1]})
x = np.arange(len(stages6)); wbar = 0.38
for i, gname in enumerate(["Woman", "Man"]):
    t = d6[d6.gender == gname].groupby("stage_contract").agg(
        n=("left_cms_this_year", "size"), k=("left_cms_this_year", "sum")).reindex(stages6)
    p, e = binom_err(t.k, t.n)
    xs = x + (i - 0.5) * wbar
    a1.bar(xs, 100 * p, yerr=100 * e, width=wbar - 0.03, color=GCOL[gname], label=gname, capsize=3,
           error_kw=dict(ecolor=INK2, lw=1))
    for xi, pi, ei, ki, ni in zip(xs, p, e, t.k, t.n):
        a1.text(xi, 100 * (pi + ei) + 0.3, f"{ki}\n/{ni}", ha="center", va="bottom", fontsize=6.5, color=INK2)
a1.set_xticks(x, short(stages6), fontsize=8)
a1.set_ylabel("Annual attrition rate (%)"); a1.set_title("Where people leave: attrition by stage")
a1.legend(); a1.grid(axis="x", visible=False); a1.set_ylim(0, 21)

# general retention: everyone who joined CMS (any stage), share still a member k years after joining
info = df.drop_duplicates("person_id").set_index("person_id")
lastyr = df.groupby("person_id").year.max()
join = info.cms_join_year[info.cms_join_year > Y0]            # joined inside the data window
ks = np.arange(0, 13)


def retention(ids):
    out = []
    for k in ks:
        at_risk = ids[join[ids] + k <= Y1]                      # cohorts observable k years later
        n = len(at_risk)
        p = (lastyr[at_risk] >= join[at_risk] + k).mean() if n else np.nan
        out.append((p, np.sqrt(p * (1 - p) / n) if n else np.nan, n))
    return np.array(out)


for gname in ["Woman", "Man"]:
    r = retention(join.index[info.loc[join.index, "gender"] == gname])
    a2.fill_between(ks, 100 * (r[:, 0] - r[:, 1]), 100 * (r[:, 0] + r[:, 1]), color=GCOL[gname], alpha=0.15, lw=0)
    a2.plot(ks, 100 * r[:, 0], color=GCOL[gname], marker="o", ms=4, label=f"{gname} (n={int(r[0, 2])})")
a2.set_xlabel("Years after joining CMS"); a2.set_ylabel("% still in CMS")
a2.set_ylim(0, 105); a2.set_xlim(-0.3, ks[-1] + 0.3); a2.legend()
a2.set_title("General retention by gender")

for i, reg in enumerate(REGION_NAMES):
    r = retention(join.index[info.loc[join.index, "institute_region"] == reg])
    a3.plot(ks, 100 * r[:, 0], color=CAT[i], marker="o", ms=3, lw=1.6, label=reg)
a3.set_xlabel("Years after joining CMS"); a3.set_ylim(0, 105); a3.set_xlim(-0.3, ks[-1] + 0.3)
a3.legend(fontsize=8, title="Institute region", title_fontsize=8)
a3.set_title("General retention by region")
finish(fig, "6_retention_attrition.png",
       f"Left: left CMS during the year / active that year, {Y0}-{Y1-1}; leavers / person-years printed; doctoral students "
       "leaving mid-PhD or at PhD completion included.\nMiddle, right: everyone who joined CMS {0}-{1}, whatever the stage; "
       "only cohorts observable k years later. Bands / error bars: binomial 1σ.".format(Y0 + 1, Y1))

# ---------------------------------------------------------------- 6b retention per joining period (Kaplan-Meier)
PERIODS = [(2009, 2014), (2015, 2020), (2021, 2026)]
PCOL = [ramp(norm(2012)), ramp(norm(2018)), ramp(norm(2025))]   # light = older cohorts, dark = newer


def kaplan_meier(ids):
    """Share still in CMS k years after joining; each step uses everyone observable at that step."""
    S, out = 1.0, [(0, 1.0, 0.0, len(ids))]
    var = 0.0                                                    # Greenwood variance sum
    for k in range(1, 13):
        risk = ids[(join[ids] + k <= Y1) & (lastyr[ids] >= join[ids] + k - 1)]
        if len(risk) < 20:
            break
        left = (lastyr[risk] == join[risk] + k - 1).sum()
        S *= 1 - left / len(risk)
        if len(risk) > left:
            var += left / (len(risk) * (len(risk) - left))
        out.append((k, S, S * np.sqrt(var), len(risk)))
    return np.array(out)


fig, axes = plt.subplots(1, 3, figsize=(18, 5.6), sharey=True)
for ax, (title, sel) in zip(axes, [("Everyone", None), ("Women", "Woman"), ("Men", "Man")]):
    for (p0, p1), c in zip(PERIODS, PCOL):
        m = (join >= p0) & (join <= p1)
        if sel:
            m &= info.loc[join.index, "gender"] == sel
        ids = join.index[m]
        r = kaplan_meier(ids)
        ax.fill_between(r[:, 0], 100 * (r[:, 1] - r[:, 2]), 100 * (r[:, 1] + r[:, 2]), color=c, alpha=0.18, lw=0)
        ax.plot(r[:, 0], 100 * r[:, 1], color=c, marker="o", ms=4, label=f"Joined {p0}-{p1} (n={len(ids)})")
    ax.set_title(f"Retention by joining period - {title}")
    ax.set_xlabel("Years after joining CMS"); ax.set_xlim(-0.3, 12.3); ax.set_ylim(0, 105)
    ax.legend(fontsize=8.5, loc="lower left")
axes[0].set_ylabel("% still in CMS (Kaplan-Meier)")
finish(fig, "6b_retention_by_join_period.png",
       "Kaplan-Meier: product of the yearly chances of staying, each using everyone who can be observed at that step, so recent joiners still count "
       "for their first years.\nA newer period's curve stops where its cohorts cannot be followed further. Bands: 1σ (Greenwood). "
       "Darker = more recent joiners.")

with PdfPages(os.path.join(HERE, "dmoc_fake_plots.pdf")) as pdf:
    for f in FIGS:
        pdf.savefig(f)
print("plots written to", PLOTS)
