"""Check saved notebooks, aggregate reconciliations, source preservation and ZIP."""
from pathlib import Path
import base64
import hashlib
import json
import os
import zipfile
import nbformat
import pandas as pd

ROOT=Path(__file__).resolve().parent
REPO_ROOT=ROOT.parent
REFERENCE_SHA256={
    'viz_style.py':'278ce1884b1fcd822a986d8e273488529733a0d5acbef49bad2c19d33d296079',
    'county_charts.py':'66d1a88c9ebea924926ca7987a3b461bf9a1887dedc3b7197c48b2d3373a7ece',
    'county_analysis_template.ipynb':'cf7ccce7cfc0ca8a2c4f9be2ec46b8c2eb54b3a1360d87aa2085e504990a41c6',
}

def sha(path):
    data=path.read_bytes()
    if path.suffix in {'.py','.ipynb','.md','.txt','.csv','.json'}:
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()

def verify():
    manifest={'review_date':'2026-11-23','organization_date':'2026-11-26','scope':['berkshire','cape_and_islands'],'counties':{},'references':{},'checks':[],'not_checked':[],'text_hash_newlines':'LF-normalized; raw workbook hashes use original bytes'}
    for name in ['viz_style.py','county_charts.py','county_analysis_template.ipynb']:
        assert sha(REPO_ROOT/name)==REFERENCE_SHA256[name]
        manifest['references'][name]=dict(sha256=sha(REPO_ROOT/name),url='https://github.com/BU-Spark/ds-prosecutor-explorer/blob/parin-dev/'+name)
    for slug in manifest['scope']:
        folder=ROOT/slug
        path=folder/(slug+'_analysis.ipynb')
        n=nbformat.read(path,as_version=4);nbformat.validate(n)
        codes=[c for c in n.cells if c.cell_type=='code']
        assert all(c.execution_count is not None for c in codes)
        assert not [o for c in codes for o in c.outputs if o.output_type=='error']
        pngs=[o.data['image/png'] for c in codes for o in c.outputs if 'image/png' in o.get('data',{})]
        assert len(pngs)>=8
        assert all(base64.b64decode(v).startswith(b'\x89PNG\r\n\x1a\n') for v in pngs)
        t=folder/'tables'
        answer=pd.read_csv(t/'question_answerability.csv',index_col=0)
        assert answer.index.tolist()==[f'Q{i}' for i in range(1,9)]
        flow=pd.read_csv(t/'cohort_flow.csv',index_col=0).iloc[0]
        assert flow.observed_case_units==flow.pending_or_unconfirmed_excluded+flow.disposed_case_units
        crosswalk=pd.read_csv(t/'disposition_crosswalk.csv',index_col=0)
        exclusions=pd.read_csv(t/'source_exclusions.csv',index_col=0).set_index('extract')
        assert crosswalk.charge_rows.sum()==exclusions.at['disposed','retained_rows']
        assert (exclusions.source_rows-exclusions.removed_rows).equals(exclusions.retained_rows)
        if (t/'q3_outcome_counts.csv').exists():
            counts=pd.read_csv(t/'q3_outcome_counts.csv',index_col=0)
            assert counts.loc['Overall'].sum()==flow.disposed_case_units
            assert counts.drop(index='Overall').sum().equals(counts.loc['Overall'])
            percentages=pd.read_csv(t/'q3_outcome_pct.csv',index_col=0)
            assert percentages.sum(axis=1).sub(100).abs().lt(1e-8).all()
        volume=pd.read_csv(t/'q1_volume.csv',index_col=0)
        assert volume.cases.sum()==flow.filed_case_units
        for group in ['race','sex']:
            p=t/('q7_'+group+'.csv')
            if p.exists():
                a=pd.read_csv(p,index_col=0)
                assert a.loc[a.suppressed,'rate_pct'].isna().all()
                assert a.loc[~a.suppressed,'n'].ge(30).all()
                assert a.rate_pct.dropna().between(0,100).all()
        source_folder=Path(os.environ.get('PROSECUTOR_DATA_ROOT',str(ROOT.parent)))/('berkshire' if slug=='berkshire' else 'cape and island')
        names=({'filed':'charges filed info.xlsx','disposed':'disposed info.xlsx','bail':'bail info.xlsx'} if slug=='berkshire' else
               {'filed':'charges filed.xlsx','disposed':'charges disposed.xlsx','bail':'bail_data.xlsx'})
        validation=json.loads((folder/'validation_summary.json').read_text())
        sources_present=all((source_folder/name).is_file() for name in names.values())
        if sources_present:
            for label,name in names.items():assert sha(source_folder/name)==validation['source_sha256'][label]
        else:
            manifest['not_checked'].append(slug+': raw source hashes (source files not present)')
        manifest['counties'][slug]=dict(notebook_sha256=sha(path),embedded_images=len(pngs),executed_cells=len(codes),
            figures=len(list((REPO_ROOT/'figures'/slug).glob('*.png'))),tables=len(list(t.glob('*.csv'))),source_hashes_verified=sources_present,validation=validation)
    original_zip=ROOT.parent/'county_notebooks_for_github.zip'
    if original_zip.exists():
        with zipfile.ZipFile(original_zip) as original:
            for slug in ['berkshire','cape_and_islands','norfolk']:
                name=f'county_notebooks_for_github/{slug}/{slug}_analysis.ipynb'
                assert original.read(name)==(ROOT.parent/name).read_bytes()
        manifest['checks'].append('Original ZIP notebooks including Norfolk unchanged')
    else:
        manifest['not_checked'].append('Original ZIP comparison (original ZIP not present)')
    manifest['checks']+=['Both notebooks validated and fully executed with no error outputs','Embedded images decoded successfully',
        'Case cohort and outcome counts reconciled','Outcome percentages sum to 100','Small-cell rates suppressed',
        'Shared reference modules unchanged']
    if all(c['source_hashes_verified'] for c in manifest['counties'].values()):
        manifest['checks'].append('Raw source workbook hashes unchanged')
    (ROOT/'review_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    allowed_root={'README_shared_counties.md','requirements_shared_counties.txt','.gitignore','.gitattributes','annual_population.csv',
        'county_adapter.py','county_review_charts.py','berkshire_source.py','cape_and_islands_source.py','build_notebooks.py','execute_notebooks.py','verify_release.py','review_manifest.json'}
    files=[ROOT/name for name in sorted(allowed_root)]
    files += [REPO_ROOT/name for name in ['county_analysis_template.ipynb','county_charts.py','viz_style.py','README.md','.gitattributes']]
    for slug in manifest['scope']:
        files += [p for p in (ROOT/slug).rglob('*') if p.is_file() and p.suffix in ['.ipynb','.csv','.json']]
        files += list((REPO_ROOT/'figures'/slug).glob('*.png'))
    out=ROOT/'county_notebooks_for_github_review.zip'
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(REPO_ROOT))
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        assert not any('/.execution/' in name or name.endswith(('.xlsx','.parquet','.db')) for name in z.namelist())
    print(json.dumps(manifest,indent=2));print('Review ZIP:',out,'bytes:',out.stat().st_size)

if __name__=='__main__':verify()
