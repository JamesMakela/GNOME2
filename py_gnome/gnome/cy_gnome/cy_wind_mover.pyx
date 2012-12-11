import cython
cimport numpy as cnp
import numpy as np
from gnome.cy_gnome.cy_ossm_time cimport CyOSSMTime
from gnome import basic_types

from movers cimport WindMover_c
from type_defs cimport WorldPoint3D, LEWindUncertainRec, LEStatus, LEType, OSErr, Seconds, VelocityRec

cdef class CyWindMover:

    cdef WindMover_c *mover
    
    # Let's define the following - it is only used for testing
    def __cinit__(self):
        self.mover = new WindMover_c()
        
    def __dealloc__(self):
        del self.mover
    
    def __init__(self, uncertain_duration=10800, uncertain_time_delay=0,
                 uncertain_speed_scale=2, uncertain_angle_scale=0.4):
        """
        .. function:: __init__(self, uncertain_duration=10800, uncertain_time_delay=0,
                 uncertain_speed_scale=2, uncertain_angle_scale=0.4)
        
        initialize a constant wind mover
        
        :param uncertain_duation: time in seconds after which the uncertainty values are updated
        :param uncertain_time_delay: wait this long after model_start_time to turn on uncertainty
        :param uncertain_speed_scale: used in uncertainty computation
        :param uncertain_angle_scale: used in uncertainty computation
        
        constant_wind_value is a tuple of values: (u, v)
        """
        self.mover.fIsConstantWind  = 1  # Assume wind is constant, but initialize velocity to 0.
        self.mover.fConstantValue.u = 0
        self.mover.fConstantValue.v = 0
        self.mover.fDuration = uncertain_duration
        self.mover.fUncertainStartTime = uncertain_time_delay
        self.mover.fSpeedScale = uncertain_speed_scale
        self.mover.fAngleScale = uncertain_angle_scale
        
    property uncertain_duration:
        def __get__(self):
            return self.mover.fDuration
        
        def __set__(self,value):
            self.mover.fDuration = value
    
    property uncertain_time_delay:
        def __get__(self):
            return self.mover.fUncertainStartTime
        
        def __set__(self, value):
            self.mover.fUncertainStartTime = value
    
    property uncertain_speed_scale:
        def __get__(self):
            return self.mover.fSpeedScale
        
        def __set__(self, value):
            self.mover.fSpeedScale = value
    
    property uncertain_angle_scale:
        def __get__(self):
            return self.mover.fAngleScale
        
        def __set__(self, value):
            self.mover.fAngleScale = value
        
    
    def prepare_for_model_run(self):
        """
        .. function::prepare_for_model_run
        
        """
        self.mover.PrepareForModelRun()
        
    def prepare_for_model_step(self, model_time, step_len, numSets=0, cnp.ndarray[cnp.npy_int] setSizes=None):
        """
        .. function:: prepare_for_model_step(self, model_time, step_len, uncertain)
        
        prepares the mover for time step, calls the underlying C++ mover objects PrepareForModelStep(..)
        
        :param model_time: current model time.
        :param step_len: length of the time step over which the get move will be computed
        """
        cdef OSErr err
        if numSets == 0:
            err = self.mover.PrepareForModelStep(model_time, step_len, False, 0, NULL)
        else:
            err = self.mover.PrepareForModelStep(model_time, step_len, True, numSets, <int *>&setSizes[0])
            
        if err != 0:
            """
            For now just raise an OSError - until the types of possible errors are defined and enumerated
            """
            raise OSError("WindMover_c.PreareForModelStep returned an error.")

    def model_step_is_done(self):
        """
        invoke C++ model step is done functionality
        """
        self.mover.ModelStepIsDone()

    def get_move(self,
                 model_time,
                 step_len,
                 cnp.ndarray[WorldPoint3D, ndim=1] ref_points,
                 cnp.ndarray[WorldPoint3D, ndim=1] delta,
                 cnp.ndarray[cnp.npy_double] windages,
                 cnp.ndarray[cnp.npy_int16] LE_status,    # TODO: would be nice if we could define this as LEStatus type
                 LEType spill_type,
                 spill_ID):
        """
        .. function:: get_move(self,
                 model_time,
                 step_len,
                 cnp.ndarray[WorldPoint3D, ndim=1] ref_points,
                 cnp.ndarray[WorldPoint3D, ndim=1] delta,
                 cnp.ndarray[cnp.npy_double] windages,
                 cnp.ndarray[cnp.npy_int16] LE_status,
                 LE_type,
                 spill_ID)
                 
        Invokes the underlying C++ WindMover_c.get_move(...)
        
        :param model_time: current model time
        :param step_len: step length over which delta is computed
        :param ref_points: current locations of LE particles
        :type ref_points: numpy array of WorldPoint3D
        :param delta: the change in position of each particle over step_len
        :type delta: numpy array of WorldPoint3D
        :param LE_windage: windage to be applied to each particle
        :type LE_windage: numpy array of numpy.npy_int16
        :param le_status: status of each particle - movement is only on particles in water
        :param spill_type: LEType defining whether spill is forecast or uncertain 
        :returns: none
        """
        cdef OSErr err
        N = len(ref_points) # set a data type?
        
        # modifies delta in place
        err = self.mover.get_move(N,
                                  model_time,
                                  step_len,
                                  &ref_points[0],
                                  &delta[0],
                                  &windages[0],
                                  <short *>&LE_status[0],
                                  spill_type,
                                  spill_ID)
        if err == 1:
            raise ValueError("Make sure numpy arrays for ref_points, delta and windages are defined")
        
        """
        Can probably raise this error before calling the C++ code - but the C++ also throwing this error
        """
        if err == 2:
            raise ValueError("The value for spill type can only be 'forecast' or 'uncertainty' - you've chosen: " + str(spill_type))
        

    def set_constant_wind(self,windU,windV):
    
        self.mover.fConstantValue.u = windU
        self.mover.fConstantValue.v = windV
        self.mover.fIsConstantWind = 1
        
    def set_ossm(self, CyOSSMTime ossm):
        """
        Use the CyOSSMTime object to set the wind mover OSSM time member variable using
        the SetTimeDep method
        """
        self.mover.SetTimeDep(ossm.time_dep)
        self.mover.fIsConstantWind = 0
        return True
   
    def get_time_value(self, modelTime):
        """
        GetTimeValue - for a specified modelTime or array of model times, it returns the wind velocity
        values
        """
        cdef cnp.ndarray[Seconds, ndim=1] modelTimeArray
        modelTimeArray = np.asarray(modelTime, basic_types.seconds).reshape((-1,))
         
        # velocity record passed to the methods and returned back to python
        cdef cnp.ndarray[VelocityRec, ndim=1] vel_rec 
        cdef VelocityRec * velrec
        
        cdef unsigned int i 
        cdef OSErr err 
        
        vel_rec = np.empty((modelTimeArray.size,), dtype=basic_types.velocity_rec)
        
        for i in range( 0, modelTimeArray.size):
           err = self.mover.GetTimeValue( modelTimeArray[i], &vel_rec[i])
           if err != 0:
               raise ValueError
        
        return vel_rec