"""Evidence-aware chart labels using the team's unchanged shared visual style."""
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from viz_style import OUTCOME_COLORS, TEXT_SECONDARY, stacked_pct_bar, save_fig
from county_charts import volume_table, MIN_CELL

BLUE = OUTCOME_COLORS['Trial Conviction']


def finish(fig, path, note=''):
    if note:
        fig.text(.01, -.03, '\n'.join(textwrap.wrap(note, 125)), fontsize=10, color=TEXT_SECONDARY, va='top')
    save_fig(fig, path)
    plt.show()
    plt.close(fig)


def unavailable(title, reason, path):
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.axis('off')
    ax.set_title(title)
    ax.text(0, .65, 'Unavailable under the shared reporting rules', weight='bold', transform=ax.transAxes)
    ax.text(0, .44, '\n'.join(textwrap.wrap(reason, 100)), transform=ax.transAxes, va='top', fontsize=13)
    finish(fig, path)


def volume(vol, county, year_label, path):
    t = volume_table(vol)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(t.index, t.cases, color=BLUE, width=.7)
    for y, n, change in zip(t.index, t.cases, t.pct_change_yoy):
        label=f'{int(n):,}'+(f'\n({change:+.0f}%)' if pd.notna(change) else '')
        ax.text(y,n,label,ha='center',va='bottom',fontsize=11)
    ax.set(xticks=list(t.index), ylim=(0,t.cases.max()*1.23), xlabel=year_label,
           ylabel='Criminal case units (docket × defendant)',title=county+': recorded criminal case volume')
    finish(fig,path,'Open cases included. Annual counts use the earliest observed year per case unit. No causal effect is inferred from calendar changes.')
    return t


def per_capita(vol, population, county, year_label, path):
    rate=vol.div(population.reindex(vol.index))*10000
    fig,ax=plt.subplots(figsize=(12,6));ax.plot(rate.index,rate,marker='o',color=BLUE,lw=2)
    for x,y in rate.items():ax.annotate(f'{y:.1f}',(x,y),xytext=(0,9),textcoords='offset points',ha='center',fontsize=11)
    ax.set(xticks=list(rate.index),ylim=(0,rate.max()*1.2),xlabel=year_label,ylabel='Recorded case units per 10,000 residents',
           title=county+': caseload-to-population proxy')
    finish(fig,path,'Annual Census PEP population, with a vintage change at 2020. Cape & Islands combines Barnstable, Dukes and Nantucket. This is caseload relative to residents, not a resident crime-risk rate.')
    return rate.rename('recorded_case_units_per_10k').to_frame()


def outcomes(cases, county, year_label, path):
    counts=pd.crosstab(cases.year,cases.outcome).reindex(columns=OUTCOME_COLORS,fill_value=0)
    counts.index=counts.index.astype(int)
    counts.loc['Overall']=counts.sum()
    assert counts.loc['Overall'].sum()==len(cases)
    _,ax=plt.subplots(figsize=(14,6))
    stacked_pct_bar(counts,unit='disposed criminal case units',xlabel=year_label,ax=ax,title=county+': recorded case outcomes')
    finish(ax.figure,path,'Most severe observed charge outcome per docket/defendant. Any recorded open charge excludes the case. Unknown remains visible; mapped zero diversion does not establish zero program participation.')
    return counts,(counts.div(counts.sum(axis=1),axis=0)*100)


SENTENCE_COLORS={'Incarceration':BLUE,'Probation':'#eb6834','Suspended':'#eda100','Fines/Other':'#1baf7a','Filed':'#8a8984','Unknown':'#c9c8c2'}


def sentencing(cases,county,path):
    v=cases[cases.conviction_evidence]
    counts=pd.crosstab(v.year,v.sentence).reindex(columns=SENTENCE_COLORS,fill_value=0)
    counts.index=counts.index.astype(int);counts.loc['Overall']=counts.sum()
    _,ax=plt.subplots(figsize=(14,6));stacked_pct_bar(counts,unit='conviction-evidence case units',xlabel='Case cohort year',ax=ax,
        colors=SENTENCE_COLORS,title=county+': recorded sentence types')
    finish(ax.figure,path,'Sentence evidence, not time served. Suspended sentences are separate; missing evidence is not treated as no incarceration. Berkshire recorded pleas require additional conviction evidence.')
    out=v.sentence.value_counts().reindex(SENTENCE_COLORS,fill_value=0).rename('cases').to_frame()
    out['pct']=100*out.cases/len(v);out['missing_sentence_pct']=100*v.sentence.eq('Unknown').mean()
    return out


def time_chart(cases,by,county,path,interval='days',label='Initiation to disposition'):
    t=cases[cases[interval].ge(0)]
    g=t.groupby(by)[interval]
    out=g.agg(n='size',median='median');out['q1']=g.quantile(.25);out['q3']=g.quantile(.75)
    out=out[out.n.ge(MIN_CELL)]
    if out.empty:
        unavailable(county+': '+label,'No group has at least 30 eligible intervals.',path);return out
    if by=='year':
        time_by_year_table(out,county,path,label)
        return out
    display=out.sort_values('n',ascending=False).head(15).sort_values('median')
    fig,ax=plt.subplots(figsize=(12,max(4,.5*len(display)+2)))
    y=np.arange(len(display));ax.hlines(y,display.q1,display.q3,color=BLUE,alpha=.4,lw=7);ax.plot(display['median'],y,'o',color=BLUE)
    for i,row in enumerate(display.itertuples()):ax.text(row.q3+8,i,f'{row.median:.0f} days (n={row.n:,})',va='center',fontsize=11)
    ax.set(yticks=y,yticklabels=[str(v) for v in display.index],xlim=(0,display.q3.max()*1.5+15),xlabel=label+' (days; dot = median, line = IQR)',title=county+': '+label.lower()+' by '+by)
    ax.grid(axis='y',visible=False);ax.grid(axis='x')
    finish(fig,path,'Pending cases, missing endpoints and negative intervals excluded. Groups with fewer than 30 usable intervals omitted. Source offense class is not a substantive crime category.')
    return out


