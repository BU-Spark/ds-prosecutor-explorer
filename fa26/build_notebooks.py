"""Build readable county notebooks following the supplied shared template."""
from pathlib import Path
import json
import re
import shutil
import textwrap

ROOT=Path(__file__).resolve().parent

def cell(kind,source):
    c={'cell_type':kind,'metadata':{},'source':textwrap.dedent(source).strip()+'\n'}
    if kind=='code':c.update(execution_count=None,outputs=[])
    return c

def build(slug,name,preserve_outputs=False):
    folder=ROOT/slug;folder.mkdir(exist_ok=True)
    cells=[]
    def md(s):cells.append(cell('markdown',s))
    def code(s):cells.append(cell('code',s))
    md(f'''# {name} Prosecution Analysis

    **Study period:** 2017–2024 case cohorts. **Review date:** November 23, 2026.

    Adapted from the team's `parin-dev` county analysis template and shared chart palette.
    One case unit is an observed docket number × defendant ID; unresolved identities are excluded and counted.
    Open cases are included in volume, excluded from outcome analysis. The most severe observed charge outcome wins:
    Trial Conviction > Plea > CWOF > Diversion > Acquittal > Dismissal > Other > Unknown.

    **Read the coverage section first.** Fields above 20% missing are insufficient under the shared rule;
    dependent metrics are withheld. Explicit Unknown and blank Missing remain separate. Disparity groups below 30
    are suppressed. This notebook reports recorded evidence, not causal effects, actual time served, or statewide history.

    **County-specific date limitation:** {'Initiated Dt is an initiation date; its equivalence to court filing needs client confirmation.' if slug=='berkshire' else 'There is no filing date. Case-ID prefix years are unverified cohort proxies; their charts are supplementary, not confirmed filing trends.'}
    ''')
    md('## Setup\nRun all cells in order. Set the `PROSECUTOR_DATA_ROOT` environment variable if the original spreadsheets are elsewhere. Raw files are read only.')
    code(f'''
    from pathlib import Path
    import os, sys, json
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display, Markdown

    ROOT = next((p for base in (Path.cwd(), *Path.cwd().parents)
                 for p in (base, base / 'county_notebooks_for_github_updated')
                 if (p / 'county_adapter.py').is_file()), None)
    if ROOT is None:
        raise FileNotFoundError('Open this notebook from its county folder or the review package root.')
    sys.path.insert(0, str(ROOT))
    from viz_style import set_style, OUTCOME_COLORS, BAIL_COLORS, stacked_pct_bar
    from county_charts import bail_table, MIN_CELL
    import county_adapter as adapter
    import county_review_charts as charts
    set_style()

    SLUG={slug!r}; COUNTY={name!r}; BERK=SLUG=='berkshire'
    COUNTY_DIR=ROOT/SLUG
    FIG_DIR=COUNTY_DIR/'figures'; TABLE_DIR=COUNTY_DIR/'tables'
    FIG_DIR.mkdir(exist_ok=True); TABLE_DIR.mkdir(exist_ok=True)
    DATA_ROOT=Path(os.environ.get('PROSECUTOR_DATA_ROOT', str(ROOT.parent)))
    YEARS=range(2017,2025)
    YEAR_LABEL='Recorded initiation year (filing proxy)' if BERK else 'Unverified case-ID prefix year'
    tables={{}}; statuses=[]
    def save_table(name,frame):
        tables[name]=frame
        frame.to_csv(TABLE_DIR/(name+'.csv'),index=True)
        display(frame)
        return frame
    def status(question,state,reason):
        statuses.append(dict(question=question,status=state,reason=reason))
        display(Markdown('**'+state+'.** '+reason))
    def fig(name):return FIG_DIR/(SLUG+'_'+name+'.png')
    ''')
    md('## Load Data and Map Dispositions\nBoth Berkshire continuation sheets are read, including the first data row on List_Frame_2. Cape duplicate headers are disambiguated before selecting fields. Identical export copies and shifted/unattached Cape rows are flagged before aggregation.')
    code('''
    raw=adapter.load_sources(SLUG, DATA_ROOT)
    filed,disposed,bail,inventory,source_hashes,exclusions,crosswalk=adapter.prepare(SLUG,raw)
    save_table('source_inventory',inventory)
    save_table('source_exclusions',exclusions)
    save_table('source_sha256',pd.Series(source_hashes,name='sha256').to_frame())
    save_table('disposition_crosswalk',crosswalk)
    ''')
    md('''**Mapping decisions.** Nolle prosequi is included in Dismissal for the shared comparison. CWOF remains separate.
    Berkshire uses disposition type, description and sentence translation together: a generic guilty record is Other if its plea/trial route is unknown.
    A plea route alone does not establish conviction or incarceration. Conflicting CWOF/custody evidence is Other pending review.
    Cape GPL is Plea, GJT/GBT/GJW are Trial Conviction, CWF is CWOF, and NOP/NPDPH/DIS/OBJ are Dismissal.
    Pretrial probation is not automatically treated as verified diversion. See the complete exported crosswalk rather than inferring meanings from colors.''')
    md('''## 0. Data Coverage
    Coverage is calculated on retained criminal charge rows in the target cohort **before excluding missing case identities**.
    The template's 20% threshold is then checked again on the case denominator used by each metric.
    A missing substantive offense-category crosswalk does not prevent a clearly labeled supplementary comparison by source offense class.
    A field can pass the completeness threshold while still needing semantic validation.''')
    code('''
    coverage=adapter.coverage_table(filed,disposed)
    save_table('coverage_charge_fields',coverage)
    INSUFFICIENT=set(coverage.loc[(coverage.extract=='disposed') & coverage.status.eq('insufficient data'),'field'])
    print('Insufficient disposed-extract fields:', ', '.join(sorted(INSUFFICIENT)) or 'none')
    ''')
    md('''## Build Case Table
    The primary key is docket × defendant, not source row or internal case ID. Berkshire selects the docket associated with the recorded district/superior court, or the sole available docket. Ambiguous dual-docket rows remain unresolved; court-stage histories cannot be reconstructed.
    Case dates use earliest recorded initiation and latest observed disposition. Class ranks F > M+ > M−; the charge ordinal breaks ties when available, then charge code and source row. Cape has no charge ordinal, so the tie-break is deterministic rather than a verified lead charge.
    A case with any charge recorded as open or unconfirmed is Pending and excluded from outcomes. Closed cases with missing outcomes retain Unknown.
    Cohorts use earliest initiation year in Berkshire; Cape's supplementary cohorts use the unverified ID-prefix year. These differ from the older notebooks' disposition-year cohorts.''')
    code('''
    filed_cases,all_cases,cases=adapter.build_cases(filed,disposed)
    metric_coverage=adapter.metric_coverage(cases)
    save_table('coverage_case_metrics',metric_coverage)
    cohort=pd.DataFrame([dict(filed_case_units=len(filed_cases),observed_case_units=len(all_cases),
        pending_or_unconfirmed_excluded=int(all_cases.outcome.eq('Pending').sum()),disposed_case_units=len(cases))])
    save_table('cohort_flow',cohort)
    identity=pd.DataFrame([dict(extract=label,unresolved_docket_or_defendant_rows=int(df.case_key.isna().sum()),
        source_case_ids=df.case_id.nunique(),resolved_docket_defendant_units=df.case_key.nunique())
        for label,df in [('filed',filed),('disposed',disposed)]])
    save_table('case_identity_audit',identity)
    def allowed(field):
        raw_field='sentence_type' if field=='sentence' else field
        return raw_field not in INSUFFICIENT and metric_coverage.at[field,'status']=='ok'
    filed_identity_ok=not coverage.loc[(coverage.extract=='filed') & coverage.field.isin(['docket','defendant_id']),'status'].eq('insufficient data').any()
    disposed_identity_ok=not coverage.loc[(coverage.extract=='disposed') & coverage.field.isin(['docket','defendant_id']),'status'].eq('insufficient data').any()
    ''')
    md('''## 1. Volume and Trend
    **Question:** How many cases were filed each year, and how has that changed since 2017?
    **Metric:** criminal case units per year, percentage change year over year and versus 2017.
    **Method:** use the filed extract, including open cases, and count each resolved docket/defendant unit once. Cape cannot provide a confirmed filing-year count.''')
    code('''
    vol=filed_cases.groupby('year').size().reindex(YEARS,fill_value=0)
    vol.index=vol.index.astype(int)
    if filed_identity_ok:
        status('Q1','Partially answerable', 'Recorded initiation is a filing proxy.' if BERK else 'No filing date; the following is an unverified case-ID-year proxy, not confirmed filings.')
        save_table('q1_volume',charts.volume(vol,COUNTY,YEAR_LABEL,fig('q1_volume')))
        print(f'2017: {vol.loc[2017]:,}; 2024: {vol.loc[2024]:,}; change: {(vol.loc[2024]/vol.loc[2017]-1):.1%}')
    else:
        status('Q1','Unavailable under shared rule','Docket/defendant coverage fails the 20% missing-data threshold.')
        charts.unavailable(COUNTY+': Q1',statuses[-1]['reason'],fig('q1_volume'))
    ''')
    md('''## 2. Per-Capita Rate
    **Question:** How many cases are filed per 10,000 residents?
    **Method:** Q1 recorded case units / annual July 1 Census PEP population × 10,000.
    The existing population estimates are reused; no new population values are retrieved. Vintages change at 2020. Cape combines Barnstable, Dukes and Nantucket. This is a caseload-to-population proxy, not a resident victimization rate.''')
    code('''
    population=pd.read_csv(ROOT/'annual_population.csv').set_index('year')
    pop=population['berkshire' if BERK else 'cape_and_islands']
    assert pop.reindex(YEARS).gt(0).all()
    if filed_identity_ok:
        status('Q2','Partially answerable','The numerator inherits Q1’s initiation/ID-year limitation; population is annual and sourced.')
        save_table('q2_per_capita',charts.per_capita(vol,pop,COUNTY,YEAR_LABEL,fig('q2_per_capita')))
    else:
        status('Q2','Unavailable under shared rule','Q1 does not meet the case-identity coverage rule.')
        charts.unavailable(COUNTY+': Q2',statuses[-1]['reason'],fig('q2_per_capita'))
    ''')
    md('''## 3. Case Outcomes
    **Question:** Of charged cases, what share end in dismissal, diversion, plea, trial conviction, or acquittal?
    **Denominator:** observed disposed criminal docket/defendant units in the 2017–2024 cohort, not all filed cases.
    The shared severity hierarchy applies across all observed charges. Open cases are excluded. Recent cohorts disproportionately contain fast-resolving cases; this is not an eventual-outcome forecast. Cape cohorts remain proxies. Unknown is kept visible.''')
    code('''
    outcome_ok=disposed_identity_ok and 'disposition' not in INSUFFICIENT
    if outcome_ok:
        status('Q3','Partially answerable','Observed disposed-case shares are available. Filing semantics, unresolved cases and unverified diversion limit a complete answer.')
        counts,pct=charts.outcomes(cases,COUNTY,YEAR_LABEL,fig('q3_outcomes_by_year'))
        save_table('q3_outcome_counts',counts);save_table('q3_outcome_pct',pct)
        print('Overall denominator:',f'{len(cases):,}', 'case units')
    else:
        status('Q3','Unavailable under shared rule','Disposition or case-identity missingness exceeds 20%.')
        charts.unavailable(COUNTY+': Q3',statuses[-1]['reason'],fig('q3_outcomes_by_year'))
    ''')
    md('''## 4. Sentencing
    **Question:** What share of convictions result in incarceration, probation, or fines/other?
    **Method:** among case units with conviction evidence, select the most severe recorded sentence. CWOF is excluded.
    Berkshire uses translated sentence text and positive actual-jail amounts; a generic plea requires additional evidence.
    Cape uses imposed sentence codes; SS is suspended and F is filed, neither is automatically incarceration or probation.
    Blank evidence is Unknown, not zero. Missing-sentence share accompanies every released rate. If source or case-level missingness exceeds 20%, the rates are withheld.''')
    code('''
    sentence_ok=outcome_ok and allowed('sentence')
    convictions=cases[cases.conviction_evidence]
    print(f'Conviction-evidence case units: {len(convictions):,}; case-level unknown sentence: {convictions.sentence.eq("Unknown").mean():.1%}')
    if sentence_ok:
        status('Q4','Partially answerable','Recorded sentence types are available; markers do not establish time served, and pleas without conviction evidence are excluded.')
        save_table('q4_sentencing',charts.sentencing(cases,COUNTY,fig('q4_sentencing')))
    else:
        status('Q4','Unavailable under shared rule','Sentence evidence exceeds 20% missing or fails an outcome/identity prerequisite. No incarceration/probation rate is released.')
        charts.unavailable(COUNTY+': sentencing',statuses[-1]['reason'],fig('q4_sentencing'))
    ''')
    md('''## 5. Pretrial Detention and Bail
    **Question:** What share of defendants are held pretrial, and how often is cash bail set?
    **Method:** discard bail dates outside 2017–2024 before selecting the first recorded date. Retain conflicting same-day statuses as Unknown. Link only source case IDs that resolve to exactly one filed docket/defendant unit.
    This is a first recorded event, **not a verified arraignment**. Berkshire Cash/Surety does not establish cash-only bail; Cape BAIL does not specify mode. These remain Unknown in the shared cash-only metric. A recorded amount is not money collected. Posting, inability to post and detention duration are unavailable.''')
    if slug=='cape_and_islands':
        cells[-1]['source'] += '\n**Cape source-label guide:** PR = Personal Recog; PRBW = Person Recog – Bail Warning; BAIL = Bail (mode unspecified); IC = In Custody; ICBR = In Custody – Bail Revoked; WO = In Custody – Held without Bail; WODN = In Custody – Dangerousness; MO = Mental Observation; NJ = Non-Jail Custody; AW = Arrest Warrant. These expand source labels, not verified detention histories.\n'
    code('''
    bail_std,bail_coverage=adapter.make_bail(bail,filed,filed_cases,SLUG)
    save_table('q5_bail_coverage',bail_coverage)
    status('Q5','Partially answerable','First-event raw status composition is available. Arraignment, payment, posting and complete detention are not established.')
    unknown_share=bail_std.status.eq('Unknown').mean()
    if filed_identity_ok and unknown_share<=.20 and len(bail_std):
        headline,by_year=bail_table(bail_std,n_filed=len(filed_cases))
        headline=headline.rename(index={'% cash bail set':'% explicitly cash-only bail (not all cash/surety)', 'median cash bail ($)':'median explicitly cash-only amount ($)'})
        save_table('q5_shared_metrics',headline)
        _,ax=plt.subplots(figsize=(13,6))
        stacked_pct_bar(by_year,colors=BAIL_COLORS,ax=ax,unit='linked cases with a bail record',xlabel=YEAR_LABEL,
            title=COUNTY+': first recorded bail-event status')
        charts.finish(ax.figure,fig('q5_bail_status'),'First in-range event, not verified arraignment. Cash Bail means explicit cash-only status. Coverage is linked filed case units, not all defendants.')
    else:
        charts.unavailable(COUNTY+': shared bail metrics','More than 20% of standardized status is unknown/ambiguous, or identity coverage fails. Cash-only and held shares are withheld.',fig('q5_bail_status'))
        print('Shared PR/cash/held rates withheld; see the supplementary raw-status distribution below.')
    raw_counts=pd.crosstab(bail_std.year,bail_std.raw_status)
    raw_counts.index=raw_counts.index.astype(int)
    save_table('q5_first_recorded_raw_status_counts',raw_counts)
    # These are source-label counts, not a substitute cash-bail classification.
    raw_total=raw_counts.sum().sort_values().tail(15)
    _,ax=plt.subplots(figsize=(12,max(4,.5*len(raw_total)+2)))
    ax.barh(raw_total.index,raw_total,color=OUTCOME_COLORS['Trial Conviction'])
    ax.set(xlabel='Linked case units; first recorded date',title=COUNTY+': source bail labels (supplementary)')
    ax.grid(axis='y',visible=False);ax.grid(axis='x')
    charts.finish(ax.figure,fig('q5_raw_status_supplement'),'Raw status labels are not equivalent to verified cash-bail, payment, or detention outcomes. First-event cases with multiple source labels remain Conflicting.')
    ''')
    md('''## 6. Time to Disposition
    **Question:** What is the median filing-to-disposition time, by offense category and court?
    **Method:** earliest initiation to latest recorded disposition in Berkshire. Pending cases, negative intervals, and cases with missing disposition endpoints are excluded from duration calculations.
    Cape has no filing date: a separately labeled offense-to-disposition interval is supplementary and does not answer the requested interval. Substantive offense categories are unavailable; source class is supplementary. Groups below 30 usable intervals are omitted.''')
    code('''
    interval='days' if BERK else 'offense_days'
    duration=cases.copy()
    duration.loc[duration.any_missing_disposition_date,interval]=np.nan
    audit=pd.DataFrame([dict(case_units=len(cases),missing_or_incomplete_endpoints=int(duration[interval].isna().sum()),
        negative_intervals=int(duration[interval].lt(0).sum()),usable_intervals=int(duration[interval].ge(0).sum()))])
    save_table('q6_date_interval_audit',audit)
    status('Q6','Partially answerable' if BERK else 'Requested interval unavailable; supplementary interval shown',
        'Initiation approximates filing; substantive offense-category mapping is absent.' if BERK else 'No filing date exists. Offense-to-disposition cannot be relabeled filing-to-disposition.')
    label='Initiation to disposition' if BERK else 'Offense to disposition (supplementary)'
    endpoints_ok='disposition_date' not in INSUFFICIENT
    if endpoints_ok:
        usable=duration.loc[duration[interval].ge(0),interval]
        print(f'{label}: median {usable.median():.0f} days; IQR {usable.quantile(.25):.0f}–{usable.quantile(.75):.0f}; n={len(usable):,}')
        save_table('q6_time_by_source_class',charts.time_chart(duration,'offense',COUNTY,fig('q6_time_by_offense'),interval,label))
        save_table('q6_time_by_cohort',charts.time_chart(duration,'year',COUNTY,fig('q6_time_by_year'),interval,label))
        if allowed('court'):
            save_table('q6_time_by_court',charts.time_chart(duration,'court',COUNTY,fig('q6_time_by_court'),interval,label))
        else:
            charts.unavailable(COUNTY+': time by court','Court coverage exceeds 20% missing/conflicting; court-specific duration is withheld.',fig('q6_time_by_court'))
    else:
        charts.unavailable(COUNTY+': time to disposition','Disposition-date coverage exceeds 20% missing.',fig('q6_time_by_offense'))
    ''')
    md('''## 7. Disparities by Race and Sex
    **Question:** Do dismissal and incarceration rates differ by race/ethnicity and sex?
    **Denominators:** all eligible disposed case units for dismissal; conviction-evidence case units for incarceration.
    Compare with White for race and Male for sex. Keep Missing and explicit Unknown separate. Suppress groups below 30 and withhold a metric when the relevant field exceeds 20% missing.
    These are descriptive recorded differences, not evidence of unequal treatment after controlling for case mix. Declinations before filing cannot be measured.''')
    code('''
    released=[]
    for group in ['race','sex']:
        if outcome_ok and allowed(group):
            rates=charts.disparity_table(cases,group)
            if not sentence_ok:
                rates=rates[rates.metric.eq('dismissal')].copy()
            save_table('q7_'+group,rates)
            charts.disparities(rates,COUNTY,group,fig('q7_rates_by_'+group),sentence_ok)
            released.append(group+' dismissal'+(' and incarceration' if sentence_ok else ' only'))
        else:
            charts.unavailable(COUNTY+': disparities by '+group,'The relevant coverage or outcome prerequisite fails the shared rule; rates are withheld.',fig('q7_rates_by_'+group))
    status('Q7','Partially answerable' if released else 'Unavailable under shared rule',
        'Released: '+', '.join(released)+'. Missingness and suppression remain material limitations.' if released else 'Relevant demographic/outcome coverage exceeds the threshold.')
    ''')
    md('''## 8. Disparities with Controls
    **Question:** Do racial gaps remain within the same offense category and prior-record level?
    **Unavailable as specified.** Neither county supplies a validated prior-record field or complete common three-year filing history. Cape also lacks filing dates.
    An extract-observed earlier case is not necessarily a prior conviction or statewide criminal history. We do not assign zero priors from missing history.
    The supplementary graph compares dismissal within the same representative charge code/description, **without prior-record adjustment**. Both race cells must contain at least 30 eligible cases. It does not establish that gaps remain after the requested controls.''')
    code('''
    status('Q8','Full answer unavailable; limited supplementary comparison',
        'Validated prior-record history and a shared substantive offense crosswalk are missing. No controlled racial-gap estimate is reported.')
    if outcome_ok and allowed('race'):
        save_table('q8_offense_only_dismissal',charts.offense_only(cases,COUNTY,fig('q8_offense_only_dismissal_supplement')))
    else:
        charts.unavailable(COUNTY+': Q8 supplementary comparison','Race or outcome coverage fails the shared threshold.',fig('q8_offense_only_dismissal_supplement'))
    ''')
    md('''## Questions for the Client and Remaining Blockers
    1. Does Berkshire Initiated Dt represent court filing? What does Cape's case-ID year mean, and can actual filing dates be provided?
    2. How should district/superior docket pairs, transfers, multiple defendants, and court-stage charge histories be linked?
    3. Can the team approve a substantive offense-category crosswalk and explain placeholders/unmapped charge codes?
    4. What evidence distinguishes a recorded plea, guilty finding, CWOF, suspended sentence, and actual custody? Can missing sentence types be supplied?
    5. Do bail events identify arraignment, cash versus surety, posting, and detention periods? What do same-day conflicting statuses mean?
    6. Is a consistent three-year history available before each cohort, and is the intended control earlier cases or prior convictions?
    7. Can demographic gaps and the extract's open/closed-case coverage be clarified?
    8. Should the 20% sentence-missingness rule apply to all disposed charges, or only conviction-eligible records? The supplied template uses all disposed charges, including records where sentencing may not apply; this revision follows that stricter source-field rule.

    Original spreadsheets and the supplied ZIP remain unchanged. Review the exported coverage, exclusions, crosswalk and audit tables before comparing counties.''')
    code('''
    save_table('question_answerability',pd.DataFrame(statuses).set_index('question'))
    assert len(statuses)==8 and len(set(x['question'] for x in statuses))==8
    assert cases.index.is_unique and filed_cases.index.is_unique
    assert not cases.outcome.eq('Pending').any()
    assert int(vol.sum())==len(filed_cases)
    if 'q3_outcome_counts' in tables:
        assert int(tables['q3_outcome_counts'].loc['Overall'].sum())==len(cases)
    assert all(not name.startswith('raw_') for name in tables)
    validation=dict(county=SLUG,checks='passed',filed_units=len(filed_cases),disposed_units=len(cases),
        tables=len(tables),figures=len(list(FIG_DIR.glob('*.png'))),source_sha256=source_hashes)
    (COUNTY_DIR/'validation_summary.json').write_text(json.dumps(validation,indent=2),encoding='utf8')
    print('Validation passed. Aggregate tables and 300 dpi figures saved. Source records were not exported.')
    ''')
    n={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},'language_info':{'name':'python','version':'3.13'}},'cells':cells}
    for i,c in enumerate(cells):c['id']=f'{slug}-{i:02d}'
    p=folder/(slug+'_analysis.ipynb')
    if preserve_outputs:
        old=json.loads(p.read_text(encoding='utf8'))
        assert len(old['cells'])==len(cells)
        for current,previous in zip(cells,old['cells']):
            assert current['cell_type']==previous['cell_type']
            if current['cell_type']=='code':
                old_source=previous['source'] if isinstance(previous['source'],str) else ''.join(previous['source'])
                assert current['source']==old_source, 'Code changed: execute again instead of preserving outputs.'
                current['outputs']=previous['outputs'];current['execution_count']=previous['execution_count']
        n['metadata']=old['metadata']
    p.write_text(json.dumps(n,ensure_ascii=False,indent=1),encoding='utf8')
    print(p,len(cells),'cells')

if __name__=='__main__':
    if not (ROOT/'annual_population.csv').is_file():
        raise FileNotFoundError('Keep the supplied annual_population.csv beside this builder.')
    build('berkshire','Berkshire');build('cape_and_islands','Cape & Islands')
