#---------------------------------------------
#vrep imports
#---------------------------------------------
import numpy as np
import vrep
from forwardKinematics import robot_config
import time
import os
import pickle
import socket
import matplotlib.pyplot as plt
from copy import deepcopy
from getRobotPose import *
#---------------------------------------------
#motor imports
#---------------------------------------------
from motor_class import motors
from tcp_class import tcp_communication

#---------------------------------------------
#optitrak imports
#---------------------------------------------
import signal
import sys
import transforms3d as t3d
from copy import deepcopy
from GetJointData import data, NatNetFuncs#receiveNewFrame, receiveRigidBodyFrameList
from NatNetClient2 import NatNetClient
from AngleControl import MotorControl
from generate_trajectory import trajectoryGenerator

#---------------------------------------------
#constants
#---------------------------------------------
PI = np.pi
NUM_TESTS = 1
#TCP addresses
socket_ip = '192.168.1.39'
socket_port = 1124

#---------------------------------------------
#optitrak setup
#---------------------------------------------
server_ip = "192.168.1.27"
multicastAddress = "239.255.42.99"
print_trak_data = False
optitrack_joint_names = ['base', 'j2', 'j3', 'j4', 'target']
ids = [0, 1, 2, 3, 4]

#Tracking class
print("Starting streaming client now...")
streamingClient = NatNetClient(server_ip, multicastAddress, verbose = print_trak_data)
NatNet = NatNetFuncs()
streamingClient.newFrameListener = NatNet.receiveNewFrame
streamingClient.rigidBodyListListener = NatNet.receiveRigidBodyFrameList

prev_frame = 0
time.sleep(0.5)
streamingClient.run()
time.sleep(0.5)
track_data = data(optitrack_joint_names,ids)
track_data.parse_data(NatNet.joint_data, NatNet.frame) #updates the frame and data that is being used
old_frame = track_data.frame

#---------------------------------------------
#Helper functions
#---------------------------------------------
def rads2degs(radians):
	degrees = np.append(radians[0:-1] * 180/PI, radians[-1])
	return degrees

def degs2rads(degrees):
	radians = np.append(degrees[0:-1] * PI/180, degrees[-1])
	return radians

#---------------------------------------------
#robot kinematics, jacobian class
#---------------------------------------------
myRobot = robot_config()

#---------------------------------------------
#vrep setup
#---------------------------------------------
pose_names = ['pose_origin', 'pose_j1', 'pose_j2', 'pose_j3', 'pose_j4']
robot_pose_names = ['robot_origin', 'robot_j1', 'robot_j2', 'robot_j3', 'robot_j4', 'target']
n_poses = len(pose_names)

P=0.5#5#0.1#2.3
PL=0.1#0.2
I=1#0.1
IL = 0#0.01
D = 0

joint_motor_indexes = [0,1,2,3] #which motors are used to control the arm in order of joints

MC = MotorControl(P, PL ,I, IL, D,joint_motor_indexes)
MC.tcp_init(socket_ip, socket_port)
MC.motor_init()

print("Arming motors now...")
MC.motors.arm()
time.sleep(2)

#SET target angles/position here
arm_angles_deg = np.array((-15,5,5, 0)) 
arm_angles_rads = degs2rads(arm_angles_deg) #rads, rads, rads, meters for q

EE_position_fk = myRobot.Tx('EE', arm_angles_rads) * 10 # is the scaling facto rfor units
EE_orientation_fk = myRobot.Te('EE', arm_angles_rads)
print("Forward kin orientation", EE_orientation_fk)
print("Forward kin end effector position {} for joint values (euler and meters){}".format(EE_position_fk, arm_angles_deg))
time.sleep(1)

trajPlanner = trajectoryGenerator()


#---------------------------------------------
#Zeros the arm to home position
#---------------------------------------------
print("Zeroing arm")
MC.zero_arm(track_data, NatNet)
print("Done Zeroing")
time.sleep(0.5)


#Starting repeatability test:
#	goal_jointAngles is the end goal of each test
#	target_jointAngles is the current set point and generated by trajectoryGenerator()
#	current_jointAngles is the measured joint angle


