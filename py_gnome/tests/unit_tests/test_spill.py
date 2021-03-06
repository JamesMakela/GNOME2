#!/usr/bin/env python

"""
Tests the spill code.
"""

from datetime import datetime, timedelta
import copy

import pytest

import numpy as np

from gnome.spill import (Spill,
                         PointLineSource)
from gnome.elements import ElementType
import gnome.array_types

from conftest import mock_append_data_arrays


# Used to mock SpillContainer functionality of creating/appending data_arrays
# Only care about 'positions' array type for all spills, no need to define
# and carry remaining numpy arrays
arr_types = {'positions': gnome.array_types.positions}


@pytest.mark.parametrize(("windage_range", "windage_persist"),
                         [(None, None),
                          ([0.02, 0.03], -1)
                          ])
def test_init(windage_range, windage_persist):
    spill = Spill(10, windage_range=windage_range,
                  windage_persist=windage_persist)
    if windage_range is None:
        windage_range = [0.01, 0.04]
    if windage_persist is None:
        windage_persist = 900

    assert np.all(spill.element_type.initializers['windages'].windage_range
                  == windage_range)
    assert (spill.element_type.initializers['windages'].windage_persist
            == windage_persist)


def test_init_exceptions():
    with pytest.raises(TypeError):
        Spill(10, element_type=ElementType(), windage_range=[0.01, 0.04])

    with pytest.raises(TypeError):
        Spill(10, element_type=ElementType(), windage_persist=0)


def test_deepcopy():
    """
    only tests that the spill_nums work -- not sure about anything else...

    test_spill_container does test some other issues.
    """

    sp1 = Spill()
    sp2 = copy.deepcopy(sp1)
    assert sp1 is not sp2

    # try deleting the copy, and see if any errors result

    del sp2
    del sp1


def test_copy():
    """
    only tests that the spill_nums work -- not sure about anything else...
    """

    sp1 = Spill()
    sp2 = copy.copy(sp1)
    assert sp1 is not sp2

    # try deleting the copy, and see if any errors result

    del sp1
    del sp2


def test_uncertain_copy():
    """
    only tests a few things...
    """

    spill = PointLineSource(
        num_elements=100,
        start_position=(28, -78, 0.),
        release_time=datetime.now(),
        end_position=(29, -79, 0.),
        end_release_time=datetime.now() + timedelta(hours=24),
        windage_range=(.02, .03),
        windage_persist=-1,
        )

    u_spill = spill.uncertain_copy()

    assert u_spill is not spill
    assert np.array_equal(u_spill.start_position, spill.start_position)
    del spill
    del u_spill


