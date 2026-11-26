"""Norfolk County prosecutor data: analysis behind the visualizations.

Inputs : charges.parquet + norfolk-supplementary.parquet (row-aligned, same row order)
Output : norfolk_viz_data.json (one block per question), norfolk_tables.json (the tables behind each chart)

Run    : python norfolk_analysis.py data/master/norfolk/charges.parquet data/master/norfolk/norfolk-supplementary.parquet
         (needs pandas + pyarrow; takes about 1-2 minutes)

Team criteria applied
  * Unit = one row per case, classified by its most serious charge.
  * Window = cases filed 2017-2024 (team questions); 2015-2024 for the Norfolk "last decade" questions.
  * Motor-vehicle-only cases are excluded (lead offense Motor Vehicle or OUI/DUI).
  * Unknown race is kept as its own group.
"""
import json, sys
import numpy as np
import pandas as pd

if len(sys.argv) > 2:
    CHARGES, SUPP = sys.argv[1], sys.argv[2]
else:  # cached pickles made from the parquet files
    CHARGES, SUPP = 'charges.pkl', 'supp.pkl'

def load(p):
    return pd.read_pickle(p) if p.endswith('.pkl') else pd.read_parquet(p)

c = load(CHARGES)
s = load(SUPP)
assert (c.case_id.values == s.case_id.values).all()
c['case_type'] = s.case_type.values
c['agency'] = s.filing_agency_desc.values
c['crime_type'] = s.crime_type.values

# ---------------- charge-level flags ----------------
cc = c.charge_code_normalized.fillna('')
desc = c.charge_description.fillna('').str.upper()
CHILD = {'265/13B', '265/13B1', '265/13B12', '265/13B34', '265/13L', '265/22A', '265/22B', '265/22C', '265/23', '265/23A',
         '265/23B', '265/24B', '265/13J', '265/26A', '265/26C', '272/29A', '272/29B', '272/29C', '272/28', '272/105',
         '119/39', '119/63'}
c['f_dv'] = c.case_type.eq('DV')
c['f_sa'] = c.case_type.eq('SA')
c['f_child'] = cc.isin(CHILD) | (cc.eq('265/15A') & desc.str.contains('CHILD'))
c['f_elder'] = cc.isin({'265/13K', '265/13H', '19A/15', '19C/10'}) | (cc.eq('266/30') & desc.str.contains(r'\+60|DISABLED'))
c['f_hate'] = cc.isin({'265/37', '265/39', '12/11J'})

# ---------------- outcome buckets (charge level) ----------------
# Severity order: lower number = more severe (used to pick the case outcome).
def bucket(r):
    rc, sub, code = r.resolution_category, r.resolution_subtype, r.disposition_code
    if rc == 'Pending': return 'Pending'
    if rc == 'Convicted':
        if sub == 'CWOF (admitted facts)': return 'CWOF'
        if code in ('GLTY', 'BVER', 'JVER'): return 'Trial conviction'
        return 'Plea / guilty'
    if rc == 'Diverted': return 'Diversion'
    if rc == 'Acquitted': return 'Acquittal'
    if rc == 'Indictment routing': return 'Moved to Superior'
    if rc in ('Civil (NR)', 'Civil (responsible)'): return 'Civil'
    return 'Dismissal'  # office walk-away, DWOP, administrative, court-driven, charge bargaining
ORDER = ['Trial conviction', 'Plea / guilty', 'CWOF', 'Diversion', 'Acquittal', 'Dismissal', 'Moved to Superior', 'Civil', 'Pending']
RANK = {k: i for i, k in enumerate(ORDER)}
key = c[['resolution_category', 'resolution_subtype', 'disposition_code']].drop_duplicates()
key['bucket'] = [bucket(r) for r in key.itertuples()]
c = c.merge(key, on=['resolution_category', 'resolution_subtype', 'disposition_code'], how='left')
c['o_rank'] = c.bucket.map(RANK)

