import pytest
from luxe_lab.generator import generate
from luxe_lab.pipeline import build

def test_same_seed_same_data_and_changed_seed_changes_it(config):
    config['sessions_per_campaign_day']=2
    first,_=generate(config)
    second,_=generate(config)
    assert first==second
    config['seed']+=1
    third,_=generate(config)
    assert first['orders']!=third['orders']

def test_two_independent_builds_have_identical_hashes(tmp_path,config):
    config['sessions_per_campaign_day']=2
    a=build(config,tmp_path/'first')
    b=build(config,tmp_path/'second')
    assert a['dataset_sha256']==b['dataset_sha256']
    assert a['raw']==b['raw']
    assert a['processed']==b['processed']
    assert a['status']=='validated'
    assert len(a['checks'])>=50
    assert all(c['violations']==0 for c in a['checks'])
    # A valid run is never destructively overwritten.
    with pytest.raises(FileExistsError):
        build(config,tmp_path/'first')

def test_invalid_config_does_not_create_run(tmp_path,config):
    config['as_of']='2026-08-24T12:00:00'
    with pytest.raises(ValueError):
        build(config,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()

