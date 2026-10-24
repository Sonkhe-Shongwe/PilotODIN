"""Deterministic, auditable ML engine. No language model is used for statistics."""
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (ExtraTreesClassifier, ExtraTreesRegressor,
                              GradientBoostingClassifier, GradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error, precision_score,
                             r2_score, recall_score, roc_auc_score)
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit, GroupKFold, GroupShuffleSplit, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

SEED = 42
CLASS_MODELS = ["logistic_regression", "decision_tree", "random_forest", "extra_trees", "gradient_boosting"]
REG_MODELS = ["linear_regression", "ridge", "decision_tree", "random_forest", "gradient_boosting"]
LABELS = {
    "logistic_regression": "Logistic Regression", "linear_regression": "Linear Regression",
    "ridge": "Ridge Regression", "decision_tree": "Decision Tree",
    "random_forest": "Random Forest", "extra_trees": "Extra Trees",
    "gradient_boosting": "Gradient Boosting",
}
LEAK_TERMS = ("diagnosis", "final_result", "outcome_after", "post_outcome", "target_encoded", "approved_after")


def native(value: Any) -> Any:
    if value is None: return None
    if isinstance(value, dict): return {str(k): native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)): return [native(x) for x in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, (pd.Timestamp,)): return value.isoformat()
    try:
        if pd.isna(value): return None
    except (ValueError, TypeError): pass
    return value


def read_data(path: str, ext: str) -> pd.DataFrame:
    if ext == ".csv":
        import re
        try:
            header=pd.read_csv(path,encoding="utf-8-sig",nrows=0)
            encoding="utf-8-sig"
        except UnicodeDecodeError:
            header=pd.read_csv(path,encoding="cp1252",nrows=0)
            encoding="cp1252"
        safe_types={c:str for c in header.columns if re.sub(r"[\s_-]+","",str(c)).lower().endswith(("id","key","code","postcode","zipcode","phone"))}
        df=pd.read_csv(path,encoding=encoding,dtype=safe_types,low_memory=False)
    elif ext == ".xlsx":
        df = pd.read_excel(path, engine="openpyxl", sheet_name=0)
    else: raise ValueError("Only CSV and XLSX files are supported")
    if df.empty or df.shape[1] < 2:
        raise ValueError("Upload a dataset with at least one row and two columns")
    if len(df) > 100000 or len(df.columns) > 100 or df.shape[0]*df.shape[1]>6000000:
        raise ValueError("Current guardrail: 100,000 rows, 100 columns and 6 million cells maximum")
    if not df.columns.is_unique:
        raise ValueError("Column names must be unique")
    df.columns = [str(c).strip() for c in df.columns]
    if any(not c for c in df.columns) or len(set(df.columns)) != len(df.columns):
        raise ValueError("Dataset has empty or duplicate column names")
    return df


def inferred_kind(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series): return "categorical"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    return "categorical"


def profile(df: pd.DataFrame, filename: str) -> dict:
    cols = []
    warnings = []
    for col in df.columns:
        s = df[col]
        kind = inferred_kind(s)
        nunique = int(s.nunique(dropna=True))
        missing = int(s.isna().sum())
        identifier = (nunique >= max(10, int(len(df)*.98)) and (col.lower().endswith(("id", "key", "number", "code")) or kind == "categorical"))
        leakage = any(term in col.lower().replace(" ", "_") for term in LEAK_TERMS)
        if identifier: warnings.append(f"{col}: possible identifier or high-cardinality field; review before training.")
        if leakage: warnings.append(f"{col}: name suggests possible target leakage. Verify when it becomes available.")
        cols.append({"name": col, "kind": kind, "missing": missing, "missing_pct": round(missing/len(df)*100, 1),
                     "unique": nunique, "identifier_risk": bool(identifier), "leakage_risk": bool(leakage),
                     "sample_values": [native(v) for v in s.dropna().unique()[:5]]})
    candidates = []
    keywords = ("target", "label", "outcome", "price", "churn", "survived", "status", "heartdisease", "risk", "sales", "revenue", "promoted")
    for c in cols:
        if any(k in c["name"].lower().replace(" ", "") for k in keywords):
            candidates.append(c["name"])
    suggestions = ["Review the target variable and the moment each feature becomes available.",
                   "Confirm whether the data contains repeated individuals or time-ordered observations."]
    if df.isna().any().any(): suggestions.append("Missing predictor values can be imputed within cross-validation pipelines.")
    if int(df.duplicated().sum()): suggestions.append("Duplicate rows detected; verify whether repeated records represent real events.")
    return {"filename": filename, "rows": len(df), "columns_count": len(df.columns), "missing_cells": int(df.isna().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()), "columns": cols, "preview": native(df.head(7).to_dict(orient="records")),
            "target_candidates": candidates[:5], "warnings": warnings[:30],
            "summary": (f"{filename} contains {len(df):,} rows and {len(df.columns)} columns. "
                        f"There are {int(df.isna().sum().sum()):,} missing cells and {int(df.duplicated().sum())} exact duplicate rows. "
                        "Column names alone cannot establish the dataset's subject or a valid prediction target."),
            "guidance": suggestions, "summary_source": "Deterministic profile; LLM interpretation is planned but not connected."}


