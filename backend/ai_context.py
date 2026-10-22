"""Redacted analytical facts shared with opt-in AI providers.

No row records, sample values, category labels, file paths or API keys.
"""
from __future__ import annotations

import math
import pandas as pd

try:
    from . import analytics, quality, storage
except ImportError:
    import analytics, quality, storage

TASKS={
 'overview':'Explain the main data quality or analysis priorities and suggest next investigations.',
 'understand':'Interpret dataset structure and warn about assumptions or unknown domain meaning.',
 'quality':'Prioritize quality issues, risks to conclusions, and safe review steps. Never apply corrections.',
 'explore':'Suggest meaningful variables, chart types and hypotheses to test, based on computed statistics.',
 'prepare':'Assess feature risks and suggest how to validate useful predictors without target leakage.',
 'model':'Recommend an evidence-based model comparison and validation approach, without claiming to have run experiments.',
 'evaluate':'Interpret saved model evaluation metrics and limitations; do not invent scores.',
 'predict':'Explain the selected model prediction and its uncertainty, based on available metadata, not the withheld input row.',
 'assistant':'Answer the provided question based on verified local facts.'
}


def _finite(v):
    try:
        f=float(v)
        return round(f,4) if math.isfinite(f) else None
    except (ValueError,TypeError,OverflowError):return None


def build(project_id:str,task:str,question:str='',target:str|None=None,experiment_id:str|None=None,prediction:dict|None=None)->dict:
    if task not in TASKS:raise ValueError('Unsupported AI analysis context')
    df,version=quality.current_data(project_id)
    issue_data=quality.snapshot(project_id)
    overview=analytics.describe(df,version)
    result={'dataset_version':version,'row_count':len(df),'column_count':len(df.columns),
            'missing_cells':overview['missing_cells'],'duplicate_rows':overview['exact_duplicates'],
            'columns':[], 'quality_findings':[], 'computed_patterns':[]}
    # Column NAMES and numeric aggregates only; deliberately omit records, samples and category strings.
    for c in overview['columns'][:50]:
        out={'name':str(c['name'])[:100],'kind':c['kind'],'missing_count':c['missing'],
             'missing_pct':c['missing_pct'],'unique_count':c['unique']}
        for k in ('mean','median','min','max','std'):
            if k in c:out[k]=_finite(c[k])
        result['columns'].append(out)
    for item in issue_data.get('issues',[])[:25]:
        result['quality_findings'].append({'kind':item['kind'],'column':str(item.get('column') or '')[:100],
                                           'affected_rows':item['affected_rows'],
                                           'decision':item['decision'],'severity':item['severity']})
    for c in df.columns[:35]:
        s=df[c]
        if not pd.api.types.is_numeric_dtype(s):continue
        vals=pd.to_numeric(s,errors='coerce').replace([float('inf'),-float('inf')],float('nan')).dropna()
        if len(vals)<5:continue
        mean=_finite(vals.mean());median=_finite(vals.median())
        if mean is None or median is None:continue
        if mean!=median and abs(mean-median)>max(abs(median)*.4, 1.0):
            result['computed_patterns'].append({'column':str(c)[:100],'mean':mean,'median':median,
              'observation':'Large mean/median difference; investigate skew or outliers, not proof of an error'})
    if target and target in df.columns:
        result['target']=str(target)[:100]
        result['feature_screening']=analytics.recommend_features(df,target,version)['features'][:40]
    if experiment_id:
        exp=storage.get_experiment(experiment_id)
        if exp and exp['project_id']==project_id:
            result['experiment']={'target':exp['config'].get('target'),'task':exp['config'].get('task'),
               'dataset_version':exp['config'].get('quality_version'),'stale':exp['config'].get('quality_version')!=version,
               'selected_model':exp.get('selected_model'),'metrics':exp.get('final_results'),
               'comparison':[{k:m.get(k) for k in ('key','status','cv_metric','cv_std')}
                            for m in (exp.get('results') or {}).get('models',[])][:5]}
    if prediction and experiment_id and 'experiment' in result:
        # Only prediction output; user-entered input feature values are excluded.
        probabilities=[]
        for item in (prediction.get('probabilities') or [])[:8]:
            if isinstance(item,dict):
                v=_finite(item.get('probability'))
                if v is not None and 0<=v<=1:
                    probabilities.append({'class':str(item.get('class',''))[:60],'probability':v})
        result['prediction']={'target':result['experiment']['target'],
           'outcome':str(prediction.get('prediction',''))[:80],
           'probabilities':probabilities}
    return result



