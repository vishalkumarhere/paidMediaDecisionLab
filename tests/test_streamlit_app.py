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
    assert len(at.get('html'))>=1
    assert any('Weekly decision screen' in heading.value for heading in at.subheader)
    for view in ['Campaigns','Forecast & scenarios','Order economics','Data & methodology','Overview']:
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
    at.checkbox(key='include_unattributed').check().run()
    at.multiselect(key='campaigns').set_value(['UNATTRIBUTED']).run()
    assert_clean(at)
    assert any('paid campaigns only' in i.value for i in at.info)


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


def test_forecast_scenario_is_interactive_and_gate_aware():
    at = app()
    at.segmented_control(key='view').set_value('Forecast & scenarios').run()
    assert_clean(at)
    values = {metric.label:metric.value for metric in at.metric}
    assert 'Forecast Orders' in values
    assert 'Hypothetical spend' in values
    baseline_scenario_spend = values['Hypothetical spend']
    at.slider(key='scenario_spend_change').set_value(10).run()
    assert_clean(at)
    changed = {metric.label:metric.value for metric in at.metric}
    assert changed['Hypothetical spend'] != baseline_scenario_spend
    assert changed['Assumed order change'].startswith('+')
    at.selectbox(key='forecast_target').set_value('contribution_after_media_cents').run()
    assert_clean(at)
    at.number_input(key='scenario_capacity').set_value(0).run()
    assert_clean(at)
    assert any('inventory-capacity assumption limits' in warning.value for warning in at.warning)