def infer_task(series: pd.Series) -> str:
    vals = series.dropna()
    unique = vals.nunique()
    if unique == 2: return "classification"
    if unique < 2: raise ValueError("Target must have at least two distinct observed values")
    if pd.api.types.is_numeric_dtype(vals): return "regression"
    if 3 <= unique <= min(20, max(3, len(vals)//5)):
        return "classification"
    raise ValueError("This text target has too many distinct classes for supervised classification. Review its meaning or encoding.")


def preparation(df: pd.DataFrame, target: str) -> dict:
    if target not in df.columns: raise ValueError("Target column not found")
    task = infer_task(df[target])
    predictors = [x for x in df.columns if x != target]
    recommendations = []
    for name in predictors:
        s = df[name]
        reasons = []
        if s.isna().all(): reasons.append("all values missing")
        if s.nunique(dropna=True) <= 1: reasons.append("constant or empty column")
        if any(k in name.lower().replace(" ", "_") for k in LEAK_TERMS): reasons.append("possible outcome leakage")
        if name.lower().endswith(("id", "key")) and s.nunique() >= len(df)*.9: reasons.append("likely identifier")
        if reasons:
            recommendations.append({"column":name,"reason":"; ".join(reasons),"requires_review":True})
    return {"task": task, "target":target,"available_features": predictors, "recommend_exclude": recommendations,
            "missing_targets": int(df[target].isna().sum()), "transformations": ["Numeric predictors: median imputation", "Categorical predictors: mode imputation, then one-hot encoding", "Learned transformations fitted within each training fold"],
            "warnings": ["Target selection, feature timing and grouped/temporal structure require human judgement.",
                         "The MVP uses random splitting. Do not train temporal/grouped records without appropriate validation."]}


def make_estimator(task: str, key: str):
    if task == "classification":
        mapping = {
            "logistic_regression": LogisticRegression(max_iter=1200, random_state=SEED),
            "decision_tree": DecisionTreeClassifier(max_depth=9, random_state=SEED),
            "random_forest": RandomForestClassifier(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "extra_trees": ExtraTreesClassifier(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "gradient_boosting": GradientBoostingClassifier(random_state=SEED),
        }
    else:
        mapping = {
            "linear_regression": LinearRegression(),
            "ridge": Ridge(alpha=1),
            "decision_tree": DecisionTreeRegressor(max_depth=9, random_state=SEED),
            "random_forest": RandomForestRegressor(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "gradient_boosting": GradientBoostingRegressor(random_state=SEED),
        }
    if key not in mapping: raise ValueError(f"Invalid {task} model: {key}")
    return mapping[key]


def make_pipeline(X: pd.DataFrame, task: str, model: str) -> Pipeline:
    numeric = [c for c in X if inferred_kind(X[c]) == "numeric"]
    categorical = [c for c in X if c not in numeric]
    # Keep missing-only columns stable across folds; let imputers use safe constants.
    num_pipe = Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True))])
    if model in ("logistic_regression", "linear_regression", "ridge"):
        num_pipe.steps.append(("scaler", StandardScaler()))
    cat_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
                         ("encoder", OneHotEncoder(handle_unknown="infrequent_if_exist", max_categories=25))])
    ct = ColumnTransformer([("numeric",num_pipe,numeric),("categorical",cat_pipe,categorical)], sparse_threshold=0)
    return Pipeline([("preprocessor", ct), ("model", make_estimator(task, model))])


