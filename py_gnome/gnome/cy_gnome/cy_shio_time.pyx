import numpy as np
import os

cimport numpy as cnp
from libc.string cimport memcpy

from gnome import basic_types

from type_defs cimport *
from utils cimport (ShioTimeValue_c,
                    EbbFloodData, EbbFloodDataH,
                    HighLowData, HighLowDataH,
                    _NewHandle, _GetHandleSize)

from cy_helpers cimport to_bytes

cdef class CyShioTime(object):
    """
    Cython wrapper around instantiating and using ShioTimeValue_c object

    The object is declared in cy_shio_time.pxd file
    """
    def __cinit__(self):
        """ Initialize object """
        self.shio = new ShioTimeValue_c()

    def __dealloc__(self):
        del self.shio

    def __init__(self,
                 path_,
                 daylight_savings_off=True,
                 scale_factor=1):
        """
        Init CyShioTime with defaults
        """
        cdef bytes file_
        self.shio.daylight_savings_off = daylight_savings_off

        if os.path.exists(path_):
            path_= os.path.normpath(path_)
            file_ = to_bytes(unicode(path_))
            err = self.shio.ReadTimeValues(file_)
            if err != 0:
                raise ValueError("File could not be correctly read by ShioTimeValue_c.ReadTimeValues(...)")

            # also set user_units for base class to -1 (undefined). For Shio, the units don't matter since it returns
            # the values by which the currents should be scaled
            self.shio.SetUserUnits(-1)
            self.scale_factor = scale_factor

        else:
            raise IOError("No such file: " + path_)

    def set_shio_yeardata_path(self, yeardata_path_):
        """
        .. function::set_shio_yeardata_path
        C++ expects a trailing slash at the end of yeardata_path,
        this is explicitly added here
        """
        cdef OSErr err
        cdef bytes yeardata_path

        yeardata_path = to_bytes(unicode(yeardata_path_))

        if os.path.exists(yeardata_path):
            if yeardata_path[-1] != os.sep:
                yeardata_path = os.path.normpath(yeardata_path) + os.sep
            err = self.shio.SetYearDataPath(yeardata_path)  # implicit conversion from bytes to char *
            if err != 0:
                raise ValueError("Path could not be correctly be set by ShioTimeValue_c.SetYearDataPath(...)")
        else:
            raise IOError("No such file: " + yeardata_path)

    property daylight_savings_off:
        def __get__(self):
            return self.shio.daylight_savings_off

        def __set__(self, bool value):
            self.shio.daylight_savings_off = value

    property filename:
        def __get__(self):
            """
            returns full path plus file name for the shio filename
            """
            return <bytes>self.shio.filePath

    property scale_factor:
        """ shio scale_factor """
        def __get__(self):
            return self.shio.fScaleFactor

        def __set__(self, value):
            self.shio.fScaleFactor = value

    property yeardata:
        def __get__(self):
            """ get path of yeardata files """
            return <bytes>self.shio.fYearDataPath

        def __set__(self, value):
            """ set path of yeardata files """
            self.set_shio_yeardata_path(value)  # todo: figure out how to change fYearDataPath directly

    property station_location:
        def __get__(self):
            """ get station location as read from file """
            cdef cnp.ndarray[WorldPoint, ndim = 1] wp
            wp = np.zeros((1,), dtype=basic_types.w_point_2d)

            wp[0] = self.shio.GetStationLocation()
            wp['lat'][:] = wp['lat'][:] / 1.e6    # correct C++ scaling here
            wp['long'][:] = wp['long'][:] / 1.e6    # correct C++ scaling here

            g_wp = np.zeros((1,), dtype=basic_types.world_point) 
            g_wp[0] = (wp['long'], wp['lat'],0)

            return tuple(g_wp[0])

    property station:
        def __get__(self):
            """ get station name as read from SHIO file """
            cdef bytes sName
            sName = self.shio.fStationName
            return sName

    property station_type:
        def __get__(self):
            """ station type: 'C', 'H', 'P' - not sure what these refer to yet? """
            cdef bytes sType
            sType = self.shio.fStationType
            return sType

    def __repr__(self):
        """
        Return an unambiguous representation of this object so it can be recreated 
        """
        # Tried the following, but eval(repr( obj_instance)) would not work on it so updated it to hard code the class name
        # '{0.__class__}( "{0.filename}", daylight_savings_off={1})'.format(self, self.shio.daylight_savings_off)
        return 'CyShioTime( "{0.filename}", daylight_savings_off={1})'.format(self, self.shio.daylight_savings_off)

    def __str__(self):
        """Return string representation of this object"""
        """info = {'Long': round(g_wp[0]['long'], 2),'Lat': round( g_wp[0]['lat'], 2),
                'StationName': sName, 'StationType': sType,
                'DaylightSavingsOff': self.shio.daylight_savings_off}"""

        info = "CyShioTime object - Info read from file:\n  File: {1.filename} \n  StationName : {0[StationName]},  StationType : {0[StationType]}\n  (Long, Lat) : ({0[Long]}, {0[Lat]})\n  DaylightSavingsOff : {0[DaylightSavingsOff]}".format(self.get_info(),self)

        return info

    def get_time_value(self, modelTime):
        """
        GetTimeValue - for a specified modelTime or array of model times, it computes
        the values for the tides
        """
        cdef cnp.ndarray[Seconds, ndim = 1] modelTimeArray
        modelTimeArray = np.asarray(modelTime, basic_types.seconds).reshape((-1,))

        # velocity record passed to OSSMTimeValue_c methods and returned back to python
        cdef cnp.ndarray[VelocityRec, ndim = 1] vel_rec 
        cdef VelocityRec * velrec

        cdef unsigned int i
        cdef OSErr err

        vel_rec = np.empty((modelTimeArray.size,), dtype=basic_types.velocity_rec)

        for i in range(0, modelTimeArray.size):
            err = self.shio.GetTimeValue( modelTimeArray[i], &vel_rec[i])
            if err != 0:
                raise ValueError("Error invoking ShioTimeValue_c.GetTimeValue method in CyShioTime: C++ OSERR = " + str(err))

        return vel_rec

    def get_ebb_flood(self, modelTime):
        """
        Return ebb flood data for specified modelTime
        """
        self.get_time_value(modelTime)  # initialize self.shio.fEbbFloodDataHdl for specified duration
        cdef short tmp_size = sizeof(EbbFloodData)
        cdef cnp.ndarray[EbbFloodData, ndim = 1] ebb_flood

        if self.shio.fStationType == 'C':
            sz = _GetHandleSize(<Handle>self.shio.fEbbFloodDataHdl)  # allocate memory and copy it over
            ebb_flood = np.empty((sz / tmp_size,), dtype=basic_types.ebb_flood_data)
            memcpy(&ebb_flood[0], self.shio.fEbbFloodDataHdl[0], sz)
            return ebb_flood
        else:
            return 0

    def get_high_low(self, modelTime):
        """
        Return high and low tide data for specified modelTime
        """
        self.get_time_value(modelTime)  # initialize self.shio.fEbbFloodDataHdl for specified duration
        cdef short tmp_size = sizeof(HighLowData)
        cdef cnp.ndarray[HighLowData, ndim = 1] high_low

        if self.shio.fStationType == 'H':
            self.get_time_value(modelTime)  # initialize self.shio.fEbbFloodDataHdl for specified duration
            sz = _GetHandleSize(<Handle>self.shio.fHighLowDataHdl)  # allocate memory and copy it over
            high_low = np.empty((sz / tmp_size,), dtype=basic_types.ebb_flood_data)

            memcpy(&high_low[0], self.shio.fHighLowDataHdl[0], sz)
            return high_low
        else:
            return 0