# Sentence categories (codes are undefined in the data dictionary -> mapping is our reading of the abbreviations)
SENT = {'COM': 'Incarceration', 'LIF': 'Incarceration', 'HOU': 'Incarceration', 'DYS': 'Incarceration', 'DYC': 'Incarceration',
        'SPS': 'Suspended / split', 'SSS': 'Suspended / split',
        'PRO': 'Probation', 'PRC': 'Probation',
        'FIN': 'Fine', 'GFIL': 'Filed / other', 'AGR': 'Filed / other', 'CON': 'Filed / other', 'POA': 'Filed / other',
        'TDS': 'Filed / other', 'OAA': 'Filed / other', 'CNS': 'Filed / other', 'PTP': 'Filed / other'}
S_ORDER = ['Incarceration', 'Suspended / split', 'Probation', 'Fine', 'Filed / other']
c['sent'] = c.impsd_sentence_type.map(SENT)
c['s_rank'] = c.sent.map({k: i for i, k in enumerate(S_ORDER)})

# Offense severity (most serious charge on the case)
SEV = ['Sexual Offenses', 'Robbery', 'Firearms/Weapons', 'Assault w/ Weapon', 'Domestic Violence', 'Drug Distribution',
       'Breaking & Entering', 'Assault & Battery', 'Drug Possession', 'Fraud/Forgery', 'Larceny/Theft', 'Property Damage',
       'Disorderly/Public Order', 'Other/Unknown', 'OUI/DUI', 'Motor Vehicle']
c['sev'] = c.offense_group.map({k: i for i, k in enumerate(SEV)})

# ---------------- case level ----------------
c = c.sort_values(['case_id', 'sev', 'o_rank'])
g = c.groupby('case_id', sort=False)
case = g.agg(defendant=('defendant_id', 'first'), offense=('offense_group', 'first'), court=('court_name', 'first'),
             court_cat=('court_category', 'first'), agency=('agency', 'first'), filed=('filing_date', 'min'),
             disposed=('disposition_date', 'max'), race=('defendant_race', 'first'), sex=('defendant_sex', 'first'),
             o_rank=('o_rank', 'min'), s_rank=('s_rank', 'min'), any_sent=('impsd_sentence_type', lambda x: x.notna().any()),
             dv=('f_dv', 'any'), sa=('f_sa', 'any'), child=('f_child', 'any'), elder=('f_elder', 'any'), hate=('f_hate', 'any'),
             anomaly=('date_anomaly_flags', lambda x: (x != '').any()))
# race/sex: first non-null value on the case
case['race'] = g.defendant_race.agg(lambda x: x.dropna().iloc[0] if x.notna().any() else 'Unknown / missing')
case['sex'] = g.defendant_sex.agg(lambda x: x.dropna().iloc[0] if x.notna().any() else 'Unknown / missing')
case['race'] = case.race.replace({'Unknown': 'Unknown / missing', 'American Indian/Native': 'Other', 'Asian': 'Asian'})
case['sex'] = case.sex.replace({'Unknown': 'Unknown / missing'})
case['outcome'] = case.o_rank.map(dict(enumerate(ORDER)))
case['sentence'] = case.s_rank.map(dict(enumerate(S_ORDER)))
case['year'] = case.filed.dt.year

# prior record: number of the defendant's cases filed in the 5 years before this case (data starts 2005)
# (counts all of the defendant's earlier cases, including motor-vehicle cases, so it is computed before the MV filter below)
def prior_counts(d):
    t = d.values.astype('datetime64[D]').astype(np.int64)
    return np.searchsorted(t, t, 'left') - np.searchsorted(t, t - 5 * 365, 'left')
case = case.sort_values(['defendant', 'filed'])
case['prior'] = case.groupby('defendant', sort=False).filed.transform(prior_counts)
case = case[~case.offense.isin(['Motor Vehicle', 'OUI/DUI'])].copy()   # drop motor-vehicle-only cases

T = case[(case.year >= 2017) & (case.year <= 2024)]
D = case[(case.year >= 2015) & (case.year <= 2024)]
resolved = lambda x: x[~x.outcome.isin(['Pending'])]
out = {}