def time_by_year_table(table,county,path,label):
    """Render the already audited Q6 aggregate table; no metric is recomputed."""
    ordered=table.sort_index()
    x=ordered.index.astype(int)
    fig,ax=plt.subplots(figsize=(12,6))
    ax.fill_between(x,ordered.q1,ordered.q3,color=BLUE,alpha=.2,label='IQR')
    ax.plot(x,ordered['median'],marker='o',color=BLUE,lw=2,label='Median')
    for year,row in ordered.iterrows():
        ax.annotate(f'{row["median"]:.0f}',(int(year),row['median']),xytext=(0,9),textcoords='offset points',ha='center',fontsize=11)
    ax.set(xticks=list(x),ylim=(0,ordered.q3.max()*1.2),xlabel='Case cohort year',ylabel='Days',
        title=county+': time to disposition by cohort year\n'+label)
    ax.legend(loc='upper left',bbox_to_anchor=(1.01,1))
    finish(fig,path,'Dots show medians; shaded band is the interquartile range. Pending cases, incomplete endpoints and negative intervals excluded. Each cohort must have at least 30 usable intervals.')


def disparity_table(cases,group):
    ref='White' if group=='race' else 'Male'
    rows=[]
    for metric,eligible,event in [('dismissal',cases,cases.outcome.eq('Dismissal')),
        ('incarceration',cases[cases.conviction_evidence],cases.sentence.eq('Incarceration'))]:
        a=eligible.assign(event=event.reindex(eligible.index))
        g=a.groupby(group).agg(n=('case_key','size'),events=('event','sum'),missing_sentence=('sentence',lambda s:int(s.eq('Unknown').sum())))
        g['rate_pct']=100*g.events/g.n
        valid=g.n.ge(MIN_CELL)
        g['suppressed']=~valid
        # Do not export the hidden small-cell numerator or rate.
        g.loc[~valid,['events','rate_pct']]=np.nan
        reference=g.at[ref,'rate_pct'] if ref in g.index and valid.loc[ref] else np.nan
        g['ratio_vs_'+ref]=g.rate_pct/reference if pd.notna(reference) and reference>0 else np.nan
        g['missing_sentence_pct']=100*g.missing_sentence/g.n if metric=='incarceration' else np.nan
        g.loc[~valid,['missing_sentence','missing_sentence_pct']]=np.nan
        g['metric']=metric;g['group']=g.index;rows.append(g.reset_index(drop=True))
    return pd.concat(rows,ignore_index=True)


def disparities(table,county,group,path,allow_incarceration):
    metrics=['dismissal','incarceration'] if allow_incarceration else ['dismissal']
    fig,axes=plt.subplots(1,len(metrics),figsize=(7*len(metrics),6),squeeze=False)
    for ax,metric in zip(axes[0],metrics):
        a=table[(table.metric==metric)&~table.suppressed].sort_values('rate_pct')
        color=OUTCOME_COLORS['Dismissal'] if metric=='dismissal' else BLUE
        ax.barh(a.group,a.rate_pct,color=color)
        for i,row in enumerate(a.itertuples()):ax.text(row.rate_pct+.8,i,f'{row.rate_pct:.1f}% (n={row.n:,})',va='center',fontsize=10)
        ax.set(xlim=(0,125),xlabel='% of '+('disposed case units' if metric=='dismissal' else 'conviction-evidence units'),title=metric.capitalize())
        ax.grid(axis='y',visible=False);ax.grid(axis='x')
    fig.suptitle(county+': recorded rates by '+group,x=.01,ha='left',weight='bold')
    finish(fig,path,'Groups below 30 eligible cases suppressed. Missing and explicit Unknown remain separate. Rates are descriptive and do not control for case mix. See CSV for missing-sentence shares and rate ratios.')


def offense_only(cases,county,path):
    a=cases.assign(event=cases.outcome.eq('Dismissal')).groupby(['charge','race']).event.agg(n='size',events='sum')
    a=a[a.n.ge(MIN_CELL)].copy();a['rate_pct']=100*a.events/a.n
    white=a.reset_index().query('race=="White"').set_index('charge').rate_pct
    a['white_pct']=a.index.get_level_values('charge').map(white)
    a['ratio_vs_white']=a.rate_pct/a.white_pct.replace(0,np.nan)
    compare=a.reset_index().query('race=="Black"').dropna(subset=['white_pct']).nlargest(6,'n').copy()
    if compare.empty:
        unavailable(county+': offense-only supplementary comparison','No Black/White comparison has 30 cases in both cells.',path)
    else:
        labels=[textwrap.fill(x,45) for x in compare.charge]
        fig,ax=plt.subplots(figsize=(13,8));y=np.arange(len(compare));w=.36
        ax.barh(y-w/2,compare.rate_pct,w,color=BLUE,label='Black');ax.barh(y+w/2,compare.white_pct,w,color='#eda100',label='White')
        ax.set(yticks=y,yticklabels=labels,xlim=(0,100),xlabel='% of disposed case units dismissed',title=county+': dismissal within the same representative charge')
        ax.legend(loc='upper left',bbox_to_anchor=(1.01,1));ax.grid(axis='y',visible=False);ax.grid(axis='x')
        finish(fig,path,'Supplementary only: no prior-record adjustment. Both race cells have at least 30 cases. Six largest eligible Black denominators shown; charge code and description form the comparison cell.')
    return a
