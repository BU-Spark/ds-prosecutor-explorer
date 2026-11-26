from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import openpyxl

START = pd.Timestamp('2017-01-01')
END = pd.Timestamp('2024-12-31')

def in_window(series, end=END):
    return series.between(START,end)

def parse_date(series):
    # Keep raw columns separately. Malformed centuries are flagged, not guessed.
    parsed = pd.to_datetime(series, format='mixed', errors='coerce')
    years = parsed.dt.year
    return parsed.where(years.between(1900,2026)).astype('datetime64[ns]')

def normalize_id(series):
    return series.map(lambda x: str(int(x)) if isinstance(x,(float,np.floating)) and pd.notna(x) and x.is_integer()
                      else str(x).strip() if pd.notna(x) else pd.NA).astype('string')

def load_workbook(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    frames, header = [], None
    for sheet in wb:
        values = sheet.values
        first = next(values)
        if header is None:
            header = [str(v).strip() for v in first]
            rows, first_excel_row = list(values), 2
        elif [str(v).strip() for v in first] == header:
            rows, first_excel_row = list(values), 2
        else:
            rows, first_excel_row = [first] + list(values), 1
        part = pd.DataFrame(rows, columns=header)
        part['source_sheet'] = sheet.title
        part['source_row'] = np.arange(first_excel_row, first_excel_row+len(part))
        frames.append(part)
    wb.close()
    frame = pd.concat(frames, ignore_index=True)
    for column in header:
        frame[column] = frame[column].map(lambda x: x.strip() if isinstance(x,str) else x)
        frame[column] = frame[column].replace(r'^\s*$', pd.NA, regex=True)
    return frame

def load(DATA_DIR):
    paths = {'filed':DATA_DIR/'charges filed info.xlsx',
             'disposed':DATA_DIR/'disposed info.xlsx', 'bail':DATA_DIR/'bail info.xlsx'}
    source_hashes = {name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
    raw = {name:load_workbook(path) for name,path in paths.items()}
    inventory=[]
    for name, frame in raw.items():
        cols=[c for c in frame if not c.startswith('source_')]
        frame['exact_duplicate'] = frame.duplicated(cols, keep='first')
        for sheet, sub in frame.groupby('source_sheet', sort=False):
            inventory.append({'extract':name,'sheet':sheet,'rows':len(sub),
                              'source_columns':len(cols),'repeated_export_rows':int(sub.exact_duplicate.sum())})

    assert len(raw['filed']) == 77250 and len(raw['disposed']) == 72896 and len(raw['bail']) == 25420
    assert raw['filed'].query("source_sheet == 'List_Frame_2'").source_row.min() == 1

    filed = raw['filed'].rename(columns={'CaseNo':'case_id','Id Prsn Dfndnt':'person_id',
     'Offense Dt':'offense_raw','Initiated Dt':'initiated_raw','Chrg Cnt':'count_no',
     'Chrg Code':'charge_code','Chrg Desc':'charge_description','Offns Class':'offense_class',
     'Race':'race_code','Gender':'sex_code','Ofcr Agncy':'agency','Current or Last Court':'court'}).copy()
    disposed = raw['disposed'].rename(columns={'Nmbr Cs':'case_id','Id Prsn Dfndnt':'person_id',
     'Offense Dt':'offense_raw','Initiated Dt':'initiated_raw','Chrg Cnt':'count_no',
     'Chrg Code':'charge_code','Chrg Desc':'charge_description','Offns Class':'offense_class',
     'Race':'race_code','Gender':'sex_code','Officer Agncy':'agency','Court':'court',
     'Judge':'judge','Disp Dt':'disposed_raw','Disp Type':'disp_type','Disp Desc':'disp_description',
     'Sentence Translation':'sentence_translation'}).copy()
    bail = raw['bail'].rename(columns={'Nmbr Cs':'case_id','Race':'race_code','Sex':'sex_code',
     'Date Sts':'bail_raw','Desc Dfndnt Sts':'bail_status','Bail Req':'requested','Bail Set':'set_amount',
     'Case Type':'case_type','Crime Type':'crime_type'}).copy()
    race_map={'W':'White','B':'Black','H':'Hispanic (source race field)','A':'Asian','U':'Unknown (U)'}
    sex_map={'M':'Male','F':'Female','U':'Unknown (U)'}
    date_audit=[]
    for name, frame in [('filed',filed),('disposed',disposed),('bail',bail)]:
        frame['case_id']=normalize_id(frame.case_id)
        if 'person_id' in frame:
            frame['person_id']=normalize_id(frame.person_id)
            frame['case_person']=frame.case_id+' | '+frame.person_id
            frame['charge_code']=normalize_id(frame.charge_code)
            frame['count_no']=normalize_id(frame.count_no)
            frame['offense_class']=frame.offense_class.fillna('Unknown')
            frame['criminal_charge']=frame.offense_class.isin(['F','M+','M-'])
            frame['placeholder_charge']=frame.charge_code.isin(['666666','999999'])
        for source, target in [('offense_raw','offense_date'),('initiated_raw','initiated_date'),
                               ('disposed_raw','disposition_date'),('bail_raw','bail_date')]:
            if source in frame:
                frame[target]=parse_date(frame[source])
                date_audit.append({'extract':name,'field':source,'blank':int(frame[source].isna().sum()),
                  'invalid_or_outside_1900_2026':int((frame[source].notna()&frame[target].isna()).sum()),
                  'valid_min':frame[target].min(),'valid_max':frame[target].max()})
        frame['race']=frame.race_code.map(lambda x: 'Missing' if pd.isna(x) else race_map.get(x,f'Code {x} (unverified)'))
        frame['sex']=frame.sex_code.map(lambda x: 'Missing' if pd.isna(x) else sex_map.get(x,f'Code {x} (unverified)'))
    return filed, disposed, bail, pd.DataFrame(inventory), source_hashes