# Q1 volume and trend
q1 = case[(case.year >= 2005) & (case.year <= 2024)].groupby('year').size()
out['q1'] = {'years': q1.index.tolist(), 'cases': q1.tolist(),
             'yoy': (q1.pct_change() * 100).round(1).fillna(0).tolist(),
             'vs2017': ((q1 / q1.loc[2017] - 1) * 100).round(1).tolist()}

# Q2 per capita (Census PEP July-1 resident population, thousands; FRED series MANORF1POP)
POP = {2005: 651.219, 2006: 652.964, 2007: 656.466, 2008: 661.872, 2009: 666.665, 2010: 673.059, 2011: 677.823, 2012: 682.984,
       2013: 688.518, 2014: 692.439, 2015: 694.774, 2016: 697.452, 2017: 701.046, 2018: 703.628, 2019: 707.164, 2020: 723.647,
       2021: 724.970, 2022: 727.727, 2023: 730.453, 2024: 737.601}
out['q2'] = {'years': q1.index.tolist(), 'per10k': [round(q1[y] / (POP[y] * 1000) * 10000, 1) for y in q1.index],
             'pop': [POP[y] for y in q1.index]}

# Q3 outcomes (disposed cases), overall and by year
R = resolved(T)
Q3B = ['Dismissal', 'Plea / guilty', 'CWOF', 'Diversion', 'Trial conviction', 'Acquittal', 'Moved to Superior', 'Civil']
ov = R.outcome.value_counts(normalize=True).reindex(Q3B).fillna(0) * 100
by = pd.crosstab(R.year, R.outcome, normalize='index').reindex(columns=Q3B).fillna(0) * 100
pend = T.groupby('year').outcome.apply(lambda x: (x == 'Pending').mean() * 100)
out['q3'] = {'buckets': Q3B, 'overall': ov.round(1).tolist(), 'n': int(len(R)), 'years': by.index.tolist(),
             'by_year': {b: by[b].round(1).tolist() for b in Q3B}, 'pending_pct': pend.round(1).tolist()}

# Q4 sentencing among convicted cases (plea/guilty or trial conviction; CWOF reported separately in Q3)
CV = T[T.outcome.isin(['Plea / guilty', 'Trial conviction'])]
sv = CV.sentence.fillna('Missing').value_counts().reindex(S_ORDER + ['Missing']).fillna(0)
out['q4'] = {'cats': S_ORDER + ['Missing'], 'pct': (sv / sv.sum() * 100).round(1).tolist(), 'n': int(len(CV)),
             'missing_pct': round(sv['Missing'] / sv.sum() * 100, 1)}
known = CV[CV.sentence.notna()]
bo = pd.crosstab(known.offense, known.sentence, normalize='index').reindex(columns=S_ORDER).fillna(0) * 100
bo = bo.loc[known.offense.value_counts().index[:10]].sort_values('Incarceration')
out['q4']['by_offense'] = {'offenses': bo.index.tolist(), **{k: bo[k].round(1).tolist() for k in S_ORDER}}

# Q6 time to disposition (closed cases, no negative/anomalous intervals)
Cl = T[T.outcome.ne('Pending') & T.disposed.notna()].copy()
Cl['days'] = (Cl.disposed - Cl.filed).dt.days
Cl = Cl[(Cl.days >= 0) & ~Cl.anomaly]
def iqr(x, by):
    q = x.groupby(by).days.describe(percentiles=[.25, .5, .75])
    q = q[q['count'] >= 30].sort_values('50%')
    return {'labels': q.index.tolist(), 'q1': q['25%'].tolist(), 'med': q['50%'].tolist(), 'q3': q['75%'].tolist(), 'n': q['count'].astype(int).tolist()}
out['q6'] = {'overall_median': float(Cl.days.median()), 'by_offense': iqr(Cl, 'offense'),
             'by_court': iqr(Cl[Cl.court.notna()], 'court'), 'n': int(len(Cl))}

