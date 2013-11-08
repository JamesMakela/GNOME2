'''
Test all operations for gridcurrent mover work
'''

import datetime
import os

import numpy as np
import pytest

from gnome.movers import GridWindMover
from gnome.utilities import time_utils
from gnome.utilities.remote_data import get_datafile

from conftest import sample_sc_release

here = os.path.dirname(__file__)
wind_dir = os.path.join(here, 'sample_data', 'winds')

wind_file = get_datafile(os.path.join(wind_dir, 'WindSpeedDirSubset.nc'))
topology_file = get_datafile(os.path.join(wind_dir, 'WindSpeedDirSubsetTop.dat'))


def test_exceptions():
    """
    Test correct exceptions are raised
    """

    bad_file = os.path.join(wind_dir, 'WindSpeedDirSubset.CUR')
    with pytest.raises(ValueError):
        GridWindMover(bad_file)

    with pytest.raises(TypeError):
        GridWindMover(wind_file, topology_file=10)


num_le = 4
start_pos = (-123.57152, 37.369436, 0.0)
rel_time = datetime.datetime(2006, 3, 31, 21, 0)
time_step = 30 * 60  # seconds
model_time = time_utils.sec_to_date(time_utils.date_to_sec(rel_time))


def test_loop():
    """
    test one time step with no uncertainty on the spill
    checks there is non-zero motion.
    also checks the motion is same for all LEs
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time)
    wind = GridWindMover(wind_file, topology_file)
    delta = _certain_loop(pSpill, wind)

    _assert_move(delta)

	# will need to set windage to be constant or each particle has a different position
    #assert np.all(delta[:, 0] == delta[0, 0])  # lat move matches for all LEs
    #assert np.all(delta[:, 1] == delta[0, 1])  # long move matches for all LEs
    tol = 1e-2
    msg = r"{0} move is not within a tolerance of {1}"
    np.testing.assert_allclose(
    	delta[:,0],
    	delta[0,0],
    	tol,
    	tol,
    	msg.format('sf_bay', tol),
    	0,
    	)
    np.testing.assert_allclose(
    	delta[:,1],
    	delta[0,1],
    	tol,
    	tol,
    	msg.format('sf_bay', tol),
    	0,
    	)
    assert np.all(delta[:, 2] == 0)  # 'z' is zeros

    return delta


def test_uncertain_loop():
    """
    test one time step with uncertainty on the spill
    checks there is non-zero motion.
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time,
                               uncertain=True)
    wind = GridWindMover(wind_file, topology_file)
    u_delta = _uncertain_loop(pSpill, wind)

    _assert_move(u_delta)

    return u_delta


def test_certain_uncertain():
    """
    make sure certain and uncertain loop results in different deltas
    """

    delta = test_loop()
    u_delta = test_uncertain_loop()
    print
    print delta
    print u_delta
    assert np.all(delta[:, :2] != u_delta[:, :2])
    assert np.all(delta[:, 2] == u_delta[:, 2])


w_grid = GridWindMover(wind_file,topology_file)


def test_default_props():
    """
    test default properties
    """

    assert w_grid.uncertain_time_delay == 0
    assert w_grid.uncertain_angle_scale == .4


def test_uncertain_time_delay():
    """
    test setting / getting properties
    """

    w_grid.uncertain_time_delay = 3
    assert w_grid.uncertain_time_delay == 3


# def test_scale_value():
#     """
#     test setting / getting properties
#     """
# 
#     c_cats.scale_value = 0
#     print c_cats.scale_value
#     assert c_cats.scale_value == 0
# 
# 
# def test_scale_refpoint():
#     """
#     test setting / getting properties
#     """
# 
#     tgt = (1, 2, 3)
#     c_cats.scale_refpoint = tgt  # can be a list or a tuple
#     assert c_cats.scale_refpoint == tuple(tgt)
#     c_cats.scale_refpoint = list(tgt)  # can be a list or a tuple
#     assert c_cats.scale_refpoint == tuple(tgt)
# 
# 
# Helper functions for tests

def _assert_move(delta):
    """
    helper function to test assertions
    """

    print
    print delta
    assert np.all(delta[:, :2] != 0)
    assert np.all(delta[:, 2] == 0)


def _certain_loop(pSpill, wind):
    wind.prepare_for_model_run()
    wind.prepare_for_model_step(pSpill, time_step, model_time)
    delta = wind.get_move(pSpill, time_step, model_time)
    wind.model_step_is_done()

    return delta


def _uncertain_loop(pSpill, wind):
    wind.prepare_for_model_run()
    wind.prepare_for_model_step(pSpill, time_step, model_time)
    u_delta = wind.get_move(pSpill, time_step, model_time)
    wind.model_step_is_done()

    return u_delta


# def test_exception_new_from_dict():
#     """
#     test exceptions raised for new_from_dict
#     """
# 
#     c_cats = CatsMover(curr_file)
#     dict_ = c_cats.to_dict('create')
#     dict_.update({'tide': td})
#     with pytest.raises(KeyError):
#         CatsMover.new_from_dict(dict_)
# 
# 
# def test_new_from_dict_tide():
#     """
#     test to_dict function for Wind object
#     create a new wind object and make sure it has same properties
#     """
# 
#     c_cats = CatsMover(curr_file, tide=td)
#     dict_ = c_cats.to_dict('create')
#     dict_.update({'tide': td})
#     c2 = CatsMover.new_from_dict(dict_)
#     assert c_cats == c2
# 
# 
# def test_new_from_dict_curronly():
#     """
#     test to_dict function for Wind object
#     create a new wind object and make sure it has same properties
#     """
# 
#     c_cats = CatsMover(curr_file)
#     dict_ = c_cats.to_dict('create')
#     c2 = CatsMover.new_from_dict(dict_)
#     assert c_cats == c2
# 
# 
