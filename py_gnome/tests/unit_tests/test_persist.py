'''
primarily tests the operations of the scenario module, the colander schemas,
and the ability of Model to be recreated in midrun
'''

from datetime import datetime, timedelta
import os
import shutil
from glob import glob

import numpy as np
import pytest

import gnome
from gnome.persist.scenario import Scenario
from gnome.utilities.remote_data import get_datafile

curr_dir = os.path.dirname(__file__)
datafiles = os.path.join(curr_dir, 'sample_data', 'boston_data')
saveloc_ = os.path.join(curr_dir, 'save_model')


# clean up saveloc_ if it exists from previous runs
# let Scenario.__init__() create saveloc_
if os.path.exists(saveloc_):
    shutil.rmtree(saveloc_)


@pytest.fixture(scope='module')
def images_dir(request):
    '''
    create images dir
    '''
    images_dir = os.path.join(datafiles, 'images')
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)

    os.makedirs(images_dir)

    return images_dir


def make_model(images_dir, uncertain=False):
    '''
    Create a model from the data in sample_data/boston_data
    It contains:
      - the GeoProjection
      - wind mover
      - random mover
      - cats shio mover
      - cats ossm mover
      - plain cats mover
    '''
    mapfile = get_datafile(os.path.join(datafiles, './MassBayMap.bna'))

    start_time = datetime(2013, 2, 13, 9, 0)
    model = gnome.model.Model(start_time=start_time,
                              duration=timedelta(days=2), time_step=30
                              * 60, uncertain=uncertain,
                              map=gnome.map.MapFromBNA(mapfile,
                              refloat_halflife=1))  # 1/2 hr in seconds
                                                    # hours

    print 'adding a renderer'

    model.outputters += gnome.renderer.Renderer(mapfile, images_dir,
            size=(800, 600))

    print 'adding a spill'
    model.spills += \
        gnome.spill.PointLineSource(num_elements=1000,
            start_position=(144.664166, 13.441944, 0.0),
            release_time=start_time, end_release_time=start_time
            + timedelta(hours=6))

    # need a scenario for SimpleMover
    # model.movers += SimpleMover(velocity=(1.0, -1.0, 0.0))

    print 'adding a RandomMover:'
    model.movers += gnome.movers.RandomMover(diffusion_coef=100000)

    print 'adding a wind mover:'

    series = np.zeros((2, ), dtype=gnome.basic_types.datetime_value_2d)
    series[0] = (start_time, (5, 180))
    series[1] = (start_time + timedelta(hours=18), (5, 180))

    w_mover = \
        gnome.movers.WindMover(gnome.environment.Wind(timeseries=series,
                               units='m/s'))
    model.movers += w_mover
    model.environment += w_mover.wind

    print 'adding a cats shio mover:'

    d_file1 = get_datafile(os.path.join(datafiles, './EbbTides.cur'))
    d_file2 = get_datafile(os.path.join(datafiles, './EbbTidesShio.txt'))
    c_mover = gnome.movers.CatsMover(d_file1,
            tide=gnome.environment.Tide(d_file2))

    # c_mover.scale_refpoint should automatically get set from tide object
    c_mover.scale = True  # default value
    c_mover.scale_value = -1

    # tide object automatically gets added by model
    model.movers += c_mover

    print 'adding a cats ossm mover:'

    d_file1 = get_datafile(os.path.join(datafiles,
                           './MerrimackMassCoast.cur'))
    d_file2 = get_datafile(os.path.join(datafiles,
                           './MerrimackMassCoastOSSM.txt'))
    c_mover = gnome.movers.CatsMover(d_file1,
            tide=gnome.environment.Tide(d_file2))
    c_mover.scale = True  # but do need to scale (based on river stage)
    c_mover.scale_refpoint = (-70.65, 42.58333)
    c_mover.scale_value = 1.
    model.movers += c_mover
    model.environment += c_mover.tide

    print 'adding a cats mover:'

    d_file1 = get_datafile(os.path.join(datafiles, 'MassBaySewage.cur'))
    c_mover = gnome.movers.CatsMover(d_file1)
    c_mover.scale = True  # but do need to scale (based on river stage)
    c_mover.scale_refpoint = (-70.78333, 42.39333)

    # the scale factor is 0 if user inputs no sewage outfall effects
    c_mover.scale_value = .04
    model.movers += c_mover
    return model