# Q7 disparities by race and sex (dismissal among disposed cases; incarceration among convicted with a known sentence)
RACES = ['White', 'Black', 'Hispanic', 'Asian', 'Other', 'Unknown / missing']
SEXES = ['Male', 'Female', 'Unknown / missing']
def rates(col, groups, ref):
    res = {}
    dis = R.groupby(col).outcome.apply(lambda x: (x == 'Dismissal').mean() * 100).reindex(groups)
    inc = known.groupby(col).sentence.apply(lambda x: (x == 'Incarceration').mean() * 100).reindex(groups)
    nd = R[col].value_counts().reindex(groups).fillna(0).astype(int); ni = known[col].value_counts().reindex(groups).fillna(0).astype(int)
    res = {'groups': groups, 'dismissal': dis.round(1).tolist(), 'incarceration': inc.round(1).tolist(),
           'dis_ratio': (dis / dis[ref]).round(2).tolist(), 'inc_ratio': (inc / inc[ref]).round(2).tolist(),
           'n_dis': nd.tolist(), 'n_inc': ni.tolist()}
    return res
out['q7'] = {'race': rates('race', RACES, 'White'), 'sex': rates('sex', SEXES, 'Male'),
             'race_missing_pct': round((T.race == 'Unknown / missing').mean() * 100, 1)}

# Q8 disparities with controls: incarceration among convicted, within offense x prior-record cells (cells < 30 suppressed)
known = known.assign(prior_grp=np.where(known.prior > 0, '1+ prior cases', 'No prior cases'))
rows = []
for off in known.offense.value_counts().index[:8]:
    for pg in ['No prior cases', '1+ prior cases']:
        cell = known[(known.offense == off) & (known.prior_grp == pg)]
        r = {}
        for race in ['White', 'Black', 'Hispanic']:
            x = cell[cell.race == race]
            r[race] = round((x.sentence == 'Incarceration').mean() * 100, 1) if len(x) >= 30 else None
            r['n_' + race] = int(len(x))
        rows.append({'offense': off, 'prior': pg, **r})
out['q8'] = {'rows': rows}

# N1 dispositions for DV / sexual assault / child abuse over the decade (2015-2024)
RD = resolved(D)
N1B = ['Dismissal', 'Plea / guilty', 'CWOF', 'Diversion', 'Trial conviction', 'Acquittal', 'Moved to Superior']
n1 = {}
for k, lab in [('dv', 'Domestic violence'), ('sa', 'Sexual assault'), ('child', 'Child abuse')]:
    x = RD[RD[k]]
    t = pd.crosstab(x.year, x.outcome, normalize='index').reindex(columns=N1B).fillna(0) * 100
    n1[lab] = {'years': t.index.tolist(), **{b: t[b].round(1).tolist() for b in N1B}, 'n': x.groupby('year').size().tolist()}
out['n1'] = {'buckets': N1B, 'groups': n1}

# N2 outcomes across district courts
DC = ['Quincy District Court', 'Dedham District Court', 'Wrentham District Court', 'Stoughton District Court', 'Brookline District Court']
x = R[R.court.isin(DC)]
t = pd.crosstab(x.court, x.outcome, normalize='index').reindex(index=DC, columns=Q3B[:6]).fillna(0) * 100
out['n2'] = {'courts': [d.replace(' District Court', '') for d in DC], 'buckets': Q3B[:6], **{b: t[b].round(1).tolist() for b in Q3B[:6]},
             'n': x.court.value_counts().reindex(DC).tolist(), 'court_missing_pct': round(T.court.isna().mean() * 100, 1)}

# N3 crime type by municipality (filing police department), % of each town's cases
OFF = [o for o in SEV if o not in ('Motor Vehicle', 'OUI/DUI')]
top = T.agency.value_counts().index[:15]
x = T[T.agency.isin(top)]
t = pd.crosstab(x.agency, x.offense, normalize='index').reindex(index=top, columns=OFF).fillna(0) * 100
county = T.offense.value_counts(normalize=True).reindex(OFF).fillna(0) * 100
out['n3'] = {'agencies': [a.replace(' Police Department', '').replace('Massachusetts State Police', 'State Police') for a in top] + ['Norfolk County (all)'],
             'offenses': OFF, 'pct': t.round(1).values.tolist() + [county.round(1).tolist()],
             'n': T.agency.value_counts().reindex(top).tolist() + [int(len(T))]}

