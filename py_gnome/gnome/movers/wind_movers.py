'''
Movers using wind as the forcing function
'''

import os
import copy
from datetime import datetime
import math

import numpy as np

from gnome.utilities import serializable
from gnome.movers import CyMover
from gnome import basic_types
from gnome.cy_gnome.cy_wind_mover import CyWindMover
from gnome.cy_gnome.cy_gridwind_mover import CyGridWindMover
from gnome import environment
from gnome.utilities import rand
import gnome.array_types


class WindMoversBase(CyMover):
    state = copy.deepcopy(serializable.Serializable.state)
    state.add(update=['uncertain_duration', 'uncertain_time_delay',
                      'uncertain_speed_scale'],
              create=['uncertain_duration', 'uncertain_time_delay',
                      'uncertain_speed_scale', 'uncertain_angle_scale',
                      'uncertain_angle_units'],
              read=['uncertain_angle_scale'])

    def __init__(self,
        uncertain_duration=24,
        uncertain_time_delay=0,
        uncertain_speed_scale=2.,
        uncertain_angle_scale=0.4,
        uncertain_angle_units='rad',
        **kwargs):
        """
        This is simply a base class for WindMover and GridWindMover for the
        common properties.

        The classes that inherit from this should define the self.mover object
        correctly so it has the required attributes.

        Input args with defaults:

        :param uncertain_duration: (seconds) the randomly generated uncertainty
            array gets recomputed based on 'uncertain_duration'
        :param uncertain_time_delay: when does the uncertainly kick in.
        :param uncertain_speed_scale: Scale for uncertainty in wind speed
            non-dimensional number
        :param uncertain_angle_scale: Scale for uncertainty in wind direction
            'deg' or 'rad'
        :param uncertain_angle_units: 'rad' or 'deg'. These are the units for
            the uncertain_angle_scale.

        It calls super in the __init__ method and passes in the optional
        parameters (kwargs)
        """
        super(WindMoversBase, self).__init__(**kwargs)

        self.uncertain_duration = uncertain_duration
        self.uncertain_time_delay = uncertain_time_delay
        self.uncertain_speed_scale = uncertain_speed_scale

        # also sets self._uncertain_angle_units
        self.set_uncertain_angle(uncertain_angle_scale, uncertain_angle_units)

        self.array_types.update(
                  {'windages': gnome.array_types.windages,
                   'windage_range': gnome.array_types.windage_range,
                   'windage_persist': gnome.array_types.windage_persist})

    # no conversion necessary - simply sets/gets the stored value
    uncertain_speed_scale = property(lambda self: \
            self.mover.uncertain_speed_scale, lambda self, val: \
            setattr(self.mover, 'uncertain_speed_scale', val))

    @property
    def uncertain_duration(self):
        return self.mover.uncertain_duration / 3600.0

    @uncertain_duration.setter
    def uncertain_duration(self, val):
        self.mover.uncertain_duration = val * 3600.0

    @property
    def uncertain_time_delay(self):
        return self.mover.uncertain_time_delay / 3600.0

    @uncertain_time_delay.setter
    def uncertain_time_delay(self, val):
        self.mover.uncertain_time_delay = val * 3600.0

    @property
    def uncertain_angle_units(self):
        """
        units specified by the user when setting the uncertain_angle:
        set_uncertain_angle()
        """
        return self._uncertain_angle_units

    @property
    def uncertain_angle_scale(self):
        """
        read only - this is set when set_uncertain_angle() is called
        It returns the angle in 'uncertain_angle_units'
        """
        if self.uncertain_angle_units == 'deg':
            return self.mover.uncertain_angle_scale * 180.0 / math.pi
        else:
            return self.mover.uncertain_angle_scale

    def set_uncertain_angle(self, val, units):
        """
        this must be a function because user must provide units with value
        """
        if units not in ['deg', 'rad']:
            raise ValueError("units for uncertain angle can be either"
                             " 'deg' or 'rad'")

        if units == 'deg':  # convert to radians
            self.mover.uncertain_angle_scale = val * math.pi / 180.0
        else:
            self.mover.uncertain_angle_scale = val

        self._uncertain_angle_units = units

    def prepare_for_model_step(
        self,
        sc,
        time_step,
        model_time_datetime,
        ):
        """
        Call base class method using super
        Also updates windage for this timestep

        :param sc: an instance of gnome.spill_container.SpillContainer class
        :param time_step: time step in seconds
        :param model_time_datetime: current time of model as a date time object
        """

        super(WindMoversBase, self).prepare_for_model_step(sc, time_step,
                model_time_datetime)

        # if no particles released, then no need for windage
        # todo: revisit this since sc.num_released shouldn't be None
        if sc.num_released is None  or sc.num_released == 0:
            return

        for spill in sc.spills:
            spill_mask = sc.get_spill_mask(spill)

            if np.any(spill_mask):
                rand.random_with_persistance(
                                sc['windage_range'][spill_mask, 0],
                                sc['windage_range'][spill_mask, 1],
                                sc['windages'][spill_mask],
                                sc['windage_persist'][spill_mask],
                                time_step)

    def get_move(
        self,
        sc,
        time_step,
        model_time_datetime,
        ):
        """
        Override base class functionality because mover has a different
        get_move signature

        :param sc: an instance of the gnome.SpillContainer class
        :param time_step: time step in seconds
        :param model_time_datetime: current time of the model as a date time
                                    object
        """
        self.prepare_data_for_get_move(sc, model_time_datetime)

        if self.active and len(self.positions) > 0:
            self.mover.get_move(
                self.model_time,
                time_step,
                self.positions,
                self.delta,
                sc['windages'],
                self.status_codes,
                self.spill_type,
                )

        return self.delta.view(dtype=basic_types.world_point_type).reshape((-1,
                len(basic_types.world_point)))

    def _state_as_str(self):
        """
        Returns a string containing properties of object.
        This can be called by __repr__ or __str__ to display props
        """
        info = \
              '  uncertain_duration={0.uncertain_duration}\n' \
            + '  uncertain_time_delay={0.uncertain_time_delay}\n' \
            + '  uncertain_speed_scale={0.uncertain_speed_scale}\n' \
            + '  uncertain_angle_scale={0.uncertain_angle_scale}\n' \
            + "  uncertain_angle_units='{0.uncertain_angle_units}'\n" \
            + '  active_start time={1.active_start}\n' \
            + '  active_stop time={1.active_stop}\n' \
            + '  current on/off status={1.on}\n'
        return info.format(self, self)


