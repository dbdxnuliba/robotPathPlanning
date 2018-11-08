import vrep
import numpy as np

class VREP_Environement():
    ''' This object defines a VREP environment '''
    def __init__(self, synchronous = False, dt = 0.05):
        self.dt = dt
        self.synchronous = synchronous
        self.robots_connected = 0
        self.robot_names = []
        self.handles_init = None
        self.clientID = None

        #Close any open connections
        vrep.simxFinish(-1)
        
        #Initiate connection to server
        self.connectToServer()

    def connectToServer(self):
        self.clientID = vrep.simxStart('127.0.0.1', 19997, True, True, 500, 5)
        
        if self.clientID != -1: # if we connected successfully
            print ('Connected to remote API server')
            
        #Setup synchronous mode or not
        if self.synchronous == True:
            print("In synchronous mode")
            vrep.simxSynchronous(self.clientID, True)

    def add_robot(self, robot_class):
        self.robots_connected = self.robots_connected + 1
        
        #Vrep env class stuff
        self.robot_names.append(robot_class.robot_name)
        
        #robot_class stuff
        robot_class.clientID = self.clientID
        robot_class.get_handles()
        
        #Add robot to class attributes
        setattr(self, robot_class.robot_name, robot_class)
        
    def start_simulation(self):
        if self.robots_connected == 0:
            print("no robots connected, simulation not started")
        else:
            # Set up streaming
            print("{} robot(s) connect: {}".format(self.robots_connected, self.robot_names))
            vrep.simxSetFloatingParameter(
                self.clientID,
                vrep.sim_floatparam_simulation_time_step,
                self.dt, # specify a simulation time stept
                vrep.simx_opmode_oneshot)
        
            # Start the simulation
            #vrep.simxStartSimulation(self.clientID,vrep.simx_opmode_blocking) #to increase loop speed mode is changed.
            vrep.simxStartSimulation(self.clientID,vrep.simx_opmode_oneshot_wait)


    def shutdown(self):
        vrep.simxStopSimulation(self.clientID, vrep.simx_opmode_oneshot)
        vrep.simxFinish(self.clientID)
class VREP_Robot():
    '''This object defines the robots in the environment'''
    def __init__(self, robot_name, handle_names, connection_type = 'nonblocking'):
        self.robot_name = robot_name
        self.handle_names = handle_names
        self.handles = None
        self.num_poses = len(handle_names) 
        self.positions = np.ones([self.num_poses,3]) #xyz
        self.orientations = np.ones([self.num_poses,4]) #xyzw
        self.connection_type = connection_type
        self.clientID = None
        
        #Connection type for object grabbing/setting
        if self.connection_type == 'blocking':
            self.opmode = vrep.simx_opmode_blocking
        elif self.connection_type == 'nonblocking':
            self.opmode = vrep.simx_opmode_oneshot
        
    def get_handles(self):
        self.handles = [vrep.simxGetObjectHandle(self.clientID,
            name, vrep.simx_opmode_blocking)[1] for name in self.handle_names]
        
    def setObjectPosition(self, object_name, cartesian_position):
        if self.clientID == None:
            print("Robot not attached to VREP environment")
        else:
            vrep.simxSetObjectPosition(
                self.clientID,
                object_name,
                -1,# Setting the absolute position
                position=cartesian_position,
                operationMode=self.opmode
                )
            
    def setObjectQuaternion(self, object_name, quaternion):
        if self.clientID == None:
            print("Robot not attached to VREP environment")
        else:
            vrep.simxSetObjectQuaternion(
                self.clientID,
                object_name,
                vrep.sim_handle_parent,# Setting the absolute position
                quaternion, #(x, y, z, w)
                operationMode = self.opmode
                )

    def getObjectPosition(self, object_name):
        if self.clientID == None:
            print("Robot not attached to VREP environment")
        else:
            cartesian_position = vrep.simxGetObjectPosition(
                self.clientID,
                object_name,
                -1,# Setting the absolute position
                operationMode = self.opmode
                )
        return cartesian_position
    
    def getObjectOrientation(self, object_name):
        if self.clientID == None:
            print("Robot not attached to VREP environment")
        else:
            quaternion = vrep.simxGetObjectQuaternion(
                self.clientID,
                object_name,
                -1,# Setting the absolute position
                operationMode = self.opmode
                )
        return quaternion