def validate_config(df: pd.DataFrame, target: str, excluded: list[str], models: list[str], task: str) -> tuple[pd.DataFrame, pd.Series, str]:
    if target not in df.columns: raise ValueError("Target not found")
    actual_task = infer_task(df[target])
    if task != actual_task: raise ValueError(f"Selected target requires {actual_task}; requested {task}.")
    if len(models) < 1 or len(models) > 5 or len(set(models)) != len(models):
        raise ValueError("Choose between 1 and 5 different models")
    if any(m not in (CLASS_MODELS if task=="classification" else REG_MODELS) for m in models):
        raise ValueError("One or more models are incompatible with this task")
    if target in excluded or any(c not in df.columns for c in excluded):
        raise ValueError("Invalid excluded features")
    X = df.drop(columns=[target]+excluded)
    X = X.loc[:, X.nunique(dropna=True) > 0]
    if not len(X.columns): raise ValueError("No usable predictors remain")
    valid = df[target].notna()
    X = X.loc[valid].copy()
    y = df.loc[valid, target].copy()
    if len(y) < 30: raise ValueError("At least 30 labelled rows are required for the local MVP")
    if task == "classification" and int(y.value_counts().min()) < 6:
        raise ValueError("Classification requires at least 6 cases in every class for stable splitting and cross-validation")
    if task == "regression":
        y = pd.to_numeric(y, errors="coerce")
        if y.isna().any() or not np.isfinite(y).all(): raise ValueError("Regression target must contain finite numeric values")
    return X, y, actual_task


def model_report(task: str, true: pd.Series, pred: np.ndarray, prob: np.ndarray | None = None) -> dict:
    if task == "regression":
        return {"mae":round(float(mean_absolute_error(true,pred)),5),
                "rmse":round(float(np.sqrt(mean_squared_error(true,pred))),5),
                "r2":round(float(r2_score(true,pred)),5)}
    labels=list(dict.fromkeys([native(x) for x in pd.Series(true).tolist()+pd.Series(pred).tolist()]))
    labels=sorted(labels,key=lambda x:str(x))
    out = {"accuracy":round(float(accuracy_score(true,pred)),5),
           "f1_macro":round(float(f1_score(true,pred,average="macro",zero_division=0)),5),
           "precision_macro":round(float(precision_score(true,pred,average="macro",zero_division=0)),5),
           "recall_macro":round(float(recall_score(true,pred,average="macro",zero_division=0)),5),
           "confusion_matrix":native(confusion_matrix(true,pred,labels=labels).tolist()),
           "class_labels":labels,"class_report":[{"label":native(lab),
                "precision":round(float(precision_score(true,pred,labels=[lab],average='macro',zero_division=0)),5),
                "recall":round(float(recall_score(true,pred,labels=[lab],average='macro',zero_division=0)),5),
                "f1":round(float(f1_score(true,pred,labels=[lab],average='macro',zero_division=0)),5),
                "support":int((pd.Series(true)==lab).sum())} for lab in labels]}
    if prob is not None:
        try: out["roc_auc"] = round(float(roc_auc_score(true, prob)),5)
        except ValueError: pass
    return out


def reliability_report(development:dict, final:dict, selected_model:str)->dict:
    """Conservative assessment: no false accuracy claims for regression."""
    issues=[]
    task=development['task']
    score=next((m.get('cv_metric') for m in development['models'] if m['key']==selected_model),None)
    baseline=development['baseline_cv']
    if score is not None and ((score>=baseline if task=='regression' else score<=baseline)):
        issues.append('The model did not beat the simple baseline during cross-validation.')
    if development['test_rows']<30:
        issues.append(f"Only {development['test_rows']} held-out observations; evaluation is unstable.")
    if task=='regression' and final.get('r2',0)<0:
        issues.append('Negative R²: worse than a constant-mean predictor on the held-out test set.')
    if task=='classification' and final.get('f1_macro',0)<.5:
        issues.append('Macro F1 is below 50%; investigate per-class performance.')
    score_sd=next((m.get('cv_std') for m in development['models'] if m['key']==selected_model),0) or 0
    if score is not None and score_sd > .5*max(abs(score),.01):
        issues.append('Performance varied sharply across validation folds.')
    return {'level':'warning' if issues else 'review','issues':issues,
            'message':'Not reliable for real decisions' if issues else 'Promising preliminary result; validate independently before deployment.'}