#This is the list of target goals locations
goal_jointAngleList = [[-15,5, 5, 0.02], [5,-15, 5, 0.01], [5,5, -15, 0], [5,5, -15, 0.015]]
#goal_jointAngleList = [[-15,5, 5, 0.02]]

#Store joint angles and EE positions/orientations
measurements_time_all = []
measurements_jointAngles_all = []
measurements_EE_position_all = []
measurements_EE_orientation_all = []
goal_jointAngleList_output = []
target_jointAngles_all = []
target_jointAngles_time_all= []


#STARTING NUMBER FOR NAMING FOLDERS OF DATASET IS THIS
#
#
#
#
counter = 100

for i in range(3):

	for g_jointAngles in goal_jointAngleList:
		counter = counter + 1

		goal_jointAngles = np.array(g_jointAngles);
		goal_jointAngles = degs2rads(goal_jointAngles) 


		#Get current location
		track_data.parse_data(NatNet.joint_data, NatNet.frame) #updates the frame and data that is being used
		j2b_euler, j3j2_euler, j4j3_pos,  = getOptitrakControl(track_data)
		current_jointAngles = np.array([j2b_euler[0], j2b_euler[1], j3j2_euler[1], j4j3_pos[2]- 0.175]) #current angles in euler RADIANS
		base_inv = track_data.bodies[0].homg_inv
		joint4 = track_data.bodies[3].homogenous_mat
		_, EE_position_optitrak, EE_orientation_optitrak, _ = track_data.homg_mat_mult(base_inv,joint4)


		#Create trajectory from current joint angles to target joint angles
		period = 1.0/50.0 # 20 Hz
		rates = np.array([0.5*PI/180, 0.5*PI/180, 0.5*PI/180, 0.001])

		#current_jointAngles should be in meters from optitrak, hence goal_jointangles should match meters too it may not
		target_trajectories, target_trajectory_time = trajPlanner.creatTrajectoryMaxVelocity(current_jointAngles, goal_jointAngles, rates, period)

		#Store values for this repeatibility run:
		measurements_time = []
		measurements_jointAngles = []
		measurements_EE_position = []
		measurements_EE_orientation = []


		start_time = time.time()

		#Used to pring out progress time:
		old_time = time.time()


		#Follow trajectory
		while (time.time()-start_time) < 1.5 * target_trajectory_time[-1]: #looking at difference in degrees

			if time.time() - old_time > 0.5:
				print("total trajectory time: {}, current trajectory time: {}".format(target_trajectory_time[-1], time.time()-start_time))
				old_time = time.time()

			#---------------------------------------------
			#Update joint angles and end effector position
			#---------------------------------------------
			track_data.parse_data(NatNet.joint_data, NatNet.frame) #updates the frame and data that is being used
			j2b_euler, j3j2_euler, j4j3_pos,  = getOptitrakControl(track_data)
			current_jointAngles = np.array([j2b_euler[0], j2b_euler[1], j3j2_euler[1], j4j3_pos[2] - 0.175]) #current angles in euler RADIANS
			base_inv = track_data.bodies[0].homg_inv
			joint4 = track_data.bodies[3].homogenous_mat
			_, EE_position_optitrak, EE_orientation_optitrak, _ = track_data.homg_mat_mult(base_inv,joint4)

			#Time stamp measurement
			time_diff = time.time() - start_time

			#Get new jont set point/target joint angles
			index = np.argmin(np.abs(target_trajectory_time - time_diff))
			target_jointAngle = np.array((target_trajectories[0,index], target_trajectories[1,index], target_trajectories[2,index], target_trajectories[3,index]))


			current_jointAngles_MM = current_jointAngles.copy()
			current_jointAngles_MM[3] = current_jointAngles[3] * 1000

			target_jointAngle_MM = target_jointAngle.copy()
			target_jointAngle_MM[3] = target_jointAngle[3] * 2000
			#Set joint angle!!!!!!!!
			MC.update(current_jointAngles_MM, target_jointAngle_MM, print_data = True)

			#Save all measurements
			measurements_time.append(time_diff)
			measurements_jointAngles.append(current_jointAngles)
			measurements_EE_position.append(EE_position_optitrak)
			measurements_EE_orientation.append(EE_orientation_optitrak)


			time.sleep(0.01)


		#Figure to show the realtime measurements
		# fig, axis = plt.subplots(2,2)

		# tmp_numpyArray = np.array(measurements_jointAngles)

		# axis[0,0].clear()
		# axis[0,0].plot(measurements_time, tmp_numpyArray[:,0])
		# axis[0,0].plot(target_trajectory_time, target_trajectories[0,:])

		# axis[0,1].clear()
		# axis[0,1].plot(measurements_time, tmp_numpyArray[:,1])
		# axis[0,1].plot(target_trajectory_time, target_trajectories[1,:])


		# axis[1,0].clear()
		# axis[1,0].plot(measurements_time, tmp_numpyArray[:,2])
		# axis[1,0].plot(target_trajectory_time, target_trajectories[2,:])

		# axis[1,1].clear()
		# axis[1,1].plot(measurements_time, tmp_numpyArray[:,3])
		# axis[1,1].plot(target_trajectory_time, target_trajectories[3,:])


		# plt.show()


		#Save measurements from last repeatibility test
		os.mkdir('data_Florian/data{}'.format(counter))
		np.save('data_Florian/data{}/jointControl_measurement_times.npy'.format(counter), measurements_time)
		np.save('data_Florian/data{}/jointControl_measurement_jointAngles.npy'.format(counter), measurements_jointAngles)
		np.save('data_Florian/data{}/jointControl_measurement_EE_orientation.npy'.format(counter), measurements_EE_orientation)
		np.save('data_Florian/data{}/jointControl_measurement_EE_position.npy'.format(counter), measurements_EE_position)
		np.save('data_Florian/data{}/jointControl_goal_joint.npy'.format(counter), goal_jointAngles)
		np.save('data_Florian/data{}/jointControl_target_jointAngles.npy'.format(counter), target_trajectories)
		np.save('data_Florian/data{}/jointControl_target_jointAngles_time.npy'.format(counter), target_trajectory_time)