# N5 charging trends (cases filed per year) for DV, SA, child abuse, elder abuse, hate crimes, 2015-2024
n5 = {lab: D.groupby('year')[k].sum().astype(int).tolist() for k, lab in
      [('dv', 'Domestic violence'), ('sa', 'Sexual assault'), ('child', 'Child abuse'), ('elder', 'Elder abuse'), ('hate', 'Hate crimes')]}
out['n5'] = {'years': sorted(D.year.unique().tolist()), 'series': n5}

# N6 nolle prosequi by crime type, District vs Superior Court, 2015-2024 (charge level; SIND = indictment routing excluded)
ch = c[(c.filing_date.dt.year.between(2015, 2024)) & ~c.offense_group.isin(['Motor Vehicle', 'OUI/DUI'])]
nop = ch[(ch.disposition_code == 'NOPR') & (ch.disposition_reason != 'SIND')]
res = {}
for cat in ['District Court', 'Superior Court']:
    a = nop[nop.court_category == cat].offense_group.value_counts()
    tot = ch[(ch.court_category == cat) & ch.disposition_code.notna()].offense_group.value_counts()
    res[cat] = {'share': (a / a.sum() * 100).round(1).reindex(OFF).fillna(0).tolist(),
                'rate': (a / tot * 100).round(1).reindex(OFF).fillna(0).tolist(), 'n': int(a.sum())}
out['n6'] = {'offenses': OFF, **res, 'sind_excluded': int(((ch.disposition_code == 'NOPR') & (ch.disposition_reason == 'SIND')).sum())}

out['meta'] = {'cases_2017_2024': int(len(T)), 'cases_2015_2024': int(len(D)), 'resolved_2017_2024': int(len(R))}
json.dump(out, open('norfolk_viz_data.json', 'w'), default=lambda o: o.item() if hasattr(o, 'item') else None)
print(json.dumps(out['meta']), '\nQ3 overall', dict(zip(Q3B, out['q3']['overall'])))
print('Q4', dict(zip(out['q4']['cats'], out['q4']['pct'])))
print('Q6 median', out['q6']['overall_median'])
print('Q7 race', out['q7']['race']); print('Q7 sex', out['q7']['sex'])
print('N5', out['n5'])

# ---------------- tidy tables for the dashboard (one JSON file, one table per question) ----------------
def nz(v, n):  # suppress rates built on fewer than 30 cases
    return None if (v is None or n < 30 or (isinstance(v, float) and np.isnan(v))) else v
tables = {}
tables['volume'] = [{'year': y, 'cases': out['q1']['cases'][i], 'pct_change_yoy': out['q1']['yoy'][i] if i else None,
                     'pct_vs_2017': out['q1']['vs2017'][i], 'population_thousands': out['q2']['pop'][i], 'per_10k': out['q2']['per10k'][i]}
                    for i, y in enumerate(out['q1']['years'])]
KEYS = {'Dismissal': 'dismissal', 'Plea / guilty': 'plea_guilty', 'CWOF': 'cwof', 'Diversion': 'diversion', 'Trial conviction': 'trial_conviction',
        'Acquittal': 'acquittal', 'Moved to Superior': 'moved_to_superior', 'Civil': 'civil'}
rows = [{'period': '2017–2024', **{KEYS[b]: out['q3']['overall'][i] for i, b in enumerate(Q3B)}, 'pending_pct': round((T.outcome == 'Pending').mean() * 100, 1), 'cases': int(len(R))}]
for i, y in enumerate(out['q3']['years']):
    rows.append({'period': str(y), **{KEYS[b]: out['q3']['by_year'][b][i] for b in Q3B}, 'pending_pct': out['q3']['pending_pct'][i],
                 'cases': int((R.year == y).sum())})
