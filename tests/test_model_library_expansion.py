"""Additional bounded, grouped model library checks."""
from backend import engine

def test_every_registered_model_creates_matching_estimator():
    for task,names in (("classification",engine.CLASS_MODELS),("regression",engine.REG_MODELS)):
        assert len(names)>=8
        assert len(set(names))==len(names)
        for name in names:
            estimator=engine.make_estimator(task,name)
            assert estimator is not None
            assert name in engine.LABELS

def test_incompatible_model_family_rejected():
    import pandas as pd
    import pytest
    df=pd.DataFrame({"signal":list(range(40)),"outcome":['yes','no']*20})
    with pytest.raises(ValueError,match="incompatible"):
        engine.validate_config(df,'outcome',[],['svr'],'classification')