class Test_PointLineSource:

    num_elements = 10
    start_position = (-128.3, 28.5, 0)
    release_time = datetime(2012, 8, 20, 13)
    timestep = 3600  # one hour in seconds

    # nominal test cases for parametrizing some tests in this class
    nom_positions = [((-128.0, 28.0, 0.), (-129.0, 29.0, 0.)),  # nominal test
                     ((-128.0, 28.0, 0.), (-129.0, 29.0, 1.))]  # w/ z!=0

    def release_and_assert(self,
                           sp, release_time, timestep, data_arrays,
                           expected_num_released):
        """
        Helper function. All tests except one invoke this function.
        For each release test in this function, group the common actions
        in this function.

        :param sp: spill object
        :param release_time: release time for particles
        :param timestep: timestep to use for releasing particles
        :param data_arrays: data_arrays to which new elements are appended.
            dict containing numpy arrays for values. Serves the same
            function as gnome.spill_container.SpillContainer().data_arrays
        :param expected_num_released: number of particles that we expect
            to release for this timestep. This is used for assertions.

        It returns a copy of the data_arrays after appending the newly
        released particles to it. This is so the caller can do more
        assertions against it.
        Also so we can keep appending to data_arrays since that is what the
        SpillContainer will work until a rewind.
        """
        prev_num_rel = sp.num_released
        num = sp.num_elements_to_release(release_time, timestep)
        assert num == expected_num_released

        # updated after set_newparticle_values is called
        assert prev_num_rel == sp.num_released

        if num > 0:
            # only invoked if particles are released
            data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
            sp.set_newparticle_values(num, release_time, timestep, data_arrays)
            assert sp.num_released == prev_num_rel + expected_num_released
        else:
            # initialize all data arrays even if no particles are released
            if data_arrays == {}:
                data_arrays = mock_append_data_arrays(arr_types, num,
                                                      data_arrays)

        assert data_arrays['positions'].shape == (sp.num_released, 3)

        return data_arrays

    def test_init(self):
        """
        Tests object initializes correctly.
        - self.end_position == self.start_position if it is not given as input
        - self.end_release_time == self.release_time if not given as input
        """
        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)

        assert sp.num_elements == self.num_elements
        assert (np.all(sp.start_position == self.start_position) and
                np.all(sp.start_position == sp.end_position))
        assert (np.all(sp.release_time == self.release_time) and
                np.all(sp.release_time == sp.end_release_time))

    def test_noparticles_model_run_after_release_time(self):
        """
        Tests that the spill doesn't release anything if the first call
        to release elements is after the release time.
        This so that if the user sets the model start time after the spill,
        they don't get anything.
        """
        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)

        # Test no particles released for following conditions
        #     current_time > spill's release_time
        #     current_time + timedelta > spill's release_time
        for rel_delay in range(1, 3):
            num = sp.num_elements_to_release(self.release_time
                                   + timedelta(hours=rel_delay),
                                   time_step=30 * 60)
            #assert num is None
            assert num == 0

        # rewind and it should work
        sp.rewind()
        data_arrays = self.release_and_assert(sp, self.release_time, 30 * 60,
                                {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

    def test_noparticles_model_run_before_release_time(self):
        """
        Tests that the spill doesn't release anything if the first call
        to num_elements_to_release is before the release_time + timestep.
        """

        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)
        print 'release_time:', self.release_time
        timestep = 360  # seconds

        # right before the release
        num = sp.num_elements_to_release(self.release_time -
                                         timedelta(seconds=360), timestep)
        #assert num is None
        assert num == 0

        # right after the release
        data_arrays = self.release_and_assert(sp, self.release_time -
                                timedelta(seconds=1),
                                timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

    def test_inst_point_release(self):
        """
        Test all particles for an instantaneous point release are released
        correctly.
        - also tests that once all particles have been released, no new
          particles are released in subsequent steps
        """
        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)
        timestep = 3600  # seconds

        # release all particles
        data_arrays = self.release_and_assert(sp, self.release_time,
                                timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

        # no more particles to release since all particles have been released
        num = sp.num_elements_to_release(self.release_time + timedelta(10),
                timestep)
        #assert num is None
        assert num == 0

        # reset and try again
        sp.rewind()
        assert sp.num_released == 0
        num = sp.num_elements_to_release(self.release_time - timedelta(10),
                                         timestep)
        #assert num is None
        assert num == 0
        assert sp.num_released == 0

        # release all particles
        data_arrays = self.release_and_assert(sp, self.release_time,
                                timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

    def test_cont_point_release(self):
        """
        Time varying release so release_time < end_release_time. It releases
        particles over 10 hours. start_position == end_position so it is still
        a point source

        It simulates how particles could be released by a Model with a variable
        timestep
        """
        sp = PointLineSource(num_elements=100,
                start_position=self.start_position,
                release_time=self.release_time,
                end_release_time=self.release_time
                + timedelta(hours=10))
        timestep = 3600  # one hour in seconds

        """
        Release elements incrementally to test continuous release

        4 times and timesteps over which elements are released. The timesteps
        are variable
        """
        # at exactly the release time -- ten get released at start_position
        # one hour into release -- ten more released
        # keep appending to data_arrays in same manner as SpillContainer would
        # 1-1/2 hours into release - 5 more
        # at end -- rest (75 particles) should be released
        data_arrays = {}
        delay_after_rel_time = [timedelta(hours=0),
                                timedelta(hours=1),
                                timedelta(hours=2),
                                timedelta(hours=10)]
        ts = [timestep, timestep, timestep / 2, timestep]
        exp_num_released = [10, 10, 5, 75]

        for ix in range(4):
            data_arrays = self.release_and_assert(sp,
                                self.release_time + delay_after_rel_time[ix],
                                ts[ix], data_arrays, exp_num_released[ix])
            assert np.alltrue(data_arrays['positions'] == self.start_position)

        assert sp.num_released == sp.num_elements

        # rewind and reset data arrays for new release
        sp.rewind()
        data_arrays = {}

        # 360 second time step: should release first LE
        # In 3600 sec, 10 particles are released so one particle every 360sec
        # release one particle each over (360, 720) seconds
        for ix in range(2):
            ts = ix * 360 + 360
            data_arrays = self.release_and_assert(sp, self.release_time, ts,
                                                  data_arrays, 1)
            assert np.alltrue(data_arrays['positions'] == self.start_position)

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_inst_line_release(self, start_position, end_position):
        """
        release all elements instantaneously but
        start_position != end_position so they are released along a line
        """
        sp = PointLineSource(num_elements=11,
                start_position=start_position,
                release_time=self.release_time,
                end_position=end_position)
        data_arrays = self.release_and_assert(sp, self.release_time,
                                              600, {}, sp.num_elements)

        assert data_arrays['positions'].shape == (11, 3)
        assert np.array_equal(data_arrays['positions'][:, 0],
                              np.linspace(-128, -129, 11))
        assert np.array_equal(data_arrays['positions'][:, 1],
                              np.linspace(28, 29, 11))

        assert sp.num_released == 11

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_first_timestep(self,
                                              start_position,
                                              end_position):
        """
        testing a release that is releasing while moving over time; however,
        all particles are released in 1st timestep

        In this one it all gets released in the first time step.
        """
        sp = PointLineSource(num_elements=11,
                start_position=start_position,
                release_time=self.release_time,
                end_position=end_position,
                end_release_time=self.release_time + timedelta(minutes=100))
        timestep = 100 * 60

        # the full release over one time step
        # (plus a tiny bit to get the last one)
        data_arrays = self.release_and_assert(sp, self.release_time,
                                            timestep + 1, {}, sp.num_elements)

        assert data_arrays['positions'].shape == (11, 3)
        assert np.array_equal(data_arrays['positions'][:, 0],
                              np.linspace(-128, -129, 11))
        assert np.array_equal(data_arrays['positions'][:, 1],
                              np.linspace(28, 29, 11))

        assert sp.num_released == 11

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_multiple_timesteps(self,
                                                 start_position,
                                                 end_position):
        """
        testing a release that is releasing while moving over time

        Release 1/10 of particles (10 out of 100) over two steps. Then release
        the remaining particles in the last step
        """
        num_elems = 100
        sp = PointLineSource(num_elems,
                start_position=start_position,
                release_time=self.release_time,
                end_position=end_position,
                end_release_time=self.release_time + timedelta(minutes=100))
        lats = np.linspace(sp.start_position[0], sp.end_position[0], num_elems)
        lons = np.linspace(sp.start_position[1], sp.end_position[1], num_elems)
        z = np.linspace(sp.start_position[2], sp.end_position[2], num_elems)

        # at release time with time step of 1/10 of release_time
        # 1/10th of total particles are expected to be released
        # release 10 particles over two steps. Then release remaining particles
        # over the last timestep
        timestep = 600
        data_arrays = {}
        delay_after_rel_time = [timedelta(0),
                                timedelta(seconds=timestep),
                                #timedelta(minutes=100)    # releases 0!
                                timedelta(minutes=90)]
        ts = [timestep, timestep, timestep]
        exp_elems = [10, 10, 80]

        for ix in range(len(ts)):
            data_arrays = self.release_and_assert(sp,
                            self.release_time + delay_after_rel_time[ix],
                            ts[ix], data_arrays, exp_elems[ix])
            assert np.array_equal(
                    data_arrays['positions'][:, 0], lats[:sp.num_released])
            assert np.array_equal(
                    data_arrays['positions'][:, 1], lons[:sp.num_released])

            if np.any(z != 0):
                assert np.array_equal(
                    data_arrays['positions'][:, 2], z[:sp.num_released])

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_vary_timestep(self, start_position,
                                             end_position, vary_timestep=True):
        """
        testing a release that is releasing while moving over time

        making sure it's right for the full release
        - vary the timestep if 'vary_timestep' is True
        - the release rate is a constant

        Same test with vary_timestep=False is used by
        test_cardinal_direction_release(..)
        """
        sp = PointLineSource(num_elements=50,
                start_position=start_position,
                release_time=self.release_time,
                end_position=end_position,
                end_release_time=self.release_time + timedelta(minutes=50))

        # start before release
        time = self.release_time - timedelta(minutes=10)
        delta_t = timedelta(minutes=10)
        num_rel_per_min = 1  # release 50 particles in 50 minutes
        data_arrays = {}

        # multiplier for varying the timestep
        mult = 0
        if not vary_timestep:
            mult = 1
        # end after release - release 10 particles at every step
        while time < sp.end_release_time:
            var_delta_t = delta_t   # vary delta_t
            exp_num_rel = 0
            if (time + delta_t > self.release_time):
                # change the rate at which particles are released
                if vary_timestep:
                    mult += 1

                var_delta_t = mult * delta_t
                timestep_min = var_delta_t.seconds / 60
                exp_num_rel = min(sp.num_elements - sp.num_released,
                                  num_rel_per_min * timestep_min)

            data_arrays = self.release_and_assert(sp,
                                                  time,
                                                  var_delta_t.total_seconds(),
                                                  data_arrays,
                                                  exp_num_rel)
            time += var_delta_t

        # all particles have been released
        assert data_arrays['positions'].shape == (sp.num_elements, 3)
        assert np.allclose(data_arrays['positions'][0], sp.start_position, 0,
                           1e-14)
        assert np.allclose(data_arrays['positions'][-1], sp.end_position, 0,
                           1e-14)

        # the delta position is a constant and is given by
        # (sp.end_position-sp.start_position)/(sp.num_elements-1)
        delta_p = (sp.end_position - sp.start_position) / (sp.num_elements - 1)
        assert np.all(delta_p == sp.delta_pos)
        assert np.allclose(delta_p, np.diff(data_arrays['positions'], axis=0),
                           0, 1e-10)

    positions = [((128.0, 2.0, 0.), (128.0, -2.0, 0.)),     # south
                 ((128.0, 2.0, 0.), (128.0, 4.0, 0.)),      # north
                 ((128.0, 2.0, 0.), (125.0, 2.0, 0.)),      # west
                 ((-128.0, 2.0, 0.), (-120.0, 2.0, 0.)),    # east
                 ((-128.0, 2.0, 0.), (-120.0, 2.01, 0.))]   # almost east

    @pytest.mark.parametrize(('start_position', 'end_position'), positions)
    def test_cont_cardinal_direction_release(self, start_position,
                                             end_position):
        """
        testing a line release to the south, north, west, east, almost east
        - multiple elements per step
        - also start before release and end after release

        Same test as test_cont_line_release3; however, the timestep is
        fixed as opposed to variable.
        """
        self.test_cont_line_release_vary_timestep(start_position, end_position,
                                     vary_timestep=False)

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_single_elem_over_multiple_timesteps(self,
                                                start_position, end_position):
        """
        testing a release that is releasing while moving over time
        - less than one elements is released per step. A single element is
          released over multiple time steps.

        Test it's right for the full release
        """
        sp = PointLineSource(num_elements=10,
                start_position=start_position,
                release_time=self.release_time,
                end_position=end_position,
                end_release_time=self.release_time + timedelta(minutes=50))

        # start before release
        time = self.release_time - timedelta(minutes=2)
        delta_t = timedelta(minutes=2)
        timestep = delta_t.total_seconds()
        data_arrays = {}

        # end after release
        while time < sp.end_release_time + delta_t:
            """
            keep releasing particles - no need to use self.release_and_assert
            since computing expected_number_of_particles_released is cumbersome
            Also, other tests verify that expected number of particles are
            being released - keep this easy to understand and follow
            """
            num = sp.num_elements_to_release(time, timestep)
            data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
            sp.set_newparticle_values(num, time, timestep, data_arrays)
            time += delta_t

        assert data_arrays['positions'].shape == (sp.num_elements, 3)
        assert np.array_equal(data_arrays['positions'][0], sp.start_position)
        assert np.array_equal(data_arrays['positions'][-1], sp.end_position)

        # the delta position is a constant and is given by
        # (sp.end_position-sp.start_position)/(sp.num_elements-1)
        delta_p = (sp.end_position - sp.start_position) / (sp.num_elements - 1)
        assert np.all(delta_p == sp.delta_pos)
        assert np.allclose(delta_p, np.diff(data_arrays['positions'], axis=0),
                           0, 1e-10)

    def test_cont_not_valid_times_exception(self):
        """ Check exception raised if end_release_time < release_time """
        with pytest.raises(ValueError):
            PointLineSource(num_elements=100,
                    start_position=self.start_position,
                    release_time=self.release_time,
                    end_release_time=self.release_time - timedelta(seconds=1))

    def test_end_position(self):
        """
        if end_position = None, then automatically set it to start_position
        """
        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)

        sp.start_position = (0, 0, 0)
        assert np.any(sp.start_position != sp.end_position)

        sp.end_position = None
        assert np.all(sp.start_position == sp.end_position)

    def test_end_release_time(self):
        """
        if end_release_time = None, then automatically set it to release_time
        """
        sp = PointLineSource(num_elements=self.num_elements,
                start_position=self.start_position,
                release_time=self.release_time)

        sp.release_time = self.release_time + timedelta(hours=20)
        assert sp.release_time != sp.end_release_time

        sp.end_release_time = None
        assert sp.release_time == sp.end_release_time


""" A few more line release (PointLineSource) tests """
num_elems = (
    (998, ),
    (100, ),
    (11, ),
    (10, ),
    (5, ),
    (4, ),
    (3, ),
    (2, ),
    )


@pytest.mark.parametrize(('num_elements', ), num_elems)
def test_single_line(num_elements):
    """
    various numbers of elemenets over ten time steps, so release
    is less than one, one and more than one per time step.
    """
    print 'using num_elements:', num_elements
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=10)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = PointLineSource(num_elements=num_elements,
                         start_position=start_pos,
                         release_time=release_time,
                         end_position=end_pos,
                         end_release_time=end_time)

    time = release_time
    data_arrays = {}
    while time <= end_time + time_step * 2:
        #data = sp.release_elements(time, time_step.total_seconds())
        num = sp.num_elements_to_release(time, time_step.total_seconds())
        data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
        if num > 0:
            sp.set_newparticle_values(num, time, time_step.total_seconds(),
                                      data_arrays)

        time += time_step

    assert len(data_arrays['positions']) == num_elements
    assert np.allclose(data_arrays['positions'][0], start_pos)
    assert np.allclose(data_arrays['positions'][-1], end_pos)

    # all axes should release particles with same, evenly spaced delta_position
    for ix in range(3):
        assert np.allclose(data_arrays['positions'][:, ix],
                     np.linspace(start_pos[ix], end_pos[ix], num_elements))


def test_line_release_with_one_element():
    """
    one element with a line release
    -- doesn't really make sense, but it shouldn't crash
    """
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=10)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = PointLineSource(num_elements=1,
                                   start_position=start_pos,
                                   release_time=release_time,
                                   end_position=end_pos,
                                   end_release_time=end_time)

    num = sp.num_elements_to_release(release_time, time_step.total_seconds())
    data_arrays = mock_append_data_arrays(arr_types, num)

    assert num == 1

    sp.set_newparticle_values(num, release_time, time_step.total_seconds(),
                                      data_arrays)
    assert sp.num_released == 1
    assert np.array_equal(data_arrays['positions'], [start_pos])


