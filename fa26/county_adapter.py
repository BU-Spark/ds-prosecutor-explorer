"""County-specific evidence rules; shared visuals live in viz_style/county_charts.

Raw spreadsheets are read only. Exclusions and mapping decisions are exported
as aggregate audits. No inferred filing date or prior criminal record is made.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from viz_style import SEVERITY, case_outcome

AS_OF = pd.Timestamp('2026-11-23')
YEARS = range(2017, 2025)
THRESHOLD = .20


def unique_value(s):
    values = s.dropna().astype(str).unique()
    return values[0] if len(values) == 1 else ('Conflicting' if len(values) > 1 else 'Missing')


def load_sources(slug, data_root):
    if slug == 'berkshire':
        import berkshire_source as source
        folder = 'berkshire'
    else:
        import cape_and_islands_source as source
        folder = 'cape and island'
    return source.load(Path(data_root) / folder)


def prepare(slug, raw):
    """Clean export artifacts, then map outcomes without changing source values."""
    filed, disposed, bail, inventory, hashes = raw
    berk = slug == 'berkshire'
    exclusions = []
    frames = []
    for name, original in [('filed', filed), ('disposed', disposed)]:
        if berk:
            bad = original.exact_duplicate
        else:
            bad = original.severe_shift | original.unattached_row | original.exact_repeated_export
        d = original.loc[~bad].copy()
        exclusions.append(dict(extract=name, source_rows=len(original), removed_rows=int(bad.sum()), retained_rows=len(d),
            duplicate_export_rows=int((original.exact_duplicate if berk else original.exact_repeated_export).sum()),
            shifted_rows=0 if berk else int(original.severe_shift.sum()),
            unattached_rows=0 if berk else int(original.unattached_row.sum())))
        if berk:
            # A pair of district/superior docket fields cannot identify court-stage
            # charge histories. Use the docket associated with the recorded court,
            # then the sole available docket. Ambiguous pairs remain unresolved.
            district = source_id(d['DistCt Dckt'])
            superior = source_id(d['SupCt Dckt'])
            court = d.court.fillna('').str.lower()
            d['docket'] = pd.Series(pd.NA, index=d.index, dtype='string')
            d.loc[court.str.contains('superior'), 'docket'] = superior
            d.loc[court.str.contains('district'), 'docket'] = district
            sole_d = district.notna() & superior.isna()
            sole_s = superior.notna() & district.isna()
            d.loc[d.docket.isna() & sole_d, 'docket'] = district
            d.loc[d.docket.isna() & sole_s, 'docket'] = superior
            d['filing_date'] = d.initiated_date
            d['filing_year'] = d.initiated_date.dt.year
            d['year_basis'] = 'Recorded initiation year (filing proxy)'
            d['charge_level'] = d.offense_class
            d['charge_count'] = pd.to_numeric(d.count_no, errors='coerce')
        else:
            d['docket'] = source_id(d.docket)
            d['filing_date'] = pd.NaT
            d['filing_year'] = d.id_year_proxy
            d['year_basis'] = 'Unverified case-ID prefix year (not filing date)'
            d['charge_level'] = d.class_raw
            d['charge_count'] = np.nan  # declared case charge total is not a charge ordinal
        d['case_key'] = d.docket + ' | ' + d.person_id
        d['criminal'] = d.charge_level.isin(['F', 'M+', 'M-'])
        d['offense'] = d.charge_level.map({'F':'Felony', 'M+':'Misdemeanor M+', 'M-':'Misdemeanor M-'})
        frames.append(d)
    f, d = frames
    if berk:
        typ = d.disp_type.fillna('')
        desc = d.disp_description.fillna('')
        text = d.sentence_translation
        positive = d[['Min Actl Jaill Impsd Term', 'Max Actl Jail Imp Term']].apply(pd.to_numeric, errors='coerce').gt(0).any(axis=1)
        custody = text.isin(['Jail', 'Jail (Time Served)', 'Split Sentence', 'Committed'])
        cwof = typ.eq('Continued Without Finding') | (typ.eq('Plea') & text.eq('Continued w/o Finding'))
        d['cwof_sentence_conflict'] = cwof & (positive | custody)
        d['outcome'] = np.select([
            typ.eq(''), d.cwof_sentence_conflict, cwof,
            typ.eq('Trial') & desc.eq('Guilty'),
            (typ.eq('Trial') & desc.isin(['Not Guilty','Required Finding of Not Guilty','Directed Verdict'])) | typ.isin(['Not Guilty','Not Guilty Insanity','Required Finding of Not Guilty','Directed Verdict']),
            typ.str.startswith('Dismissed') | typ.eq('Nolle Prosequi'),
            typ.eq('Plea') & ~text.isin(['Continued w/o Change of Plea','Filed w/o Change of Plea'])],
            ['Unknown','Other','CWOF','Trial Conviction','Acquittal','Dismissal','Plea'], default='Other')
        d['closed'] = d.Status.eq('Closed')
        d['sentence'] = np.select([custody | positive, text.eq('Probation'), text.eq('Suspended Sentence'),
            text.isin(['Fines','Court Cost/Restitution','Community Service','House Arrest'])],
            ['Incarceration','Probation','Suspended','Fines/Other'], default='Unknown')
        d['conviction_evidence'] = typ.eq('Guilty') | d.outcome.eq('Trial Conviction') | (d.outcome.eq('Plea') & d.sentence.ne('Unknown'))
        d['raw_disposition'] = d.disp_type
        d['sentence_source'] = text
    else:
        mapping = {'GPL':'Plea','GJT':'Trial Conviction','GBT':'Trial Conviction','GJW':'Trial Conviction','CWF':'CWOF',
            'NGBT':'Acquittal','NGJT':'Acquittal','NGJW':'Acquittal','NGI':'Acquittal','NOP':'Dismissal','NPDPH':'Dismissal','DIS':'Dismissal','OBJ':'Dismissal'}
        d['outcome'] = d.disposition_code.map(mapping).fillna('Other').where(d.disposition_code.notna(), 'Unknown')
        d['closed'] = d.case_status.isin(['Closed','Closed YO','Closed Civil Ca','Completed'])
        d['sentence'] = d.sentence_code.map({'TERM':'Incarceration','SPLT':'Incarceration','LF':'Incarceration','LWOP':'Incarceration','SS':'Suspended','F':'Filed'}).fillna('Unknown')
        d['conviction_evidence'] = d.outcome.isin(['Plea','Trial Conviction'])
        d['raw_disposition'] = d.disposition_code
        d['sentence_source'] = d.sentence_code
        d['cwof_sentence_conflict'] = False
    d['conviction_evidence'] &= d.criminal
    d['pending_or_unconfirmed'] = ~d.closed | d.outcome.eq('Unknown')
    # Unknown outcome on a closed case is not evidence that the charge is pending.
    d['outcome_for_case'] = d.outcome.where(d.closed, 'Pending')
    crosswalk = (d.groupby(['raw_disposition','outcome'], dropna=False).size().rename('charge_rows').reset_index())
    return f, d, bail.copy(), inventory, hashes, pd.DataFrame(exclusions), crosswalk


def source_id(s):
    return s.map(lambda x: str(int(x)) if isinstance(x, (float, np.floating)) and pd.notna(x) and x.is_integer()
                 else str(x).strip() if pd.notna(x) else pd.NA).replace('', pd.NA).astype('string')


def coverage_table(f, d):
    rows = []
    for label, frame in [('filed', f), ('disposed', d)]:
        # Charge-level coverage is measured before dropping missing case identities.
        a = frame[frame.criminal & frame.filing_year.isin(YEARS)]
        fields = {'docket':'docket', 'defendant_id':'person_id','filing_date':'filing_date',
            'charge_level':'charge_level','offense_category':None,'court':'court','race':'race_code','sex':'sex_code'}
        if label == 'disposed':
            fields.update(disposition_date='disposition_date', disposition='raw_disposition', sentence_type='sentence_source')
        for shared, col in fields.items():
            missing = pd.Series(True, index=a.index) if col is None else a[col].isna()
            pct = missing.mean() * 100
            available=a.loc[~missing,'filing_year'].dropna()
            rows.append(dict(extract=label, field=shared, rows=len(a), missing_rows=int(missing.sum()), pct_missing=pct,
                years_available=f'{int(available.min())}-{int(available.max())}' if len(available) else 'none',
                status='insufficient data' if pct > 100*THRESHOLD else 'ok',
                note='No validated substantive offense crosswalk; source class is supplementary.' if col is None else ''))
    return pd.DataFrame(rows)


def build_cases(f, d):
    def aggregate(frame, outcomes):
        a = frame[frame.case_key.notna()].copy()
        a['level_rank'] = a.charge_level.map({'F':0,'M+':1,'M-':2}).fillna(9)
        a['count_rank'] = a.charge_count.fillna(999999)
        lead = a.sort_values(['case_key','level_rank','count_rank','charge_code','source_row'], kind='stable').drop_duplicates('case_key').set_index('case_key')
        g = a.groupby('case_key', sort=False)
        c = g.agg(filing_date=('filing_date','min'), year=('filing_year','min'), criminal=('criminal','max'), n_charges=('case_key','size'))
        for col in ['race','sex','court']:
            c[col] = g[col].first().fillna('Missing').where(g[col].nunique().le(1),'Conflicting')
        c['offense'] = lead.offense.fillna('Unknown')
        c['charge'] = lead.charge_code.fillna('Missing')+' | '+lead.charge_description.fillna('Missing')
        if outcomes:
            ranks={name:i for i,name in enumerate(SEVERITY)}
            a['outcome_rank']=a.outcome.map(ranks)
            c['outcome']=a.groupby('case_key').outcome_rank.min().map(dict(enumerate(SEVERITY)))
            c.loc[~g.closed.all(),'outcome']='Pending'
            c['end'] = g.disposition_date.max()
            c['offense_start'] = g.offense_date.min()
            c['conviction_evidence'] = g.conviction_evidence.max()
            c['any_missing_disposition_date'] = g.disposition_date.count().lt(g.size())
            # Sentence priority follows the shared template; Unknown remains an
            # explicit category, and incomplete charge evidence is also reported.
            conv = a[a.conviction_evidence]
            ranks = {'Incarceration':0,'Probation':1,'Suspended':2,'Fines/Other':3,'Filed':4,'Unknown':5}
            picked = conv.assign(sr=conv.sentence.map(ranks)).sort_values('sr').drop_duplicates('case_key').set_index('case_key')
            c['sentence'] = picked.sentence.reindex(c.index).fillna('Unknown')
            c['incomplete_sentence_evidence'] = conv.assign(sentence_unknown=conv.sentence.eq('Unknown')).groupby('case_key').sentence_unknown.max().reindex(c.index,fill_value=False).astype(bool)
        return c[c.criminal & c.year.isin(YEARS)].copy()
    filed_cases = aggregate(f, False)
    all_cases = aggregate(d, True)
    cases = all_cases[all_cases.outcome.ne('Pending')].copy()
    cases['days'] = (cases.end-cases.filing_date).dt.days
    cases['offense_days'] = (cases.end-cases.offense_start).dt.days
    cases['case_key'] = cases.index
    cases['prior_record'] = 'Unknown'
    assert filed_cases.index.is_unique and cases.index.is_unique
    assert cases.outcome.isin(SEVERITY).all()
    return filed_cases, all_cases, cases


def metric_coverage(cases):
    rows=[]
    for field in ['race','sex','court','sentence']:
        c=cases[cases.conviction_evidence] if field=='sentence' else cases
        missing=c[field].isin(['Missing','Conflicting','Unknown']) if field in ['court','sentence'] else c[field].isin(['Missing','Conflicting'])
        rows.append(dict(field=field, denominator=len(c), missing_or_conflicting=int(missing.sum()), pct_missing=100*missing.mean(),
            status='insufficient data' if missing.mean()>THRESHOLD else 'ok'))
    return pd.DataFrame(rows).set_index('field')


def make_bail(bail, f, filed_cases, slug):
    """Only unambiguous case-ID -> docket/defendant links; no person expansion."""
    a=bail[bail.bail_date.dt.year.isin(YEARS)].copy()
    first_date=a.groupby('case_id').bail_date.transform('min')
    a=a[a.bail_date.eq(first_date)]
    field='bail_status' if slug=='berkshire' else 'bail_code'
    mapping=({'Released on Own Recognizance':'PR','Held Without Right To Bail':'Held Without Bail','Cash Only':'Cash Bail'}
             if slug=='berkshire' else {'PR':'PR','PRBW':'PR','WO':'Held Without Bail'})
    a['standard_status']=a[field].map(mapping).fillna('Unknown')
    g=a.groupby('case_id')
    first=g.agg(raw_status=(field,unique_value), status=('standard_status',unique_value), bail_date=('bail_date','min'))
    first['status']=first.status.where(first.status.isin(['PR','Cash Bail','Held Without Bail']),'Unknown')
    a['numeric_amount']=pd.to_numeric(a.set_amount,errors='coerce')
    first['amount']=g.numeric_amount.agg(lambda s:s.dropna().iloc[0] if s.dropna().nunique()==1 else np.nan)
    links=f[['case_id','case_key']].dropna().drop_duplicates()
    unambiguous=links.groupby('case_id').case_key.nunique()
    links=links[links.case_id.isin(unambiguous[unambiguous.eq(1)].index)]
    b=first.reset_index().merge(links,on='case_id',validate='one_to_one')
    b=b[b.case_key.isin(filed_cases.index)].copy()
    # Several source case IDs may resolve to one docket/defendant. Select the
    # earliest linked event again at the final counting unit; do not double count.
    earliest=b.groupby('case_key').bail_date.transform('min')
    b=b[b.bail_date.eq(earliest)]
    b=b.groupby('case_key',as_index=False).agg(status=('status',unique_value),raw_status=('raw_status',unique_value),
        bail_date=('bail_date','min'),amount=('amount',lambda s:s.dropna().iloc[0] if s.dropna().nunique()==1 else np.nan))
    b['status']=b.status.where(b.status.isin(['PR','Cash Bail','Held Without Bail']),'Unknown')
    b['year']=b.case_key.map(filed_cases.year).astype(int)
    b['unable_to_post']=np.nan
    # Amount is meaningful as a cash-bail amount only for explicit Cash Only.
    b['recorded_amount']=b.amount
    b.loc[~b.status.eq('Cash Bail'),'amount']=np.nan
    assert b.case_key.is_unique
    diagnostics=pd.DataFrame([dict(first_event_case_ids=len(first), linked_filed_case_units=len(b), filed_case_units=len(filed_cases),
        coverage_pct=100*len(b)/len(filed_cases), unknown_standard_status_pct=100*b.status.eq('Unknown').mean(),
        ambiguous_source_case_ids=int(unambiguous.gt(1).sum()), note='First recorded in-range event; arraignment and payment are unverified.')])
    return b,diagnostics
