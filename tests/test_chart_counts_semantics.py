"""Explicit count chart denominator disclosure."""
import pandas as pd
from backend import analytics

def test_count_with_y_excludes_missing_and_explains_denominator():
    frame=pd.DataFrame({"Device":["mobile","mobile","desktop"],"Amount":[10,None,30]})
    with_y=analytics.chart(frame,0,'Device','Amount','bar','count')
    assert sum(int(r['value']) for r in with_y['data'])==2
    assert 'non-missing Amount' in with_y['note']
    no_y=analytics.chart(frame,0,'Device',None,'bar','count')
    assert sum(int(r['value']) for r in no_y['data'])==3
    assert 'Record count by Device' in no_y['note']
