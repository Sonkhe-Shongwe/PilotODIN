"""Report exports render reviewed exhibits rather than JSON dumps."""
import fitz
from backend import reports

def test_exhibit_renders_group_values_and_preserves_sources():
    artifact={'operation':'compare','result':{'data':[{'label':'Gauteng','value':345.75},{'label':'Mpumalanga','value':180.5}]},'params':{'x':'Region','y':'Revenue'},
    'id':'0'*32,'dataset_version':3,'tool_version':'v1','computed_at':'2026-10-24','objective':'Regional sales'}
    report={'title':'Regional analysis','narrative':'Human-reviewed assessment','id':'a'*32,'revision':2,
    'dataset_versions':[3],'content_sha256':'f'*64,'evidence':[artifact],
    'limitations':['Descriptive statistics do not establish causation.']}
    html=reports.render_html(report).decode()
    pdf=reports.render_pdf(report)
    txt=' '.join(page.get_text() for page in fitz.open(stream=pdf,filetype='pdf'))
    assert '345.75' in html and '345.75' in txt
    assert 'Gauteng' in html and 'Gauteng' in txt
    assert 'f'*64 in html and 'f'*64 in txt
    assert '<pre>' not in html and html.startswith('<!doctype html>')
    assert 'Page 1' in txt