def test_line_release_with_big_timestep():
    """
    a line release: where the timestep spans before to after the release time
    """
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=300)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = PointLineSource(num_elements=10,
                         start_position=start_pos,
                         release_time=release_time,
                         end_position=end_pos,
                         end_release_time=end_time)

    num = sp.num_elements_to_release(release_time - timedelta(seconds=100),
                                     time_step.total_seconds())
    assert num == sp.num_elements

    data_arrays = mock_append_data_arrays(arr_types, num)
    sp.set_newparticle_values(num, release_time - timedelta(seconds=100),
                              time_step.total_seconds(), data_arrays)

    # all axes should release particles with same, evenly spaced delta_position
    for ix in range(3):
        assert np.allclose(data_arrays['positions'][:, ix],
                     np.linspace(start_pos[ix], end_pos[ix], sp.num_elements))

""" end line release (PointLineSource) tests"""


def release_elements(sp, release_time, time_step, data_arrays={}):
    """
    Common code for all spatial release tests
    """
    num = sp.num_elements_to_release(release_time, time_step)

    if num > 0:
        # release elements and set their initial values
        data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
        sp.set_newparticle_values(num, release_time, time_step, data_arrays)
    else:
        if data_arrays == {}:
            # initialize arrays w/ 0 elements if nothing is released
            data_arrays = mock_append_data_arrays(arr_types, 0, data_arrays)

    return (data_arrays, num)