def run_training(df: pd.DataFrame, target: str, excluded: list[str], models: list[str], task: str,
                 split_strategy:str='random', split_column:str|None=None):
    X, y, task = validate_config(df, target, excluded, models, task)
    if split_strategy not in ('random','time','group'):
        raise ValueError('Invalid split strategy')
    if split_strategy != 'random' and (not split_column or split_column not in df):
        raise ValueError('Group or time column is required for this split')
    if split_strategy != 'random' and split_column == target:
        raise ValueError('Target cannot also be a split column')
    if split_strategy != 'random' and split_column in X:
        X=X.drop(columns=[split_column])
    if X.empty or not X.shape[1]:raise ValueError('No predictor fields after split-column exclusion')
    cv_groups=None
    if split_strategy=='group':
        groups=df.loc[X.index,split_column].fillna('(Missing group)').astype(str)
        if groups.nunique()<6:raise ValueError('Group splitting requires at least 6 distinct groups')
        train_idx,test_idx=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=SEED).split(X,y,groups))
        X_train,X_test=X.iloc[train_idx],X.iloc[test_idx]
        y_train,y_test=y.iloc[train_idx],y.iloc[test_idx]
        cv_groups=groups.iloc[train_idx]
        folds=min(5,cv_groups.nunique())
        cv=GroupKFold(n_splits=folds)
        if task=='classification' and y_train.nunique()!=y.nunique():
            raise ValueError('Group split removed a target class from training; choose different groups or collect more data')
    elif split_strategy=='time':
        raw=df.loc[X.index,split_column]
        if pd.api.types.is_numeric_dtype(raw):times=pd.to_numeric(raw,errors='coerce')
        else:
            times=pd.to_datetime(raw,errors='coerce',dayfirst=True,format='mixed')
        if times.isna().any():raise ValueError('Time split contains unparseable or missing dates; correct these before training')
        order=np.argsort(times.to_numpy(),kind='stable')
        cut=int(len(y)*.8)
        if cut<20 or len(y)-cut<5:raise ValueError('Time split requires at least 20 train and 5 test cases')
        X_train,X_test=X.iloc[order[:cut]],X.iloc[order[cut:]]
        y_train,y_test=y.iloc[order[:cut]],y.iloc[order[cut:]]
        folds=3 if len(y_train)>=36 else 2
        cv=TimeSeriesSplit(n_splits=folds)
        if task=='classification' and y_train.nunique()!=y.nunique():
            raise ValueError('Time split has a target class absent from training')
    else:
        stratify=y if task=='classification' else None
        X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=.2,random_state=SEED,stratify=stratify)
        min_class=int(y_train.value_counts().min()) if task=='classification' else 5
        folds=min(5,min_class) if task=='classification' else 5
        cv=StratifiedKFold(n_splits=folds,shuffle=True,random_state=SEED) if task=='classification' else KFold(n_splits=folds,shuffle=True,random_state=SEED)
    score='f1_macro' if task=='classification' else 'neg_mean_absolute_error'
    baseline=DummyClassifier(strategy='most_frequent') if task=='classification' else DummyRegressor(strategy='median')
    base_pipe=Pipeline([('preprocessor',make_pipeline(X_train,task,models[0]).named_steps['preprocessor']),('model',baseline)])
    cv_kwargs={'groups':cv_groups} if cv_groups is not None else {}
    # Group-aware CV is only valid when no group appears in both development folds.
    base_scores=cross_val_score(base_pipe,X_train,y_train,cv=cv,scoring=score,n_jobs=1,error_score='raise',**cv_kwargs)
    reports,pipelines=[],{}
    for key in models:
        pipe=make_pipeline(X_train,task,key)
        try:
            scores=cross_val_score(pipe,X_train,y_train,cv=cv,scoring=score,n_jobs=1,error_score='raise',**cv_kwargs)
            pipe.fit(X_train,y_train)
            value=float(scores.mean())*(1 if task=='classification' else -1)
            reports.append({'key':key,'name':LABELS[key],'cv_metric':round(value,5),
                            'cv_std':round(float(scores.std()),5),'status':'ready'})
            pipelines[key]=pipe
        except Exception as ex:
            reports.append({'key':key,'name':LABELS[key],'status':'failed','error':str(ex)[:230]})
    if not pipelines:raise ValueError('Every model failed; review data type, validation strategy and feature configuration')
    baseline_cv=round(float(base_scores.mean())*(1 if task=='classification' else -1),5)
    wins=[m for m in reports if m['status']=='ready' and
          (m['cv_metric']<baseline_cv if task=='regression' else m['cv_metric']>baseline_cv)]
    return {'task':task,'target':target,'features':list(X.columns),'excluded_features':excluded,
            'split_strategy':split_strategy,'split_column':split_column,
            'labelled_rows':len(y),'train_rows':len(X_train),'test_rows':len(X_test),'folds':folds,
            'primary_metric':'F1 macro (higher is better)' if task=='classification' else 'MAE (lower is better)',
            'baseline_cv':baseline_cv,'beats_baseline':bool(wins),
            'models':reports,'input_schema':input_schema(X_train),
            'warning':'Development folds determine selection; held-out test is used once after model selection. '+
                      ('No candidate beat the baseline: predictions may be unreliable.' if not wins else '')},pipelines,X_test,y_test