tables['outcomes'] = rows
tables['sentences'] = [{'sentence': k, 'pct': out['q4']['pct'][i], 'cases': int(round(out['q4']['pct'][i] * out['q4']['n'] / 100))} for i, k in enumerate(out['q4']['cats'])]
bo_ = out['q4']['by_offense']
SK = {'Incarceration': 'incarceration', 'Suspended / split': 'suspended_split', 'Probation': 'probation', 'Fine': 'fine', 'Filed / other': 'filed_other'}
tables['sentence_by_offense'] = [{'offense': o, **{SK[k]: bo_[k][i] for k in S_ORDER}, 'cases': int((known.offense == o).sum())} for i, o in enumerate(bo_['offenses'])]
tables['time'] = []
for kind, blk in [('Offense', out['q6']['by_offense']), ('Court', out['q6']['by_court'])]:
    for i, l in enumerate(blk['labels']):
        tables['time'].append({'kind': kind, 'group': l.replace(' District Court', ' District').replace('Norfolk Superior Court', 'Superior Court'),
                               'p25_days': blk['q1'][i], 'median_days': blk['med'][i], 'p75_days': blk['q3'][i], 'cases': blk['n'][i]})
tables['time'].append({'kind': 'All', 'group': 'All cases', 'p25_days': float(Cl.days.quantile(.25)), 'median_days': out['q6']['overall_median'],
                       'p75_days': float(Cl.days.quantile(.75)), 'cases': out['q6']['n']})
tables['disparity'] = []
for dim, blk in [('Race', out['q7']['race']), ('Sex', out['q7']['sex'])]:
    for i, gname in enumerate(blk['groups']):
        tables['disparity'].append({'dimension': dim, 'group': gname,
            'dismissal_pct': nz(blk['dismissal'][i], blk['n_dis'][i]), 'dismissal_ratio': nz(blk['dis_ratio'][i], blk['n_dis'][i]),
            'incarceration_pct': nz(blk['incarceration'][i], blk['n_inc'][i]), 'incarceration_ratio': nz(blk['inc_ratio'][i], blk['n_inc'][i]),
            'disposed_cases': blk['n_dis'][i], 'convicted_cases': blk['n_inc'][i]})
tables['controls'] = [{'offense': r['offense'], 'prior_record': r['prior'], 'white_pct': r['White'], 'black_pct': r['Black'], 'hispanic_pct': r['Hispanic'],
                       'white_n': r['n_White'], 'black_n': r['n_Black'], 'hispanic_n': r['n_Hispanic']} for r in out['q8']['rows']]
tables['special_outcomes'] = []
for lab, blk in out['n1']['groups'].items():
    for i, y in enumerate(blk['years']):
        tables['special_outcomes'].append({'crime': lab, 'year': y, **{KEYS[b]: blk[b][i] for b in N1B}, 'cases': blk['n'][i]})
tables['courts'] = [{'court': ct, **{KEYS[b]: out['n2'][b][i] for b in Q3B[:6]}, 'cases': out['n2']['n'][i]} for i, ct in enumerate(out['n2']['courts'])]
tables['towns'] = [{'town': a, 'offense': o, 'pct': out['n3']['pct'][i][j], 'town_cases': out['n3']['n'][i]}
                   for i, a in enumerate(out['n3']['agencies']) for j, o in enumerate(out['n3']['offenses'])]
TK = {'Domestic violence': 'domestic_violence', 'Sexual assault': 'sexual_assault', 'Child abuse': 'child_abuse', 'Elder abuse': 'elder_abuse', 'Hate crimes': 'hate_crimes'}
tables['charging_trends'] = [{'year': y, **{TK[k]: v[i] for k, v in out['n5']['series'].items()}} for i, y in enumerate(out['n5']['years'])]
tables['nolle'] = [{'offense': o, 'district_share_pct': out['n6']['District Court']['share'][i], 'district_rate_pct': out['n6']['District Court']['rate'][i],
                    'superior_share_pct': out['n6']['Superior Court']['share'][i], 'superior_rate_pct': out['n6']['Superior Court']['rate'][i]}
                   for i, o in enumerate(OFF)]
json.dump(tables, open('norfolk_tables.json', 'w'), default=lambda o: o.item() if hasattr(o, 'item') else None, ensure_ascii=False)
print({k: len(v) for k, v in tables.items()})