""" conditions for SpatialRelease """


class TestSpatialRelease:
    @pytest.fixture(autouse=True)
    def setup(self, sample_spatial_release):
        """
        define common use attributes here.
        rewind the model. Fixture is a function argument only for this function
        autouse means it is used by all test functions without explicitly
        stating it as a function argument
        After each test, the autouse fixture setup is called so self.sp and
        self.start_positions get defined
        """
        #if not hasattr(self, 'sp'):
        self.sp = sample_spatial_release[0]
        self.start_positions = sample_spatial_release[1]
        self.sp.rewind()

    def test_SpatialRelease_rewind(self):
        """ test rewind sets state to original """
        assert self.sp.num_released == 0
        assert self.sp.start_time_invalid == True

    def test_SpatialRelease_0_elements(self):
        """
        if current_time + timedelta(seconds=time_step) <= self.release_time,
        then do not release any more elements
        """
        num = self.sp.num_elements_to_release(self.sp.release_time -
                                              timedelta(seconds=600), 600)
        assert num == 0

        self.sp.rewind()

        # first call after release_time
        num = self.sp.num_elements_to_release(self.sp.release_time +
                                              timedelta(seconds=1), 600)
        assert num == 0

        # still shouldn't release
        num = self.sp.num_elements_to_release(self.sp.release_time +
                                              timedelta(hours=1), 600)
        assert num == 0

        self.sp.rewind()

        # now it should:
        (data_arrays, num) = release_elements(self.sp, self.sp.release_time,
                                              600)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)

    def test_SpatialRelease(self):
        """
        see if the right arrays get created
        """
        (data_arrays, num) = release_elements(self.sp, self.sp.release_time,
                                              600)

        assert (self.sp.num_released == self.sp.num_elements and
                self.sp.num_elements == num)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)

    def test_SpatialRelease_inst_release_twice(self):
        """
        make sure they don't release elements twice
        """
        (data_arrays, num) = release_elements(self.sp, self.sp.release_time,
                                              600)
        assert (self.sp.num_released == self.sp.num_elements and
                self.sp.num_elements == num)

        (data_arrays, num) = release_elements(self.sp, self.sp.release_time +
                                              timedelta(seconds=600), 600,
                                              data_arrays)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)
        assert num == 0