def input_schema(X: pd.DataFrame) -> list[dict]:
    fields = []
    for c in X:
        s = X[c]
        if inferred_kind(s)=="numeric":
            fields.append({"name":c,"kind":"number","min":native(s.min()),"max":native(s.max()),"required":False,"domain": _prediction_domain(c)})
        else:
            categories = [str(x) for x in s.dropna().unique()[:40]]
            fields.append({"name":c,"kind":"select" if s.nunique(dropna=True)<=30 else "text","options":categories if len(categories)<=30 else [],"required":False})
    return fields


def _prediction_domain(name: str) -> dict | None:
    """Strict bounds only for explicitly recognized clock and count fields."""
    normalized = ''.join(c for c in name.lower() if c.isalnum())
    if normalized == "hourofday":
        return {"min": 0, "max": 23, "integer": True}
    if normalized == "transactionsinlasthour":
        return {"min": 0, "integer": True}
    return None


def _validate_prediction_domain(name: str, value: float, domain: dict | None) -> None:
    if not domain:
        return
    if domain.get("integer") and not value.is_integer():
        raise ValueError(f"{name} must be a whole number")
    if "min" in domain and value < domain["min"]:
        raise ValueError(f"{name} must be at least {domain['min']}")
    if "max" in domain and value > domain["max"]:
        raise ValueError(f"{name} must not exceed {domain['max']}")


def predict_one(pipe: Pipeline, schema: list[dict], values: dict) -> dict:
    required_names = {f["name"] for f in schema}
    if set(values)-required_names: raise ValueError("Unknown prediction features submitted")
    row = {}
    input_warnings = []
    for f in schema:
        val = values.get(f["name"])
        if val in (None, ""):
            row[f["name"]] = np.nan
        elif f["kind"]=="number":
            try:
                num = float(val)
                if not math.isfinite(num): raise ValueError()
                _validate_prediction_domain(f["name"], num, f.get("domain") or _prediction_domain(f["name"]))
                row[f["name"]] = num
                if f.get('min') is not None and num < float(f['min']):
                    input_warnings.append(f"{f['name']} is below the observed training range ({f['min']}–{f.get('max')}).")
                if f.get('max') is not None and num > float(f['max']):
                    input_warnings.append(f"{f['name']} is above the observed training range ({f.get('min')}–{f['max']}).")
            except (TypeError,OverflowError): raise ValueError(f"{f['name']} must be a finite number")
            except ValueError as exc:
                if str(exc).startswith(f["name"]):
                    raise
                raise ValueError(f"{f['name']} must be a finite number") from exc
        else:
            row[f["name"]] = str(val)
    pred = pipe.predict(pd.DataFrame([row]))[0]
    result = {"prediction":native(pred),"model":pipe.named_steps["model"].__class__.__name__,"input_warnings":input_warnings}
    if hasattr(pipe,"predict_proba"):
        proba=pipe.predict_proba(pd.DataFrame([row]))[0]
        labels=pipe.named_steps["model"].classes_
        result["probabilities"] = [{"class":native(label),"probability":round(float(v),5)} for label,v in zip(labels,proba)]
    return result
