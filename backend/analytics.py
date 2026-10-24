"""Read-only, bounded exploratory analytics. All numbers are computed locally.

The workspace draws its plots from these aggregations instead of receiving a
whole data frame. No claims about causation or prediction are made here.
"""
from __future__ import annotations

import math
import re
import numpy as np
import pandas as pd

try:
    from . import engine
except ImportError:
    import engine


def describe(df: pd.DataFrame, version: int) -> dict:
    cols=[]
    for name in df:
        s=df[name]
        numeric=pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        info={"name":name,"kind":"numeric" if numeric else "categorical",
              "unique":int(s.nunique(dropna=True)),"missing":int(s.isna().sum()),
              "missing_pct":round(float(s.isna().mean())*100,2)}
        if numeric:
            v=pd.to_numeric(s,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            if not v.empty:
                info.update({"min":engine.native(v.min()),"max":engine.native(v.max()),
                             "mean":engine.native(v.mean()),"median":engine.native(v.median())})
        cols.append(info)
    return {"version":version,"rows":len(df),"columns":cols,
            "missing_cells":int(df.isna().sum().sum()),
            "exact_duplicates":int(df.duplicated().sum()),"source":"local_computed"}


def _column(df:pd.DataFrame,name:str):
    if name not in df.columns:
        raise ValueError(f"Column {name!r} not found")
    return df[name]


def chart(df:pd.DataFrame,version:int, x:str, y:str|None=None, kind:str='auto', aggregation:str='mean', bins:int=16)->dict:
    xs=_column(df,x)
    if y: _column(df,y)
    if kind=='auto':
        kind='scatter' if y and pd.api.types.is_numeric_dtype(xs) and pd.api.types.is_numeric_dtype(df[y]) else ('bar' if y or not pd.api.types.is_numeric_dtype(xs) else 'histogram')
    if kind not in ('bar','histogram','scatter','line','box'):
        raise ValueError('Supported charts: bar, histogram, scatter, line, box')
    if aggregation not in ('mean','sum','count','median'):
        raise ValueError('Unsupported aggregation')
    out={"version":version,"type":kind,"x":x,"y":y,"aggregation":aggregation,
         "sampled":False,"data":[],"note":"Descriptive relationships do not establish causation."}
    if kind=='histogram':
        numeric=pd.to_numeric(xs,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if numeric.empty: raise ValueError('Histogram requires numeric values')
        bins=max(4,min(int(bins),40))
        counts, edges=np.histogram(numeric.to_numpy(dtype=float),bins=bins)
        out['data']=[{'label':f'{edges[i]:,.2f}–{edges[i+1]:,.2f}', 'x':float((edges[i]+edges[i+1])/2),'start':float(edges[i]),'end':float(edges[i+1]),'value':int(c)} for i,c in enumerate(counts)]
        out['valid_observations']=int(numeric.size)
        out['excluded_observations']=int(len(xs)-numeric.size)
        out['note']='Frequency per interval. Missing or non-finite observations are excluded.'
    elif kind in ('scatter','line'):
        if not y: raise ValueError('Scatter and line charts need an Y column')
        view=df[[x,y]].copy()
        if kind=='scatter':
            view[x]=pd.to_numeric(view[x],errors='coerce')
            view[y]=pd.to_numeric(view[y],errors='coerce')
            view=view.replace([np.inf,-np.inf],np.nan).dropna()
            if view.empty: raise ValueError('Scatter requires two numeric columns')
            if len(view)>500: view=view.sample(n=500,random_state=42);out['sampled']=True
            out['data']=[{'x':float(a),'y':float(b)} for a,b in zip(view[x],view[y])]
        else:
            view[y]=pd.to_numeric(view[y],errors='coerce');view=view.dropna()
            if view.empty: raise ValueError('Line chart requires a numeric Y column')
            groups=view.groupby(x,dropna=False)[y].agg(aggregation if aggregation!='count' else 'count').reset_index()
            if len(groups)>80: groups=groups.iloc[np.linspace(0,len(groups)-1,80,dtype=int)];out['sampled']=True
            out['data']=[{'label':str(a),'value':float(b)} for a,b in zip(groups[x],groups[y])]
    elif kind=='box':
        s=pd.to_numeric(xs,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if s.empty: raise ValueError('Box summary needs numeric values')
        q1=float(s.quantile(.25));q3=float(s.quantile(.75));iqr=q3-q1
        low,high=q1-1.5*iqr,q3+1.5*iqr
        inliers=s[(s>=low)&(s<=high)]
        outliers=s[(s<low)|(s>high)].sort_values().to_numpy(dtype=float)
        out['data']=[{'label':x,'min':float(s.min()),'q1':q1,'median':float(s.median()),'q3':q3,'max':float(s.max()),
                      'whisker_low':float(inliers.min()) if not inliers.empty else float(s.min()),
                      'whisker_high':float(inliers.max()) if not inliers.empty else float(s.max()),
                      'outliers':[float(v) for v in outliers[:40]],'outliers_total':int(len(outliers))}]
        out['note']='Whiskers end at observed inliers within 1.5×IQR fences; marked outliers may still be valid.'
    else:
        if y:
            v=pd.to_numeric(df[y],errors='coerce')
            if aggregation!='count' and v.notna().sum()==0:raise ValueError('Y must be numeric for the chosen aggregation')
            grouped=pd.DataFrame({'category':xs.fillna('(Missing)').astype(str),'value':v}).groupby('category',dropna=False)['value'].agg(aggregation).sort_values(ascending=False)
            if aggregation=='count':
                out['note']=f'Count of non-missing {y} observations by {x}. Missing values in the selected measure are excluded.'
        else:
            grouped=xs.fillna('(Missing)').astype(str).value_counts()
            out['note']=f'Record count by {x}; no numeric measure is required.'
        out['truncated']=len(grouped)>30
        out['data']=[{'label':str(k),'value':float(v)} for k,v in grouped.head(30).items() if pd.notna(v)]
    return out


def correlation(df: pd.DataFrame, version: int, method: str = 'pearson') -> dict:
    """Bounded pairwise-complete correlation matrix, without causal inference."""
    if method not in ('pearson','spearman'):
        raise ValueError('Choose Pearson or Spearman correlation')
    fields=[name for name in df if pd.api.types.is_numeric_dtype(df[name])
            and not pd.api.types.is_bool_dtype(df[name])
            and not name.lower().endswith(('id','key','code','number'))][:14]
    if len(fields)<2:
        return {'version':version,'method':method,'columns':fields,'cells':[],
                'note':'At least two non-identifier numeric fields are needed.'}
    view=df[fields].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    cells=[]
    for y in fields:
        for x in fields:
            if x==y:
                clean=view[x].dropna()
                n=int(len(clean))
                score=1.0 if n>=3 and clean.nunique()>=2 else None
                cells.append({'x':x,'y':y,'r':score,'n':n})
                continue
            clean=view[[x,y]].dropna()
            n=int(len(clean))
            if n<3 or clean[x].nunique()<2 or clean[y].nunique()<2:
                score=None
            else:
                v=clean[x].corr(clean[y],method=method)
                score=round(float(v),5) if pd.notna(v) and np.isfinite(v) else None
            cells.append({'x':x,'y':y,'r':score,'n':n})
    return {'version':version,'method':method,'columns':fields,'cells':cells,
            'note':'Pairwise complete cases only. Blank cells have fewer than 3 pairs or no variation. Correlation does not establish causation.'}


def insights(df:pd.DataFrame,version:int)->dict:
    facts=[]
    n=len(df)
    if n==0:return {'version':version,'findings':[]}
    for c in df:
        s=df[c]
        missing=int(s.isna().sum())
        if missing:
            facts.append({'category':'missing','column':c,'title':f'{missing:,} missing values in {c}',
                          'detail':f'{missing/n:.1%} of rows are missing. Inspect the pattern before imputing.','priority':2})
        if s.nunique(dropna=True)<=1:
            facts.append({'category':'features','column':c,'title':f'{c} has no variation',
                          'detail':'This column cannot distinguish different records. Consider excluding it from a prediction model.','priority':2})
        if re.search(r'(?:id|key|code)$',c,re.I) and s.nunique(dropna=True) >= .9*n:
            facts.append({'category':'features','column':c,'title':f'{c} looks like an identifier',
                          'detail':'High uniqueness suggests a record identifier rather than a generalisable feature. Check its role before training.','priority':3})
        if pd.api.types.is_numeric_dtype(s):
            numeric=pd.to_numeric(s,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            if len(numeric)>=8:
                q1,q3=numeric.quantile([.25,.75]);iqr=q3-q1
                if iqr>0:
                    unusual=int(((numeric<q1-1.5*iqr)|(numeric>q3+1.5*iqr)).sum())
                    if unusual:
                        facts.append({'category':'distribution','column':c,'title':f'{unusual:,} unusual values in {c}',
                                      'detail':'Outside the 1.5×IQR fences. Unusual does not mean incorrect.','priority':1})
    duplicates=int(df.duplicated().sum())
    if duplicates:facts.append({'category':'duplicates','column':None,'title':f'{duplicates:,} exact duplicate rows','detail':'Review whether repeated observations are meaningful before deleting.','priority':2})
    facts.sort(key=lambda item:-item['priority'])
    return {'version':version,'findings':facts[:30], 'method':'deterministic_descriptive_rules'}


def recommend_features(df:pd.DataFrame,target:str,version:int)->dict:
    if target not in df: raise ValueError('Choose a target column')
    entries=[]
    for name in df:
        if name==target:continue
        s=df[name];reasons=[];risk='low'
        if s.nunique(dropna=True)<=1: reasons.append('Constant or entirely missing');risk='high'
        if re.search(r'(?:id|key|code|number)$',name,re.I) and s.nunique(dropna=True)>=.9*len(df):
            reasons.append('High-cardinality identifier candidate');risk='high'
        if any(k in name.lower().replace(' ','_') for k in engine.LEAK_TERMS):
            reasons.append('Potential post-outcome leakage');risk='high'
        if s.isna().mean()>.5:reasons.append('More than half its values are missing');risk='review' if risk=='low' else risk
        if s.dtype=='object' and s.nunique(dropna=True)>.7*len(df):
            reasons.append('High-cardinality text; potentially expensive to encode');risk='review' if risk=='low' else risk
        entries.append({'column':name,'risk':risk,'recommendation':'review exclusion' if risk=='high' else ('investigate' if risk=='review' else 'consider'),
                        'reasons':reasons or ['No obvious structural warning; usefulness must be validated'],
                        'missing_pct':round(float(s.isna().mean())*100,1)})
    return {'version':version,'target':target,'features':entries,
            'disclaimer':'These are screening hints, not validated feature importance. Confirm availability at prediction time and compare using training-only cross-validation.'}


def answer(df:pd.DataFrame,version:int,question:str)->dict:
    q=question.lower().strip()
    overview=describe(df,version)
    findings=insights(df,version)['findings']
    if not q or len(q)>350:raise ValueError('Enter a question of at most 350 characters')
    if any(w in q for w in ('missing','null','blank')):
        ranked=sorted(overview['columns'],key=lambda c:-c['missing'])
        relevant=[f"{c['name']}: {c['missing']:,} ({c['missing_pct']}%)" for c in ranked if c['missing']]
        response='Missing values by column: '+('; '.join(relevant[:12]) if relevant else 'none detected')+'.'
    elif any(w in q for w in ('duplicate','repeat')):
        response=f"The working dataset contains {overview['exact_duplicates']:,} exact duplicate rows. Repeated observations may still be valid."
    elif any(w in q for w in ('model','predict','feature','leak')):
        response='Model choice depends on your confirmed target and validation strategy. In Prepare, inspect identifier and leakage warnings, then compare models using development-set cross-validation. Keep the test set untouched until selection.'
    elif any(w in q for w in ('issue','quality','clean','problem','anomal','outlier')):
        response=f"The local analysis found {len(findings)} descriptive findings. "+('; '.join(f['title'] for f in findings[:4]) if findings else 'No descriptive warnings emerged')+'. Review recommendations in Data Quality before approving changes.'
    else:
        response=f"This working dataset has {overview['rows']:,} rows, {len(overview['columns'])} columns, {overview['missing_cells']:,} missing cells and {overview['exact_duplicates']:,} exact duplicate rows. Select Explore for variable-specific charts."
    return {'version':version,'answer':response,'source':'local_computed_rules',
            'limitations':'This is a deterministic local assistant, not an LLM; it does not infer business meaning or claim causality.'}


def recommended_charts(df:pd.DataFrame,version:int)->dict:
    """Rank data-dependent charts without treating identifiers as useful groups."""
    import re
    candidates=[]
    numeric=[c for c in df if pd.api.types.is_numeric_dtype(df[c]) and not re.search(r'(id|key|code|number)$',c,re.I)]
    category=[c for c in df if not pd.api.types.is_numeric_dtype(df[c]) and not re.search(r'(id|key|code|number)$',c,re.I) and 1<df[c].nunique(dropna=True)<=min(40,max(2,len(df)//2))]
    for c in category[:6]:
        metric=next((m for m in numeric if re.search(r'(sales|price|revenue|amount|profit|cost|qty|quantity|score)',m,re.I)),None)
        if metric is None:metric=numeric[0] if numeric else None
        candidates.append({'title':f"{'Median '+metric+' by ' if metric else 'Records by '}{c}",
                           'x':c,'y':metric,'kind':'bar','aggregation':'median' if metric else 'count',
                           'reason':'Uses a category rather than an identifier; median resists extreme observations.' if metric else 'Compares category frequencies.'})
    for c in numeric[:6]:
        values=pd.to_numeric(df[c],errors='coerce').dropna()
        if len(values)<5:continue
        mean=float(values.mean());median=float(values.median())
        if abs(mean-median)>max(abs(median)*.3,1):
            candidates.append({'title':f'Investigate extreme values in {c}','x':c,'y':None,
                               'kind':'box','aggregation':'median',
                               'reason':f'Mean {mean:,.2f} versus median {median:,.2f}; extreme values may distort the mean.'})
        candidates.append({'title':f'Distribution of {c}','x':c,'y':None,'kind':'histogram','aggregation':'count',
                           'reason':'Inspect numerical distribution and unusual observations.'})
    if len(numeric)>1:
        candidates.append({'title':f'{numeric[0]} versus {numeric[1]}','x':numeric[0],'y':numeric[1],
                           'kind':'scatter','aggregation':'mean','reason':'Inspect association; it does not establish causation.'})
    return {'version':version,'recommendations':candidates[:12]}


def investigate(df:pd.DataFrame, version:int, operation:str, column:str|None=None)->dict:
    """Allowlisted, read-only ODIN investigations. No arbitrary code or data mutation."""
    if operation=='overview':
        d=describe(df,version)
        return {'operation':operation,'version':version,'summary':{'rows':d['rows'],'missing_cells':d['missing_cells'],
                'exact_duplicates':d['exact_duplicates'],'columns_count':len(d['columns'])}}
    if operation=='recommend_charts':return recommended_charts(df,version)
    if operation=='quality_summary':
        data=insights(df,version)
        return {'operation':operation,'version':version,'findings':data['findings'][:15]}
    if operation=='numeric_distribution':
        if not column or column not in df:raise ValueError('Select an existing numeric column')
        series=pd.to_numeric(df[column],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if series.empty:raise ValueError('No numeric observations found')
        q1,q3=series.quantile([.25,.75]);lo,hi=q1-1.5*(q3-q1),q3+1.5*(q3-q1)
        count=int(((series<lo)|(series>hi)).sum())
        return {'operation':operation,'version':version,'column':column,'count':len(series),
                'min':float(series.min()),'max':float(series.max()),'mean':float(series.mean()),
                'median':float(series.median()),'q1':float(q1),'q3':float(q3),
                'outliers_by_iqr':count,'warning':'Statistical outliers are not necessarily data errors.'}
    raise ValueError('Unsupported investigation')



def missingness_diagnostics(df:pd.DataFrame, version:int, column:str)->dict:
    """Read-only missingness investigation; all values are computed on the working dataset.

    The detailed result stays on localhost. Cloud receives only bounded numerical
    summaries, never raw rows or category labels.
    """
    if column not in df:raise ValueError('Choose an existing column')
    s=df[column]
    mask=s.isna() | s.map(lambda v:isinstance(v,str) and not v.strip())
    total=len(df);missing=int(mask.sum())
    if not missing:raise ValueError('No missing entries remain in this column')
    findings={'operation':'missingness','version':version,'column':column,
              'total_rows':total,'missing_rows':missing,'missing_pct':round(100*missing/max(1,total),2),
              'row_numbers':[int(i)+1 for i in np.flatnonzero(mask.to_numpy())[:100]],
              'row_list_truncated':missing>100,'numeric_comparisons':[],
              'categorical_comparisons':[], 'suggested_treatments':[],
              'caution':'Observed patterns cannot establish MCAR, MAR or MNAR by themselves.'}
    for other in list(df.columns):
        if other==column:continue
        values=df[other]
        if pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
            numeric=pd.to_numeric(values,errors='coerce').replace([np.inf,-np.inf],np.nan)
            affected=numeric[mask].dropna();observed=numeric[~mask].dropna()
            if not affected.empty and not observed.empty:
                findings['numeric_comparisons'].append({'column':other,
                    'missing_group_count':int(len(affected)),'other_group_count':int(len(observed)),
                    'missing_group_median':float(affected.median()),
                    'other_group_median':float(observed.median()),
                    'missing_group_mean':float(affected.mean()),
                    'other_group_mean':float(observed.mean())})
        elif values.nunique(dropna=True)<=12 and values.nunique(dropna=True)>=2:
            # These grouped category labels are LOCAL ONLY and never included in cloud context.
            category=values.fillna('(Missing)').astype(str)
            if category.map(len).max()>50:continue
            grouped=pd.DataFrame({'value':category,'missing':mask}).groupby('value')['missing'].agg(['sum','count'])
            findings['categorical_comparisons'].append({'column':other,'groups':[
                {'label':str(label),'missing_count':int(row['sum']),'total_count':int(row['count']),
                 'missing_pct':round(100*int(row['sum'])/max(1,int(row['count'])),2)}
                for label,row in grouped.sort_values('count',ascending=False).head(12).iterrows()]})
        if len(findings['numeric_comparisons'])>=12 and len(findings['categorical_comparisons'])>=8:break
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        observed=pd.to_numeric(s[~mask],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if not observed.empty:
            median=float(observed.median())
            findings['suggested_treatments'].append({'id':'median','label':f'Fill with observed median ({median:,.2f})',
                'value':median,'requires_approval':True,
                'tradeoff':'Changes the observed distribution and may weaken relationships. Review grouped patterns first.'})
    findings['suggested_treatments'].extend([
      {'id':'retain','label':'Keep missing, with a modelling-time imputer','requires_approval':False,
       'tradeoff':'Keeps the original working data intact; fitted imputation must occur within training folds.'},
      {'id':'source','label':'Verify against the source records','requires_approval':False,
       'tradeoff':'Preferred when original records can resolve the missing values reliably.'}])
    return findings


def plan_investigation(df:pd.DataFrame,version:int,question:str,task:str='assistant')->dict|None:
    """Deterministic evidence-gathering planner; no user-supplied executable code."""
    lower=question.casefold()
    if not any(word in lower for word in ('missing','null','blank','imput','incomplete')):
        return None
    matching=[c for c in df.columns if c.casefold() in lower and df[c].isna().any()]
    if len(matching)!=1:
        available=[c for c in df.columns if df[c].isna().any()]
        if len(available)==1:matching=available
    if not matching:return None
    report=missingness_diagnostics(df,version,matching[0])
    # Send only bounded numerical facts for language-model interpretation.
    safe={'operation':'missingness','column':report['column'],'missing_rows':report['missing_rows'],
          'missing_pct':report['missing_pct'],'total_rows':report['total_rows'],
          'numeric_comparisons':report['numeric_comparisons'][:8],
          'categorical_group_counts':[{ 'column':group['column'],
              'groups':[{'missing_count':item['missing_count'],'total_count':item['total_count']}
                        for item in group['groups'][:8]]}
                        for group in report['categorical_comparisons'][:5]],
          'caution':report['caution']}
    return {'operation':'missingness','column':matching[0],'safe_context':safe,'local_report':report,
       'steps':['Inspect missing records','Compare numeric groups','Compare category-level missing rates','Review safe treatment options']}