class WindMover(WindMoversBase, serializable.Serializable):

    """
    Python wrapper around the Cython wind_mover module.
    This class inherits from CyMover and contains CyWindMover

    The real work is done by the CyWindMover object.  CyMover
    sets everything up that is common to all movers.

    In addition to base class array_types.basic, also use the
    array_types.windage dict since WindMover requires a windage array
    """
    state = copy.deepcopy(WindMoversBase.state)
    state.add(read=['wind_id'], create=['wind_id'])

    @classmethod
    def new_from_dict(cls, dict_):
        """
        define in WindMover and check wind_id matches wind

        invokes: super(WindMover,cls).new_from_dict(dict\_)
        """

        wind_id = dict_.pop('wind_id')
        if dict_.get('wind').id != wind_id:
            raise ValueError('id of wind object does not match the wind_id'\
                             ' parameter')
        return super(WindMover, cls).new_from_dict(dict_)

    def wind_id_to_dict(self):
        """
        used only for storing state so no wind_id_from_dict is defined. This
        is not a read/write attribute. Only defined for serializable_state
        """

        return self.wind.id

    def from_dict(self, dict_):
        """
        For updating the object from dictionary

        'wind' object is not part of the state since it is not serialized/
        deserialized; however, user can still update the wind attribute with a
        new Wind object. That must be poped out of the dict() here, then call
        super to process the standard dict\_
        """

        self.wind = dict_.pop('wind', self.wind)

        super(WindMover, self).from_dict(dict_)

    def __init__(self, wind, **kwargs):
        """
        Uses super to call CyMover base class __init__

        :param wind: wind object -- provides the wind time series for the mover

        Remaining kwargs are passed onto WindMoversBase __init__ using super.
        See Mover documentation for remaining valid kwargs.
        """

        self.mover = CyWindMover()
        self.wind = wind

        # set optional attributes
        super(WindMover, self).__init__(**kwargs)

    def __repr__(self):
        """
        .. todo::
            We probably want to include more information.
        """

        info = 'WindMover(\n{0})'.format(self._state_as_str())
        return info

    def __str__(self):
        info = \
            "WindMover - current state." \
            + " See 'wind' object for wind conditions:\n" \
            + "{0}".format(self._state_as_str())
        return info

    @property
    def wind(self):
        return self._wind

    @wind.setter
    def wind(self, value):
        if not isinstance(value, environment.Wind):
            raise TypeError('wind must be of type environment.Wind')
        else:
            # update reference to underlying cython object
            self._wind = value
            self.mover.set_ossm(self.wind.ossm)