# def test_PointSourceSurfaceRelease_new_from_dict():
#     """
#     test to_dict function for Wind object
#     create a new wind object and make sure it has same properties
#     """
# 
#     spill = PointSourceSurfaceRelease(num_elements=1000,
#             start_position=(144.664166, 13.441944, 0.),
#             release_time=datetime(2013, 2, 13, 9, 0),
#             end_release_time=datetime(2013, 2, 13, 9, 0)
#             + timedelta(hours=6))
# 
#     sp_state = spill.to_dict('create')
#     print sp_state
# 
#     # this does not catch two objects with same ID
# 
#     sp2 = PointSourceSurfaceRelease.new_from_dict(sp_state)
# 
#     assert spill == sp2
# 
# 
# def test_PointSourceSurfaceRelease_from_dict():
#     """
#     test from_dict function for Wind object
#     update existing wind object from_dict
#     """
# 
#     spill = PointSourceSurfaceRelease(num_elements=1000,
#             start_position=(144.664166, 13.441944, 0.),
#             release_time=datetime(2013, 2, 13, 9, 0),
#             end_release_time=datetime(2013, 2, 13, 9, 0)
#             + timedelta(hours=6))
# 
#     sp_dict = spill.to_dict()
#     sp_dict['windage_range'] = [.02, .03]
#     spill.from_dict(sp_dict)
# 
#     for key in sp_dict.keys():
#         if isinstance(spill.__getattribute__(key), np.ndarray):
#             np.testing.assert_equal(sp_dict.__getitem__(key),
#                                     spill.__getattribute__(key))
#         else:
#             assert spill.__getattribute__(key) \
#                 == sp_dict.__getitem__(key)
#==============================================================================

if __name__ == '__main__':

    # TC = Test_PointSourceSurfaceRelease()
    # TC.test_model_skips_over_release_time()

    test_line_release_with_big_timestep()
