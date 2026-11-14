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
                              HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge, ElasticNet
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC, SVR
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error, precision_score,
                             r2_score, recall_score, roc_auc_score)
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit, GroupKFold, GroupShuffleSplit, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

SEED = 42
CLASS_MODELS = ["logistic_regression", "decision_tree", "random_forest", "extra_trees", "gradient_boosting", "hist_gradient_boosting", "knn", "svm", "naive_bayes"]
REG_MODELS = ["linear_regression", "ridge", "elastic_net", "decision_tree", "random_forest", "gradient_boosting", "hist_gradient_boosting", "knn", "svr"]
LABELS = {
    "logistic_regression": "Logistic Regression", "linear_regression": "Linear Regression",
    "ridge": "Ridge Regression", "decision_tree": "Decision Tree",
    "random_forest": "Random Forest", "extra_trees": "Extra Trees",
    "gradient_boosting": "Gradient Boosting",
    "hist_gradient_boosting": "Histogram Gradient Boosting", "knn": "K-Nearest Neighbours",
    "svm": "Support Vector Classifier", "svr": "Support Vector Regression",
    "naive_bayes": "Gaussian Naive Bayes", "elastic_net": "Elastic Net",
}
LEAK_TERMS = ("diagnosis", "final_result", "outcome_after", "post_outcome", "target_encoded", "approved_after")
PREPARE_CATEGORY_EXAMPLE_LIMIT = 5
PREPARE_CATEGORY_EXAMPLE_LENGTH = 80


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
    """Show the ACTUAL pipeline plan, including exclusions and risk provenance.

    The audit is deterministic and does not estimate predictive importance:
    leakage and identifiers require domain review, not automatic deletion.
    Category examples are display-only and omitted for high-risk fields.
    """
    if target not in df.columns: raise ValueError("Target column not found")
    task = infer_task(df[target])
    predictors = [x for x in df.columns if x != target]
    recommendations, feature_audit, high_risk = [], [], []
    for name in predictors:
        series = df[name]
        kind = inferred_kind(series)
        missing = int(series.isna().sum())
        distinct = int(series.nunique(dropna=True))
        reasons = []
        if missing == len(df): reasons.append("all values missing")
        if distinct <= 1: reasons.append("constant or empty column")
        normalized = name.lower().replace(" ", "_")
        leakage = any(term in normalized for term in LEAK_TERMS)
        # Keep mandatory Prepare/admission review aligned with the existing
        # feature-advice check: near-unique *Code/*Number fields may be identifiers,
        # even though their names do not end with id/key. This is a warning,
        # never proof of actual identity or prediction-time leakage.
        identifier = (normalized.endswith(("id","key","code","number"))
                      and distinct >= len(df)*.9)
        if leakage: reasons.append("possible outcome leakage")
        if identifier: reasons.append("likely identifier")
        if reasons:
            recommendations.append({"column":name,"reason":"; ".join(reasons),"requires_review":True})
        risk = "high" if leakage or identifier else "review" if reasons else "low"
        if risk == "high": high_risk.append(name)
        treatment = ("Excluded from modelling if all values are missing"
                     if missing == len(df) or distinct == 0 else
                     "Numeric: median imputation fitted on training folds" if kind == "numeric" else
                     "Categorical: mode imputation + capped one-hot encoding fitted on training folds")
        category_examples = []
        if kind == "categorical" and distinct and risk != "high":
            for value in series.dropna().unique()[:PREPARE_CATEGORY_EXAMPLE_LIMIT]:
                label = str(value)
                if len(label) > PREPARE_CATEGORY_EXAMPLE_LENGTH:
                    label = label[:PREPARE_CATEGORY_EXAMPLE_LENGTH - 1] + "…"
                category_examples.append(label)
        feature_audit.append({
            "column":name,"kind":kind,"missing":missing,
            "missing_pct":round(100*missing/len(df),2),
            "distinct":distinct,"risk":risk,
            "reasons":reasons,"treatment":treatment,
            "default_included":bool(distinct>0),
            "category_examples":category_examples,
        })
    return {
        "task":task,"target":target,"available_features":predictors,
        "recommend_exclude":recommendations,"feature_audit":feature_audit,
        "resource_plan":training_resource_plan(
            df.loc[:,[col for col in predictors if df[col].nunique(dropna=True)>0]],
            int(df[target].notna().sum())),
        "resource_plan_scope":"Preflight estimate for all usable candidate predictors before manual exclusions; the training request recomputes the actual budget.",
        "high_risk_features":high_risk,
        "missing_targets":int(df[target].isna().sum()),
        "transformations":[
            "Numeric: training-fold median imputation; all-missing columns omitted",
            "Categorical: training-fold mode imputation and capped one-hot encoding",
            "Preprocessing fitted separately within cross-validation folds and final training",
        ],
        "warnings":[
            "Feature availability after the outcome and repeated individuals are not inferred from data alone.",
            "High-risk features remain user-controlled; including any requires an explicit review acknowledgement.",
            "A time or group validation strategy should be used whenever random independence is not defensible.",
        ],
    }


