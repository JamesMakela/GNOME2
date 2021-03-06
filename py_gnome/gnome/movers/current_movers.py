'''
Movers using currents and tides as forcing functions
'''

import os
import copy
from datetime import datetime, timedelta

from gnome.movers import CyMover
from gnome import environment
from gnome.utilities import serializable
from gnome.cy_gnome import cy_cats_mover, cy_shio_time, cy_ossm_time, \
    cy_gridcurrent_mover


class CatsMover(CyMover, serializable.Serializable):

    state = copy.deepcopy(CyMover.state)

    _update = ['scale', 'scale_refpoint', 'scale_value']
    _create = ['tide_id']
    _create.extend(_update)
    state.add(update=_update, create=_create, read=['tide_id'])
    state.add_field(serializable.Field('filename', create=True,
                    read=True, isdatafile=True))

    @classmethod
    def new_from_dict(cls, dict_):
        """
        define in WindMover and check wind_id matches wind
        
        invokes: super(WindMover,cls).new_from_dict(dict_)
        """

        if 'tide' in dict_:
            try:
                if dict_.get('tide').id != dict_.pop('tide_id'):
                    raise ValueError('id of tide object does not match the tide_id parameter'
                            )
            except KeyError, ex:
                ex.args = \
                    ("Found 'tide' in dict but no '{0}' key".format(ex.args[0]),
                     )
                raise ex

        return super(CatsMover, cls).new_from_dict(dict_)

    def __init__(
        self,
        filename,
        tide=None,
        **kwargs
        ):
        """
        Uses super to invoke base class __init__ method. 
        
        :param filename: file containing currents patterns for Cats 
        
        Optional parameters (kwargs). Defaults are defined by CyCatsMover object.
        
        :param tide: a gnome.environment.Tide object to be attached to CatsMover
        :param scale: a boolean to indicate whether to scale value at reference point or not
        :param scale_value: value used for scaling at reference point
        :param scale_refpoint: reference location (long, lat, z). The scaling applied to all data is determined by scaling the 
                               raw value at this location.
        
        Remaining kwargs are passed onto Mover's __init__ using super. 
        See Mover documentation for remaining valid kwargs.
        """

        if not os.path.exists(filename):
            raise ValueError('Path for Cats filename does not exist: {0}'.format(filename))

        self.filename = filename  # check if this is stored with cy_cats_mover?
        self.mover = cy_cats_mover.CyCatsMover()
        self.mover.text_read(filename)

        self._tide = None
        if tide is not None:
            self.tide = tide

        self.scale = kwargs.pop('scale', self.mover.scale_type)
        self.scale_value = kwargs.get('scale_value',
                self.mover.scale_value)

        # todo: no need to check for None since properties that are None are not persisted

        if 'scale_refpoint' in kwargs:
            self.scale_refpoint = kwargs.pop('scale_refpoint')

        if self.scale and self.scale_value != 0.0 \
            and self.scale_refpoint is None:
            raise TypeError("Provide a reference point in 'scale_refpoint'."
                            )

        super(CatsMover, self).__init__(**kwargs)

    def __repr__(self):
        """
        unambiguous representation of object
        """

        info = 'CatsMover(filename={0})'.format(self.filename)
        return info

    # Properties

    scale = property(lambda self: bool(self.mover.scale_type),
                     lambda self, val: setattr(self.mover, 'scale_type'
                     , int(val)))
    scale_refpoint = property(lambda self: self.mover.ref_point,
                              lambda self, val: setattr(self.mover,
                              'ref_point', val))

    scale_value = property(lambda self: self.mover.scale_value,
                           lambda self, val: setattr(self.mover,
                           'scale_value', val))

    # a test case for colander.drop
    # ===========================================================================
    # def scale_refpoint_to_dict(self):
    #     if self.scale_refpoint is None:
    #         return (None, None, None)
    # ===========================================================================

    def tide_id_to_dict(self):
        if self.tide is None:
            return None
        else:
            return self.tide.id

    @property
    def tide(self):
        return self._tide

    @tide.setter
    def tide(self, tide_obj):
        if not isinstance(tide_obj, environment.Tide):
            raise TypeError('tide must be of type environment.Tide')

        if isinstance(tide_obj.cy_obj, cy_shio_time.CyShioTime):
            self.mover.set_shio(tide_obj.cy_obj)
        elif isinstance(tide_obj.cy_obj, cy_ossm_time.CyOSSMTime):
            self.mover.set_ossm(tide_obj.cy_obj)
        else:
            raise TypeError('Tide.cy_obj attribute must be either CyOSSMTime or CyShioTime type for CatsMover.'
                            )

        self._tide = tide_obj

    def from_dict(self, dict_):
        """
        For updating the object from dictionary
        
        'tide' object is not part of the state since it is not serialized/deserialized;
        however, user can still update the tide attribute with a new Tide object. That must
        be poped out of the dict here, then call super to process the standard dict_
        """

        if 'tide' in dict_ and dict_.get('tide') is not None:
            self.tide = dict_.pop('tide')

        super(CatsMover, self).from_dict(dict_)


