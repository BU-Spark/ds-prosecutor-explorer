from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import openpyxl

START = pd.Timestamp('2017-01-01')
END = pd.Timestamp('2024-12-31')

def normalize_id(series):
    return series.map(lambda x: str(int(x)) if isinstance(x,(float,np.floating)) and pd.notna(x) and x.is_integer()
                      else str(x).strip() if pd.notna(x) else pd.NA).astype('string')


AS_OF=pd.Timestamp('2026-11-23')
def parse_date(s):
    p=pd.to_datetime(s,format='mixed',errors='coerce')
    return p.where(p.ge(pd.Timestamp('1900-01-01'))&p.le(AS_OF)).astype('datetime64[ns]')

def load_cape(path):
    wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
    parts=[];headers=[]
    for sheet in wb:
        values=sheet.values;raw_header=list(next(values));seen={};names=[]
        for i,h in enumerate(raw_header):
            name=str(h).strip() if h is not None else f'Unnamed_{i+1}'
            seen[name]=seen.get(name,0)+1
            names.append(name if seen[name]==1 else f'{name}__{seen[name]}')
            headers.append({'file':path.name,'sheet':sheet.title,'position':i+1,'trimmed_header':name,
                            'analysis_name':names[-1],'duplicate_label':seen[name]>1})
        part=pd.DataFrame(list(values),columns=names)
        for c in names:
            part[c]=part[c].map(lambda x:x.strip() if isinstance(x,str) else x)
            part[c]=part[c].replace(r'^\s*$',pd.NA,regex=True)
        part['exact_repeated_export']=part.duplicated(names,keep='first')
        part['source_sheet']=sheet.title;part['source_row']=np.arange(2,len(part)+2)
        parts.append(part)
    wb.close()
    return pd.concat(parts,ignore_index=True),pd.DataFrame(headers)