def make_estimator(task: str, key: str):
    if task == "classification":
        mapping = {
            "logistic_regression": LogisticRegression(max_iter=1200, random_state=SEED),
            "decision_tree": DecisionTreeClassifier(max_depth=9, random_state=SEED),
            "random_forest": RandomForestClassifier(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "extra_trees": ExtraTreesClassifier(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "gradient_boosting": GradientBoostingClassifier(random_state=SEED),
            "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=15,early_stopping=False,random_state=SEED),
            "knn": KNeighborsClassifier(n_neighbors=3,n_jobs=1),
            "svm": SVC(kernel="rbf",C=1.0,cache_size=100,random_state=SEED),
            "naive_bayes": GaussianNB(),
        }
    else:
        mapping = {
            "linear_regression": LinearRegression(),
            "ridge": Ridge(alpha=1),
            "decision_tree": DecisionTreeRegressor(max_depth=9, random_state=SEED),
            "random_forest": RandomForestRegressor(n_estimators=70, max_depth=14, n_jobs=1, random_state=SEED),
            "gradient_boosting": GradientBoostingRegressor(random_state=SEED),
            "hist_gradient_boosting": HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=15,early_stopping=False,random_state=SEED),
            "knn": KNeighborsRegressor(n_neighbors=3,n_jobs=1),
            "svr": SVR(kernel="rbf",C=1.0,cache_size=100),
            "elastic_net": ElasticNet(alpha=0.1,l1_ratio=0.5,max_iter=1500,random_state=SEED),
        }
    if key not in mapping: raise ValueError(f"Invalid {task} model: {key}")
    return mapping[key]


NUMERIC_IMPUTATION_STRATEGIES = ("median", "mean")
CATEGORICAL_IMPUTATION_STRATEGIES = ("most_frequent", "constant")
CATEGORICAL_MISSING_MARKER = "__PILOTODIN_MISSING__"
MAX_ONE_HOT_CATEGORIES = 25


def validate_numeric_imputation(strategy: str) -> str:
    """Allow only known fold-fitted numeric imputation methods; fail closed."""
    if strategy not in NUMERIC_IMPUTATION_STRATEGIES:
        raise ValueError("Numeric imputation must be median or mean")
    return strategy


def validate_categorical_imputation(strategy: str) -> str:
    """Allowlist the categorical missing-value strategy."""
    if strategy not in CATEGORICAL_IMPUTATION_STRATEGIES:
        raise ValueError("Categorical imputation must be most_frequent or constant")
    return strategy


def check_categorical_missing_marker(X: pd.DataFrame, strategy: str) -> None:
    """Do not merge a real observed category with the reserved missing marker."""
    validate_categorical_imputation(strategy)
    if strategy != "constant":
        return
    for column in X:
        if (inferred_kind(X[column]) == "categorical"
                and X[column].dropna().eq(CATEGORICAL_MISSING_MARKER).any()):
            raise ValueError(
                "The reserved categorical missing marker already exists as a data value "
                f"in {column}. Select mode imputation instead."
            )


def make_pipeline(X: pd.DataFrame, task: str, model: str,
                  numeric_imputation: str = "median",
                  categorical_imputation: str = "most_frequent") -> Pipeline:
    numeric_imputation = validate_numeric_imputation(numeric_imputation)
    check_categorical_missing_marker(X, categorical_imputation)
    numeric = [c for c in X if inferred_kind(X[c]) == "numeric"]
    categorical = [c for c in X if c not in numeric]
    # Keep missing-only columns stable across folds; let imputers use safe constants.
    num_pipe = Pipeline([("imputer", SimpleImputer(strategy=numeric_imputation, keep_empty_features=True))])
    if model in ("logistic_regression", "linear_regression", "ridge", "elastic_net", "knn", "svm", "svr"):
        num_pipe.steps.append(("scaler", StandardScaler()))
    cat_pipe = Pipeline([("imputer", SimpleImputer(strategy=categorical_imputation,
                                                      fill_value=CATEGORICAL_MISSING_MARKER if categorical_imputation == "constant" else None,
                                                      keep_empty_features=True)),
                         ("encoder", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                                  max_categories=MAX_ONE_HOT_CATEGORIES))])
    ct = ColumnTransformer([("numeric",num_pipe,numeric),("categorical",cat_pipe,categorical)], sparse_threshold=0)
    return Pipeline([("preprocessor", ct), ("model", make_estimator(task, model))])