def local_advice(ctx:dict,task:str)->str:
    """Grounded, substantive non-LLM fallback covering every workspace."""
    issues=ctx['quality_findings']
    categories={}
    for issue in issues:
        k=issue['kind'];categories.setdefault(k,0);categories[k]+=issue['affected_rows']
    cols=ctx['column_count'];rows=ctx['row_count']
    base=f"The current dataset contains {rows:,} rows and {cols} columns (working version {ctx['dataset_version']})."
    if task=='quality':
        if not issues:return base+' No automatic quality issues were detected. This does not prove that the dataset is error-free.'
        tips={'spelling':'Confirm whether differently spelled labels describe the same category before merging.',
              'case_variant':'Review category case differences before harmonizing them.',
              'whitespace':'Check formatting corrections and preserve your undo decisions.',
              'missing':'Investigate missingness before imputing or discarding observations.',
              'outliers':'Compare means with medians and inspect extreme values; do not delete them automatically.',
              'ambiguous_dates':'Confirm the day/month convention before parsing dates.',
              'identifier':'Exclude unique identifiers from candidate predictors if they cannot generalize.',
              'duplicates':'Review whether repeated observations are legitimate before deleting.'}
        ranked=sorted(categories.items(),key=lambda p:-p[1])[:5]
        lines=[f"{k}: {n:,} affected records. {tips.get(k,'Review source context before changing values')}" for k,n in ranked]
        return base+' Key investigations: '+' '.join(lines)+' Quality changes require approved actions in Data Quality.'
    if task=='explore':
        patterns=ctx['computed_patterns']
        if patterns:
            sample=patterns[0]
            return (base+f" {sample['column']} has mean {sample['mean']:,.2f} versus median {sample['median']:,.2f}. "
                   'Investigate the distribution and potential extreme values; this alone does not prove an error. '
                   'Try grouped median charts or a box plot in Explore, and check unresolved category standardization.')
        return base+' Compare numeric distributions using histograms or box plots, and categorical frequency using bar charts. Avoid treating identifiers as meaningful group labels.'
    if task=='prepare':
        hints=ctx.get('feature_screening',[])
        risky=[x for x in hints if x['risk']!='low']
        if risky:
            return base+' Review these potential predictors: '+ '; '.join(f"{x['column']} ({', '.join(x['reasons'])})" for x in risky[:5])+'. Confirm each feature is available at the time of prediction; validate usefulness using training-fold cross-validation.'
        return base+' No major structural predictors were flagged. Confirm leakage risk, target timing, and validation strategy before training.'
    if task=='model':
        return base+' Set a clear target and compare a transparent baseline against tree-based models using development-fold cross-validation. Avoid random splits for time-ordered or grouped observations. Select features using training data only.'
    if task=='evaluate':
        experiment=ctx.get('experiment')
        if not experiment:return base+' No experiment was provided. Train several baselines, compare cross-validation scores, then evaluate only the chosen model on held-out test data.'
        return base+f" Selected model: {experiment.get('selected_model') or 'not selected'}. " + ('This experiment was trained on an older dataset version; retrain it.' if experiment.get('stale') else 'Review cross-validation variability, class balance and held-out performance before trusting a result.')
    if task=='predict':
        predicted=ctx.get('prediction')
        if predicted:return f"Prediction for target {predicted['target']}: {predicted['outcome']}. This is a model estimate, not a verified fact. Review the training data, model metrics and potential distribution shift before acting."
        return 'Select a current trained model and generate a prediction to interpret its target and uncertainty.'
    if task=='understand':
        missing=ctx['missing_cells']
        return base+f" There are {missing:,} missing cells. Column names alone cannot determine the business context or establish a safe prediction target; review definitions and data provenance."
    return base+f" There are {ctx['missing_cells']:,} missing cells, {ctx['duplicate_rows']:,} exact duplicate rows and {len(issues)} detected quality findings. Investigate Data Quality and Explore before defining a prediction target."