def load(DATA_DIR):
    paths={'filed':DATA_DIR/'charges filed.xlsx','disposed':DATA_DIR/'charges disposed.xlsx','bail':DATA_DIR/'bail_data.xlsx'}
    hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in paths.items()}
    loaded={k:load_cape(v) for k,v in paths.items()}
    raw={k:v[0] for k,v in loaded.items()}
    headers=pd.concat([v[1] for v in loaded.values()],ignore_index=True)

    inventory=[]
    for name,frame in raw.items():
        source_cols=[c for c in frame if c not in ['source_row','source_sheet','exact_repeated_export']]
        inventory.append({'extract':name,'rows':len(frame),'columns':len(source_cols),
          'all_blank_columns':sum(frame[c].isna().all() for c in source_cols),
          'repeated_identical_rows_after_first':int(frame.exact_repeated_export.sum())})

    blank_fields=[]
    for name,frame in raw.items():
        for column in frame:
            if frame[column].isna().all():blank_fields.append({'extract':name,'all_blank_field':column})

    assert [len(raw[x]) for x in ['filed','disposed','bail']]==[130242,115763,40274]

    charge_rename={'Docket Number':'docket','Case Number':'case_id','Defendant ID':'person_id',
     '# of Charges on Case':'declared_charge_count','Offense Date':'offense_raw','Disposition Date':'disposition_raw',
     'Charge Code':'charge_code','Charge Code Description':'charge_description','Charge Category':'class_raw',
     'Court Location Description':'court','Description':'agency','Description__2':'case_status',
     'Disposition':'disposition_code','Disposition Description':'disposition_description',
     'Disposition Event Description':'event_description','Dispostion Comment':'disposition_comment',
     'Judge Name':'judge','Defendant Sex':'sex_code','Race':'race_code',
     'Imposed Sent. Type Code':'sentence_code','Imposed Sent. Type Desc.':'sentence_description',
     'Imposed Sent. Date':'sentence_date_raw','Pros. Rec. Sent. Date':'recommended_date_raw'}
    F=raw['filed'].rename(columns=charge_rename).copy()
    D=raw['disposed'].rename(columns=charge_rename).copy()
    B=raw['bail'].rename(columns={'Case Number':'case_id','Status':'bail_code','Description':'bail_description',
     'Bail Amount Requested':'requested','Bail Amount':'set_amount','Date':'bail_raw',
     'Defendant Sex':'sex_code','Race':'race_code','List of Charges on Case':'charge_list',
     'List of Charges on Case (Desc)':'charge_list_description'}).copy()
    race_map={'W':'White','B':'Black','H':'Hispanic (source race field)','A':'Asian','U':'Unknown (U)'}
    sex_map={'M':'Male','F':'Female','U':'Unknown (U)'}
    date_audit=[];quarantine=[]
    for name,frame in [('filed',F),('disposed',D),('bail',B)]:
        frame['case_id']=normalize_id(frame.case_id)
        if 'person_id' in frame:
            frame['person_id']=normalize_id(frame.person_id)
            frame['case_person']=frame.case_id+' | '+frame.person_id.fillna('Missing person ID')
            frame['charge_code']=normalize_id(frame.charge_code)
            frame['declared_charge_count']=pd.to_numeric(frame.declared_charge_count,errors='coerce')
            frame['class_raw']=frame.class_raw.astype('string')
            frame['source_class']=frame.class_raw.fillna('Missing')
            frame['class_plot']=frame.source_class.where(frame.source_class.isin(['F','M+','M-','CM','Missing']),'Unmapped code')
            frame['class_unmapped']=frame.class_raw.notna()&~frame.class_raw.isin(['F','M+','M-','CM'])
            frame['known_criminal']=frame.class_raw.isin(['F','M+','M-'])
            invalid_sex=frame.sex_code.notna()&~frame.sex_code.isin(['M','F','U'])
            frame['severe_shift']=frame.sex_code.eq('Closed').fillna(False)
            frame['unattached_row']=frame.person_id.isna()&frame.charge_code.isna()&frame.charge_description.isna()
            for _,row in frame.loc[frame.severe_shift].iterrows():
                quarantine.append({'extract':name,'sheet':row.source_sheet,'excel_row':int(row.source_row),
                  'reason':'Closed appears in sex field; shifted demographic/status pattern'})
            for _,row in frame.loc[frame.unattached_row].iterrows():
                quarantine.append({'extract':name,'sheet':row.source_sheet,'excel_row':int(row.source_row),
                  'reason':'unattached row: defendant, charge code and description all missing'})
        else:frame['severe_shift']=False
        frame['race']=frame.race_code.map(lambda x:'Missing' if pd.isna(x) else race_map.get(x,f'Unmapped code: {x}'))
        frame['sex']=frame.sex_code.map(lambda x:'Missing' if pd.isna(x) else sex_map.get(x,f'Unmapped code: {x}'))
        frame['id_year_proxy']=pd.to_numeric(frame.case_id.str.extract(r'^(\d{2})-\d{2}-\d+$')[0],errors='coerce')+2000
        frame['id_year_category']=frame.id_year_proxy.map(lambda x:'Missing proxy year' if pd.isna(x) else str(int(x)))
        for source,target in [('offense_raw','offense_date'),('disposition_raw','disposition_date'),
                               ('sentence_date_raw','sentence_date'),('recommended_date_raw','recommended_date'),('bail_raw','bail_date')]:
            if source in frame:
                parsed=pd.to_datetime(frame[source],format='mixed',errors='coerce')
                frame[target]=parse_date(frame[source])
                frame[target+'_quality']=np.select([frame[source].isna(),frame[target].isna()],['Missing','Invalid / out of bounds'],default='Valid')
                date_audit.append({'extract':name,'field':source,'rows':len(frame),
                  'source_blank':int(frame[source].isna().sum()),'invalid_nonblank':int((frame[source].notna()&frame[target].isna()).sum()),
                  'raw_min':str(parsed.min()),'raw_max':str(parsed.max()),
                  'before_1900':int(parsed.lt(pd.Timestamp('1900-01-01')).sum()),'after_as_of':int(parsed.gt(AS_OF).sum())})

    quarantine=pd.DataFrame(quarantine)

    return F, D, B, pd.DataFrame(inventory), hashes