def test_init_exception():
    with pytest.raises(ValueError):
        Scenario(os.path.join(saveloc_, 'x', 'junk'))


def test_dir_gets_created(images_dir):
    assert not os.path.exists(saveloc_)
    Scenario(os.path.join(saveloc_))
    assert os.path.exists(saveloc_)


def test_exception_no_model_to_load(images_dir):
    '''
    raises exception since the saveloc_ from where to load the model is empty.
    There are no Model_*.txt files that can be loaded
    '''
    s = Scenario(os.path.join(saveloc_))
    with pytest.raises(ValueError):
        s.load()


def test_exception_no_model_to_save():
    s = Scenario(os.path.join(saveloc_))
    with pytest.raises(AttributeError):
        s.save()


def test_exception_multiple_models_to_load(images_dir):
    '''
    create a model, save it. Then copy the Model_*.json
    file to a new Mode_*_new.json file in the same location.
    During Scenario(...).load(), this should raise an exception
    since there should only be 1 Model_*.json in saveloc_
    '''
    model = make_model(images_dir)
    scene = Scenario(saveloc_, model)
    scene.save()
    m_file = glob(os.path.join(saveloc_, 'Model_*.json'))[0]
    (fname, ext) = os.path.splitext(m_file)
    f_new = '{0}_new'.format(fname)
    m_new = f_new + ext
    shutil.copyfile(m_file, m_new)
    with pytest.raises(ValueError):
        scene.load()


@pytest.mark.slow
@pytest.mark.parametrize('uncertain', [False, True])
def test_save_load_scenario(images_dir, uncertain):
    model = make_model(images_dir, uncertain)

    print 'saving scnario ..'
    scene = Scenario(saveloc_, model)
    scene.save()

    scene.model = None  # make it none - load from persistence
    print 'loading scenario ..'
    model2 = scene.load()

    assert model == model2


@pytest.mark.xfail
@pytest.mark.slow
@pytest.mark.parametrize('uncertain', [False, True])
def test_save_load_midrun_scenario(images_dir, uncertain):
    """
    create model, save it after 1step, then load and check equality of original
    model and persisted model
    """

    model = make_model(images_dir, uncertain)

    model.step()
    print 'saving scnario ..'
    scene = Scenario(saveloc_, model)
    scene.save()

    scene.model = None  # make it none - load from persistence
    print 'loading scenario ..'
    model2 = scene.load()

    for sc in zip(model.spills.items(), model2.spills.items()):
        sc[0]._array_allclose_atol = 1e-5  # need to change both atol
        sc[1]._array_allclose_atol = 1e-5

    assert model.spills == model2.spills
    assert model == model2


@pytest.mark.slow
@pytest.mark.parametrize('uncertain', [False, True])
def test_save_load_midrun_no_movers(images_dir, uncertain):
    """
    create model, save it after 1step, then load and check equality of original
    model and persisted model
    Remove all movers and ensure it still works as expected
    """

    model = make_model(images_dir, uncertain)

    for mover in model.movers:
        del model.movers[mover.id]

    model.step()
    print 'saving scnario ..'
    scene = Scenario(saveloc_, model)
    scene.save()

    scene.model = None  # make it none - load from persistence
    print 'loading scenario ..'
    model2 = scene.load()

    for sc in zip(model.spills.items(), model2.spills.items()):
        # need to change both atol since reading persisted data
        sc[0]._array_allclose_atol = 1e-5
        sc[1]._array_allclose_atol = 1e-5

    assert model.spills == model2.spills
    assert model == model2


@pytest.mark.xfail
@pytest.mark.slow
@pytest.mark.parametrize('uncertain', [False, True])
def test_load_midrun_ne_rewound_model(images_dir, uncertain):
    """
    Load the same model that was persisted previously after 1 step
    This time rewind the original model and test that the two are not equal.
    The data arrays in the spill container must not match
    """

    # data arrays in model.spills no longer equal

    model = make_model(images_dir, uncertain)

    model.step()
    print 'saving scnario ..'
    scene = Scenario(saveloc_, model)
    scene.save()

    model.rewind()
    model2 = scene.load()

    assert model.spills != model2.spills
    assert model != model2
