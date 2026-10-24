"""A3 held-out evidence: same-test-set baseline and candid prediction warnings."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
import joblib

from backend import engine, main


class AlwaysNo:
    """Tiny pickle-safe test model; no learned artifact accepted from users."""
    def predict(self, rows):
        return np.array(["No"]*len(rows))


def test_classifier_baseline_uses_development_training_targets_only():
    df=pd.DataFrame({
        "Signal":list(range(64)),
        "Segment":["North" if i%3 else "South" for i in range(64)],
        "Outcome":["Yes" if i%2 else "No" for i in range(64)]
    })
    original=df.copy(deep=True)
    result,pipes,xt,yt=engine.run_training(df,"Outcome",[],["logistic_regression"],"classification")
    assert result["baseline_reference"] in {"Yes","No"}
    assert result["test_rows"]==len(yt)
    expected=float(engine.f1_score(yt,np.repeat(result["baseline_reference"],len(yt)),
                                   average="macro",zero_division=0))
    calculated=engine.heldout_baseline_metric("classification",yt,result["baseline_reference"])
    assert calculated==round(expected,5)
    assert "logistic_regression" in pipes
    assert original.equals(df)


def test_regression_baseline_uses_frozen_development_median():
    df=pd.DataFrame({"Signal":list(range(60)),
                     "Price":[float(200+i*(i%4+1)) for i in range(60)]})
    result,pipes,xt,yt=engine.run_training(df,"Price",[],["linear_regression"],"regression")
    reference=result["baseline_reference"]
    assert isinstance(reference,(float,int))
    expected=round(float(np.mean(np.abs(yt.to_numpy()-reference))),5)
    assert engine.heldout_baseline_metric("regression",yt,reference)==expected
    assert len(xt)==len(yt) and result["baseline_cv"]>=0


def test_selection_records_comparable_heldout_baseline_and_warns_on_a_tie(monkeypatch,tmp_path):
    exp_id="small-frozen-test"
    p=tmp_path/"models"/exp_id
    p.mkdir(parents=True)
    joblib.dump(AlwaysNo(),p/"logistic_regression.joblib")
    yt=pd.Series(["Yes","No"]*20)
    joblib.dump((pd.DataFrame({"Signal":list(range(40))}),yt),p/"test_set.joblib")
    experiment={
        "id":exp_id,"project_id":"isolated-project","status":"completed",
        "config":{"quality_version":2,"target":"Flagged","task":"classification"},
        "selected_model":None,
        "results":{"task":"classification","target":"Flagged",
                   "baseline_reference":"No","baseline_cv":.3,
                   "test_rows":40,"models":[{"key":"logistic_regression","status":"ready",
                                             "cv_metric":.6,"cv_std":.01}]}
    }
    store=[]
    monkeypatch.setattr(main,"experiment_or_404",lambda _:experiment)
    monkeypatch.setattr(main.quality,"current_version",lambda _:2)
    monkeypatch.setattr(main.storage,"HOME",tmp_path)
    monkeypatch.setattr(main.storage,"select_model",lambda eid,key,result:store.append(result) or True)
    response=main.choose_model(exp_id,main.SelectionRequest(model_key="logistic_regression"))
    final=response["final_results"]
    assert final["sample_count"]==40
    assert final["baseline_test_metric"]==final["f1_macro"]
    assert final["beats_heldout_baseline"] is False
    assert final["baseline_test_label"]=="Macro F1"
    assert any("held-out test set" in item for item in final["reliability"]["issues"])
    sensitivity=final["feature_sensitivity"]
    assert sensitivity["status"]=="computed"
    assert sensitivity["sample_rows"]==40 and sensitivity["total_predictors"]==1
    assert sensitivity["features_evaluated"]==1 and sensitivity["repeats"]==2
    assert sensitivity["scores"][0]["feature"]=="Signal"
    assert sensitivity["scores"][0]["mean_importance"]==0
    assert len(store)==1 and store[0] is final


class ProbabilityDummy:
    named_steps={"model":type("Names",(),{"classes_":np.array(["No","Yes"])})()}
    def predict(self, rows):
        return np.array(["Yes"]*len(rows))
    def predict_proba(self, rows):
        return np.array([[.2,.8]]*len(rows))


def test_predictions_warn_for_missing_inputs_unseen_categories_and_uncalibrated_probabilities():
    schema=[
        {"name":"HourOfDay","kind":"number","min":0,"max":23,
         "domain":{"integer":True,"min":0,"max":23}},
        {"name":"Device","kind":"select","options":["mobile","desktop"],
         "category_check_complete":True},
    ]
    model=ProbabilityDummy()
    ordinary=engine.predict_one(model,schema,{"HourOfDay":9,"Device":"mobile"})
    assert ordinary["input_warnings"]==[]
    assert ordinary["probabilities"][1]["probability"]==.8
    assert ordinary["probability_estimates_calibrated"] is False
    novel=engine.predict_one(model,schema,{"HourOfDay":9,"Device":"console"})
    assert any("not observed during training" in warning for warning in novel["input_warnings"])
    missing=engine.predict_one(model,schema,{"HourOfDay":"","Device":""})
    assert len(missing["input_warnings"])==2
    with pytest.raises(ValueError,match="HourOfDay"):
        engine.predict_one(model,schema,{"HourOfDay":25,"Device":"mobile"})


def test_truncated_high_cardinality_vocabulary_never_falsely_claims_unseen_input():
    schema=[{"name":"ZipCode","kind":"text","options":[],
             "observed_categories":400,"category_check_complete":False}]
    result=engine.predict_one(ProbabilityDummy(),schema,{"ZipCode":"CODE-399"})
    assert not any("not observed during training" in w for w in result["input_warnings"])


def test_reliability_does_not_invent_heldout_baseline_for_legacy_experiments():
    development={"task":"classification","test_rows":40,"baseline_cv":.2,
        "models":[{"key":"logistic_regression","cv_metric":.7,"cv_std":.01}]}
    final={"f1_macro":.8}
    review=engine.reliability_report(development,final,"logistic_regression")
    assert review["level"]=="review"
    assert review["issues"]==[]