def validate_config(df: pd.DataFrame, target: str, excluded: list[str], models: list[str], task: str,
                    *, categorical_imputation: str = "most_frequent") -> tuple[pd.DataFrame, pd.Series, str]:
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
    budget=training_resource_plan(X,len(y),models,categorical_imputation=categorical_imputation)
    if not budget["within_local_budget"]:
        raise ValueError(
            "Local training resource guardrail exceeded: "
            +str(budget["labelled_rows"])+" labelled rows, approximately "
            +str(budget["estimated_dense_training_mb"])+" MB of dense training features. "
            +"This 8 GB-friendly build supports up to "
            +str(MAX_ML_LABELLED_ROWS)+" labelled rows and "
            +str(MAX_DENSE_TRAIN_BYTES//(1024*1024))+" MB estimated dense features. "
            +budget["selected_model_guard"]+". "
            +"Reduce rows/columns or choose a less costly model; the source project remains unchanged."
        )
    if task == "regression":
        y = pd.to_numeric(y, errors="coerce")
        if y.isna().any() or not np.isfinite(y).all(): raise ValueError("Regression target must contain finite numeric values")
    return X, y, actual_task


# Local-first, 8 GB-friendly safeguards. A source dataset may contain more rows;
# this budget applies ONLY to fitting a model, not to opening or exploring it.
MAX_ML_LABELLED_ROWS = 30_000
MAX_DENSE_TRAIN_BYTES = 256 * 1024 * 1024
MAX_KERNEL_MODEL_ROWS = 5_000  # nonlinear SVC/SVR train-time scales poorly
MAX_NEIGHBOUR_MODEL_ROWS = 12_000  # preserve practical CPU predict responsiveness


def training_resource_plan(X: pd.DataFrame, labelled_rows: int, models: list[str] | None = None,
                           *, categorical_imputation: str = "most_frequent") -> dict:
    """Conservative dense-matrix upper bound before starting expensive CV.

    Capped one-hot encoding uses at most 25 columns per categorical source,
    including a dedicated missing category when requested and needed.
    Assume *all* labelled rows could be training data because group splits
    need not retain a strict 80/20 row ratio. This is not a peak RSS bound.
    """
    encoded_width = 0
    for _, values in X.items():
        if inferred_kind(values) == "numeric":
            encoded_width += 1
        else:
            distinct = int(values.nunique(dropna=True))
            missing_marker = categorical_imputation == "constant" and values.isna().any()
            encoded_width += min(MAX_ONE_HOT_CATEGORIES, max(1, distinct + int(missing_marker)))
    estimated=int(labelled_rows*encoded_width*8)
    selected=set(models or [])
    if selected.intersection(("svm","svr")):
        model_row_limit=MAX_KERNEL_MODEL_ROWS
        model_guard="Kernel SVM/SVR: at most 5,000 labelled rows"
    elif "knn" in selected:
        model_row_limit=MAX_NEIGHBOUR_MODEL_ROWS
        model_guard="K-nearest neighbours: at most 12,000 labelled rows"
    else:
        model_row_limit=MAX_ML_LABELLED_ROWS
        model_guard="No additional model-family row limit"
    return {
        "labelled_rows":int(labelled_rows),
        "source_features":int(X.shape[1]),
        "estimated_encoded_columns":int(encoded_width),
        "estimated_dense_training_mb":round(estimated/(1024*1024),2),
        "row_limit":MAX_ML_LABELLED_ROWS,
        "selected_model_row_limit":model_row_limit,
        "selected_model_guard":model_guard,
        "model_family_row_limits":{"svm":MAX_KERNEL_MODEL_ROWS,"svr":MAX_KERNEL_MODEL_ROWS,
                                   "knn":MAX_NEIGHBOUR_MODEL_ROWS},
        "estimated_dense_mb_limit":MAX_DENSE_TRAIN_BYTES//(1024*1024),
        "within_local_budget":bool(labelled_rows<=model_row_limit and estimated<=MAX_DENSE_TRAIN_BYTES),
        "note":"Conservative upper-bound dense matrix for all labelled rows, including uneven group splits; model, CV, pandas and OS overhead are additional. Not a peak RAM measurement."
    }


def bounded_feature_sensitivity(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, task: str) -> dict:
    """Bounded post-selection permutation sensitivity on frozen held-out data.

    Analytic diagnostic, never used for model selection, hyperparameter tuning
    or causal inference. The source test set and fitted model are unchanged.
    """
    max_rows,max_features,repeats=64,8,2
    total=int(X_test.shape[1])
    count=min(total,max_features)
    if total==0 or len(X_test)<12 or len(y_test)!=len(X_test):
        return {"status":"unavailable","reason":"Too few held-out observations or no predictors for bounded sensitivity."}
    chosen=np.linspace(0,total-1,count,dtype=int).tolist()
    indices=np.linspace(0,len(X_test)-1,min(len(X_test),max_rows),dtype=int)
    sample=X_test.iloc[indices].copy(deep=True)
    truth=y_test.iloc[indices]
    if task not in ("classification","regression"):
        return {"status":"unavailable","reason":"Unknown modelling task."}
    def evaluate(frame:pd.DataFrame)->float:
        predicted=model.predict(frame)
        if task=="classification":
            return float(f1_score(truth,predicted,average="macro",zero_division=0))
        return float(mean_absolute_error(truth,predicted))
    baseline=evaluate(sample)
    rng=np.random.default_rng(SEED)
    rows=[]
    for index in chosen:
        feature=str(X_test.columns[index])
        changes=[]
        for _ in range(repeats):
            mutated=sample.copy(deep=True)
            mutated.iloc[:,index]=sample.iloc[rng.permutation(len(sample)),index].to_numpy()
            permuted=evaluate(mutated)
            # Positive delta means the unpermuted model score was better.
            changes.append(baseline-permuted if task=="classification" else permuted-baseline)
        rows.append({"feature":feature,"mean_importance":round(float(np.mean(changes)),5),
                     "repeat_std":round(float(np.std(changes)),5)})
    rows.sort(key=lambda row:(-row["mean_importance"],row["feature"]))
    return {
        "status":"computed","method":"Bounded post-selection permutation sensitivity",
        "metric":"Macro F1 loss" if task=="classification" else "MAE increase",
        "sample_rows":int(len(sample)),"total_test_rows":int(len(X_test)),
        "features_evaluated":len(rows),"total_predictors":total,
        "repeats":repeats,"seed":SEED,"data_source":"Frozen held-out set, AFTER model choice",
        "reference_metric":round(float(baseline),5),
        "sampled":bool(len(sample)<len(X_test) or count<total),
        "scores":rows,
        "limitations":[
            "A sampled diagnostic on a selected model, not a validated causal or local explanation.",
            "Correlated predictors, small samples and shuffled time/group values can distort the ranking.",
            "Untested predictors are not ranked; negative values reflect sampling variation or instability.",
            "Use this result to investigate behaviour, never to choose or retune the model on held-out data."
        ]
    }


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


def heldout_baseline_metric(task: str, y_test: pd.Series, training_reference: Any) -> float:
    """Score the frozen development-only baseline after model choice.

    It must never be used for candidate selection: the untouched test data
    is accessed only once, alongside the selected model's final evaluation.
    """
    if len(y_test)==0:
        raise ValueError("Cannot score a baseline with an empty test set")
    prediction=np.repeat(training_reference,len(y_test))
    if task=='classification':
        return round(float(f1_score(y_test,prediction,average='macro',zero_division=0)),5)
    if task=='regression':
        return round(float(mean_absolute_error(y_test,prediction)),5)
    raise ValueError("Unknown baseline task")


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
    if final.get('baseline_test_metric') is not None:
        metric='mae' if task=='regression' else 'f1_macro'
        candidate=final.get(metric)
        baseline_test=final['baseline_test_metric']
        if candidate is not None and ((candidate>=baseline_test) if task=='regression' else (candidate<=baseline_test)):
            issues.append('The model did not outperform its training-derived simple baseline on the held-out test set.')
    score_sd=next((m.get('cv_std') for m in development['models'] if m['key']==selected_model),0) or 0
    if score is not None and score_sd > .5*max(abs(score),.01):
        issues.append('Performance varied sharply across validation folds.')
    return {'level':'warning' if issues else 'review','issues':issues,
            'message':'Not reliable for real decisions' if issues else 'Promising preliminary result; validate independently before deployment.'}


def run_training(df: pd.DataFrame, target: str, excluded: list[str], models: list[str], task: str,
                 split_strategy:str='random', split_column:str|None=None, stop_check=None,
                 numeric_imputation:str='median', categorical_imputation:str='most_frequent'):
    numeric_imputation = validate_numeric_imputation(numeric_imputation)
    validate_categorical_imputation(categorical_imputation)
    # Optional cooperative checkpoint. sklearn's individual fit/CV call is
    # blocking; interruption is checked between expensive operations only.
    def checkpoint():
        if stop_check is not None:
            stop_check()
    checkpoint()
    if split_strategy not in ('random','time','group'):
        raise ValueError('Invalid split strategy')
    if split_strategy != 'random' and (not split_column or split_column not in df):
        raise ValueError('Group or time column is required for this split')
    if split_strategy != 'random' and split_column == target:
        raise ValueError('Target cannot also be a split column')
    # The validation/preflight must see the exact predictors that will be
    # fitted. Group IDs and timestamps are split metadata, never features.
    # Preserve the original user exclusions in the persisted experiment.
    fit_excluded = list(dict.fromkeys([*excluded, *([split_column] if split_strategy != 'random' else [])]))
    X, y, task = validate_config(df, target, fit_excluded, models, task,
                                 categorical_imputation=categorical_imputation)
    check_categorical_missing_marker(X, categorical_imputation)
    if X.empty or not X.shape[1]:raise ValueError('No predictor fields after split-column exclusion')
    cv_groups=None
    if split_strategy=='group':
        # Factorization preserves actual identifiers, mixed string/numeric IDs,
        # and a unique code for missing values. Avoid coalescing nulls into
        # legitimate source text such as '(Missing group)'.
        groups=pd.Series(pd.factorize(df.loc[X.index,split_column],sort=False)[0],
                         index=X.index,dtype='int64')
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
        sorted_times=times.iloc[order].reset_index(drop=True)
        if sorted_times.iloc[cut-1] == sorted_times.iloc[cut]:
            raise ValueError(
                'Time split boundary crosses identical timestamps. Use a different time grain '
                'or review the data; equal-time observations must not cross train and holdout.'
            )
        X_train,X_test=X.iloc[order[:cut]],X.iloc[order[cut:]]
        y_train,y_test=y.iloc[order[:cut]],y.iloc[order[cut:]]
        folds=3 if len(y_train)>=36 else 2
        # Split by DISTINCT timestamp, not row position: a repeated instant
        # must not leak between the development-train and validation folds.
        train_times=times.iloc[order[:cut]].reset_index(drop=True)
        instants=train_times.drop_duplicates().reset_index(drop=True)
        if len(instants)<folds+1:
            raise ValueError('Chronological cross-validation needs at least '+str(folds+1)+
                             ' distinct training timestamps; use a finer time grain or more data.')
        cv=[]
        for earlier,later in TimeSeriesSplit(n_splits=folds).split(instants):
            train_end=instants.iloc[earlier[-1]]
            test_start=instants.iloc[later[0]]
            test_end=instants.iloc[later[-1]]
            development=np.flatnonzero(train_times.le(train_end).to_numpy())
            validation=np.flatnonzero((train_times.ge(test_start)&train_times.le(test_end)).to_numpy())
            if not len(development) or not len(validation):
                raise ValueError('Chronological cross-validation produced an empty fold')
            cv.append((development,validation))
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
    base_pipe=Pipeline([('preprocessor',make_pipeline(X_train,task,models[0],numeric_imputation,categorical_imputation).named_steps['preprocessor']),('model',baseline)])
    cv_kwargs={'groups':cv_groups} if cv_groups is not None else {}
    # Group-aware CV is only valid when no group appears in both development folds.
    checkpoint()
    base_scores=cross_val_score(base_pipe,X_train,y_train,cv=cv,scoring=score,n_jobs=1,error_score='raise',**cv_kwargs)
    checkpoint()
    reports,pipelines=[],{}
    for key in models:
        checkpoint()
        pipe=make_pipeline(X_train,task,key,numeric_imputation,categorical_imputation)
        try:
            scores=cross_val_score(pipe,X_train,y_train,cv=cv,scoring=score,n_jobs=1,error_score='raise',**cv_kwargs)
            checkpoint()
            pipe.fit(X_train,y_train)
            checkpoint()
            value=float(scores.mean())*(1 if task=='classification' else -1)
            reports.append({'key':key,'name':LABELS[key],'cv_metric':round(value,5),
                            'cv_std':round(float(scores.std()),5),'status':'ready'})
            pipelines[key]=pipe
        except InterruptedError:
            raise  # Never disguise a user stop/timeout as one failed model.
        except Exception as ex:
            reports.append({'key':key,'name':LABELS[key],'status':'failed','error':str(ex)[:230]})
    checkpoint()
    if not pipelines:raise ValueError('Every model failed; review data type, validation strategy and feature configuration')
    baseline_cv=round(float(base_scores.mean())*(1 if task=='classification' else -1),5)
    wins=[m for m in reports if m['status']=='ready' and
          (m['cv_metric']<baseline_cv if task=='regression' else m['cv_metric']>baseline_cv)]
    return {'task':task,'target':target,'features':list(X.columns),'excluded_features':excluded,
            'numeric_imputation':numeric_imputation,'categorical_imputation':categorical_imputation,
            'split_strategy':split_strategy,'split_column':split_column,
            'labelled_rows':len(y),'train_rows':len(X_train),'test_rows':len(X_test),'folds':folds,
            'primary_metric':'F1 macro (higher is better)' if task=='classification' else 'MAE (lower is better)',
            'baseline_cv':baseline_cv,'beats_baseline':bool(wins),
            # Baseline prediction is fitted from the TRAINING target only.
            # It can be scored on the untouched holdout after model selection.
            'baseline_reference':native(y_train.value_counts().idxmax()) if task=='classification' else native(float(y_train.median())),
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
            is_bounded=s.nunique(dropna=True)<=30
            fields.append({"name":c,"kind":"select" if is_bounded else "text",
                           "options":categories if is_bounded else [],"required":False,
                           "observed_categories":int(s.nunique(dropna=True)),
                           "category_check_complete":bool(is_bounded)})
    return fields


def _prediction_domain(name: str) -> dict | None:
    """Strict bounds only for recognizable clock and nonnegative count fields.

    The first guardrail covered HourOfDay in demo data but missed the exact
    incident_hour_of_the_day field in real insurance claims. Use small,
    reviewed field-name aliases, not broad substring guessing: arbitrary
    fields containing 'hour', 'vehicle' or 'loss' need domain-specific meaning.
    """
    normalized = ''.join(c for c in name.lower() if c.isalnum())
    if normalized in {"hourofday", "incidenthouroftheday"}:
        return {"min": 0, "max": 23, "integer": True}
    if normalized in {"transactionsinlasthour", "numberofvehiclesinvolved"}:
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
            input_warnings.append(f"{f['name']} is missing; the model will use its training-fitted imputation.")
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
            # Only a COMPLETE observed vocabulary can prove unfamiliarity.
            # For high-cardinality text, sending only sampled categories must
            # never lead to a false out-of-distribution claim.
            if f.get('category_check_complete') and str(val) not in f.get('options',[]):
                input_warnings.append(
                    f"{f['name']} has a category not observed during training. "
                    "The encoder may map it to an unknown/infrequent group."
                )
    pred = pipe.predict(pd.DataFrame([row]))[0]
    result = {"prediction":native(pred),"model":pipe.named_steps["model"].__class__.__name__,"input_warnings":input_warnings}
    if hasattr(pipe,"predict_proba"):
        proba=pipe.predict_proba(pd.DataFrame([row]))[0]
        labels=pipe.named_steps["model"].classes_
        result["probabilities"] = [{"class":native(label),"probability":round(float(v),5)} for label,v in zip(labels,proba)]
        result["probability_estimates_calibrated"] = False
    return result