# 		measurements_time_all.append(measurements_time)
# 		measurements_jointAngles_all.append(measurements_jointAngles)
# 		measurements_EE_orientation_all.append(measurements_EE_orientation)
# 		measurements_EE_position_all.append(measurements_EE_position)
# 		goal_jointAngleList_output.append(goal_jointAngles)
# 		target_jointAngles_all.append(target_trajectories)
# 		target_jointAngles_time_all.append(target_trajectory_time)

# print("Saving Measurements")

# measurements_time_all = np.array(measurements_time_all)
# measurements_jointAngles_all = np.array(measurements_jointAngles_all)
# measurements_EE_orientation_all = np.array(measurements_EE_orientation_all)
# measurements_EE_position_all = np.array(measurements_EE_position_all)
# goal_jointAngleList_output = np.array(goal_jointAngleList_output)
# target_jointAngles_all = np.array(target_jointAngles_all)
# target_jointAngles_time_all = np.array(target_jointAngles_time_all)


# np.save('data_Florian/data1/jointControl_measurement_times.npy', measurements_time_all)
# np.save('data_Florian/data1/jointControl_measurement_jointAngles.npy', measurements_jointAngles_all)
# np.save('data_Florian/data1/jointControl_measurement_EE_orientation.npy', measurements_EE_orientation_all)
# np.save('data_Florian/data1/jointControl_measurement_EE_position.npy', measurements_EE_position_all)
# np.save('data_Florian/data1/jointControl_goal_joint.npy', goal_jointAngleList_output)
# np.save('data_Florian/data1/jointControl_target_jointAngles.npy', target_jointAngles_all)
# np.save('data_Florian/data1/jointControl_target_jointAngles_time.npy', target_jointAngles_time_all)




#---------------------------------------------
#Zeros the arm to home position
#---------------------------------------------
print("Zeroing arm")
MC.zero_arm(track_data, NatNet)
print("Done Zeroing")
time.sleep(0.5)

#---------------------------------------------
#Cleanup
#---------------------------------------------
print("Clean up")
MC.tcp_close()
streamingClient.stop()