class GridCurrentMover(CyMover, serializable.Serializable):

    _update = ['uncertain_duration', 'uncertain_time_delay',
               'uncertain_cross', 'uncertain_along', 'current_scale']
    state = copy.deepcopy(CyMover.state)

    state.add(update=_update)
    state.add_field([serializable.Field('filename', create=True,
                    read=True, isdatafile=True),
                    serializable.Field('topology_file', create=True,
                    read=True, isdatafile=True)])

    def __init__(
        self,
        filename,
        topology_file=None,
#         current_scale=1,
#         uncertain_duration=timedelta(hours=24),
#         uncertain_time_delay=timedelta(hours=0),
#         uncertain_along=0.5,
#         uncertain_cross=.25,
        **kwargs
        ):
        """
        Initialize a GridCurrentMover

        :param filename: absolute or relative path to the data file: could be netcdf or filelist
        :param topology_file=None: absolute or relative path to topology file. If not given, the
                                   GridCurrentMover will copmute the topology from the data file.
        :param active_start: datetime when the mover should be active
        :param active_stop: datetime after which the mover should be inactive
        :param current_scale: Value to scale current data
        :param uncertain_duration: how often does a given uncertain element gets reset
        :param uncertain_time_delay: when does the uncertainly kick in.
        :param uncertain_cross: Scale for uncertainty perpendicular to the flow
        :param uncertain_along: Scale for uncertainty parallel to the flow

        uses super: super(GridCurrentMover,self).__init__(**kwargs)
        """

        # # NOTE: will need to add uncertainty parameters and other dialog fields
        # #       use super with kwargs to invoke base class __init__

        if not os.path.exists(filename):
            raise ValueError('Path for current file does not exist: {0}'.format(filename))

        if topology_file is not None:
            if not os.path.exists(topology_file):
                raise ValueError('Path for Topology file does not exist: {0}'.format(topology_file))

        self.filename = filename  # check if this is stored with cy_gridcurrent_mover?
        self.topology_file = topology_file  # check if this is stored with cy_gridcurrent_mover?
        #self.mover = cy_gridcurrent_mover.CyGridCurrentMover()
        self.mover = \
        cy_gridcurrent_mover.CyGridCurrentMover(current_scale=kwargs.pop('current_scale', 1),
             uncertain_duration=3600.*kwargs.pop('uncertain_duration', 24),
             uncertain_time_delay=3600.*kwargs.pop('uncertain_time_delay', 0),
             uncertain_along=kwargs.pop('uncertain_along', 0.5),
             uncertain_cross=kwargs.pop('uncertain_cross', 0.25))

        self.mover.text_read(filename, topology_file)

        super(GridCurrentMover, self).__init__(**kwargs)

    def __repr__(self):
        """
        .. todo::
            We probably want to include more information.
        """

        info = \
            'GridCurrentMover( uncertain_duration={0.uncertain_duration},' \
            + 'uncertain_time_delay={0.uncertain_time_delay}, '\
            + 'uncertain_cross={0.uncertain_cross}, ' \
            + 'uncertain_along={0.uncertain_along}, '\
            + 'active_start={1.active_start}, active_stop={1.active_stop}, '\
            + 'on={1.on})'
        return info.format(self.mover, self)

    def __str__(self):
        info = 'GridCurrentMover - current state.\n' \
            + '  uncertain_duration={0.uncertain_duration}\n' \
            + '  uncertain_time_delay={0.uncertain_time_delay}\n' \
            + '  uncertain_cross={0.uncertain_cross}\n' \
            + '  uncertain_along={0.uncertain_along}' \
            + '  active_start time={1.active_start}' \
            + '  active_stop time={1.active_stop}' \
            + '  current on/off status={1.on}'
        return info.format(self.mover, self)


    # Define properties using lambda functions: uses lambda function, which are
    #accessible via fget/fset as follows:
    uncertain_duration = property(lambda self: \
                                  self.mover.uncertain_duration/3600.,
                                  lambda self, val: setattr(self.mover,
                                  'uncertain_duration', val*3600.))

    uncertain_time_delay = property(lambda self: \
                                    self.mover.uncertain_time_delay/3600.,
                                    lambda self, val: \
                                    setattr(self.mover,
                                    'uncertain_time_delay', val*3600.))

    uncertain_cross = property(lambda self: \
            self.mover.uncertain_cross, lambda self, val: \
            setattr(self.mover, 'uncertain_cross', val))

    uncertain_along = property(lambda self: \
            self.mover.uncertain_along, lambda self, val: \
            setattr(self.mover, 'uncertain_along', val))

    current_scale = property(lambda self: \
            self.mover.current_scale, lambda self, val: \
            setattr(self.mover, 'current_scale', val))

    def export_topology(self, topology_file):
        """
        :param topology_file=None: absolute or relative path where topology file will be written.
        """

        if topology_file is None:
            raise ValueError('Topology file path required: {0}'.format(topology_file))

        self.mover.export_topology(topology_file)


