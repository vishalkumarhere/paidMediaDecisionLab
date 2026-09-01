from streamlit.testing.v1 import AppTest
from luxe_lab.storage import ROOT


def app():
    return AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()


def assert_clean(at):
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_overview_and_all_views_render():
    at = app()
    assert_clean(at)
    assert len(at.metric)==4
    assert len(at.get('html'))==1
    for view in ['Campaigns','Order economics','Data & methodology','Overview']:
        at.segmented_control(key='view').set_value(view).run()
        assert_clean(at)
        assert len(at.get('html'))>0


def test_filters_change_metrics_and_empty_selection_is_safe():
    at = app()
    original = at.metric[0].value
    at.selectbox(key='channel').set_value('Meta').run()
    assert_clean(at)
    assert at.metric[0].value != original
    assert set(at.multiselect(key='campaigns').value)=={'C04','C05'}
    at.multiselect(key='campaigns').set_value([]).run()
    assert_clean(at)
    assert any('Select at least one' in i.value for i in at.info)
    assert len(at.metric)==0
    at.button[0].click().run()
    assert_clean(at)
    assert at.metric[0].value == original


def test_date_filter_and_literal_search():
    at = app()
    at.selectbox(key='period').set_value('Last 7 days').run()
    assert_clean(at)
    at.segmented_control(key='view').set_value('Data & methodology').run()
    assert_clean(at)
    at.text_input(key='search').set_value('NO_MATCH_[').run()
    assert_clean(at)
    assert any('0 matching rows' in c.value for c in at.caption)
    assert any('Campaign and channel filters do not apply' in c.value for c in at.caption)