def wind_mover_from_file(filename, **kwargs):
    """
    Creates a wind mover from a wind time-series file (OSM long wind format)

    :param filename: The full path to the data file
    :param **kwargs: All keyword arguments are passed on to the WindMover
                     constructor

    :returns mover: returns a wind mover, built from the file
    """

    w = environment.Wind(filename=filename,
                         ts_format=basic_types.ts_format.magnitude_direction)
    wm = WindMover(w, **kwargs)

    return wm


def constant_wind_mover(speed, direction, units='m/s'):
    """
    utility function to create a mover with a constant wind

    :param speed: wind speed
    :param direction: wind direction in degrees true
                  (direction from, following the meteorological convention)
    :param units='m/s': the units that the input wind speed is in.
                        options: 'm/s', 'knot', 'mph', others...


    :returns WindMover: returns a gnome.movers.WindMover object all set up.
    """

    series = np.zeros((1, ), dtype=basic_types.datetime_value_2d)

    # note: if there is ony one entry, the time is arbitrary

    series[0] = (datetime.now(), (speed, direction))
    wind = environment.Wind(timeseries=series, units=units)
    w_mover = WindMover(wind)
    return w_mover


class GridWindMover(WindMoversBase, serializable.Serializable):

    state = copy.deepcopy(WindMoversBase.state)
    state.add_field([serializable.Field('wind_file', create=True,
                    read=True, isdatafile=True),
                    serializable.Field('topology_file', create=True,
                    read=True, isdatafile=True)])

    def __init__(
        self,
        wind_file,
        topology_file=None,
        **kwargs
        ):
        """
        :param wind_file: file containing wind data on a grid
        :param topology_file: Default is None. When exporting topology, it
            is stored in this file

        Pass optional arguments to base class
        uses super: super(GridWindMover,self).__init__(**kwargs)
        """

        if not os.path.exists(wind_file):
            raise ValueError('Path for wind file does not exist: {0}'
                             .format(wind_file))

        if topology_file is not None:
            if not os.path.exists(topology_file):
                raise ValueError('Path for Topology file does not exist: {0}'
                                 .format(topology_file))

        # is wind_file and topology_file is stored with cy_gridwind_mover?
        self.wind_file = wind_file
        self.topology_file = topology_file
        self.mover = CyGridWindMover()
        super(GridWindMover, self).__init__(**kwargs)

        self.mover.text_read(wind_file, topology_file)

    def __repr__(self):
        """
        .. todo::
            We probably want to include more information.
        """

        info = 'GridWindMover(\n{0})'.format(self._state_as_str())
        return info

    def __str__(self):
        info = 'GridWindMover - current state.\n' \
            + "{0}".format(self._state_as_str())
        return info

    def export_topology(self, topology_file):
        """
        :param topology_file=None: absolute or relative path where topology
                                   file will be written.
        """

        if topology_file is None:
            raise ValueError('Topology file path required: {0}'.
                             format(topology_file))

        self.mover.export_topology(topology_file)
