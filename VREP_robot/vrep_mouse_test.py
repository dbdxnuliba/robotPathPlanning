
# coding: utf-8

# In[ ]:

import curses
from curses import wrapper

import transforms3d as t3d

import sys
sys.path.append("..")
import numpy as np
import time
import vrep
import spacenav

from vrepRobot import VREP_Environement, VREP_Robot
from utils.mouse3d import MouseClient


# In[ ]:


def main(stdscr):
	# Clear screen
	stdscr.clear()

	mouse = MouseClient()
	mouse.run()
	#mouse.stop()


	# In[ ]:
	vrep_env = VREP_Environement()

	#Adding robots to scene
	ik_handles = ['ik_joint1', 'ik_joint2', 'ik_joint3', 'ik_joint4', 'ik_joint5', 'ik_joint6', 'ik_joint7', 'ik_ee', 'kinematicsTest_IKTip', 'ik_rf7_static']
	vrep_env.add_robot(VREP_Robot('ik_robot', ik_handles))

	viz_handles = ['viz_joint1', 'viz_joint2', 'viz_joint3', 'viz_joint4', 'viz_joint5', 'viz_joint6', 'viz_joint7']
	vrep_env.add_robot(VREP_Robot('viz_robot', viz_handles))




	# In[ ]:
	initialPosition = [0.0,0.0,0.0]
	vrep_env.ik_robot.setObjectPosition(vrep_env.ik_robot.handles[7], initialPosition, relative2 = 'ik_rf7_static' )
	vrep_env.ik_robot.setObjectOrientation(vrep_env.ik_robot.handles[7], [0,0,0], relative2 = 'ik_rf7_static' )

	vrep_env.ik_robot.setObjectPosition(vrep_env.ik_robot.handles[8], initialPosition, relative2 = 'ik_rf7_static' )
	vrep_env.ik_robot.setObjectOrientation(vrep_env.ik_robot.handles[8], [0,0,0], relative2 = 'ik_rf7_static' )


	# In[ ]:
	#Add all robot before starting the simulation - once robots are added start simulation
	vrep_env.start_simulation()


	insertion_pos = vrep_env.ik_robot.getJointPosition(vrep_env.ik_robot.handles[-1])[1]

	# In[ ]:
	position = np.zeros(3)
	orientation = np.zeros(3)
	orientation_mat = np.eye(3)
	joint_data = [0,0,0,0,0,0,0]

	stdscr.nodelay(True)
	stdscr.addstr(0, 0, str(mouse.event[:]))

	mode = True

	while True:

		c = stdscr.getch()
		if c == ord('w'):
			insertion_pos += 0.001
		elif c == ord('s'):
			insertion_pos += - 0.001
		elif c == ord('r'):
			mode = not mode
		elif c == ord('q'):
			break  # Exit the while loop
		insertion_pos = np.clip(insertion_pos, 0, 5.5e-2)
		vrep_env.ik_robot.setJointPosition(vrep_env.ik_robot.handles[6], insertion_pos)

		if mode == True:
			stdscr.addstr(1,0,str('Position mode, press r to change'))
		else:
			stdscr.addstr(1,0,str('Orientation mode, press r to change'))

		#x,z,y,rx,rz,ry, meters and radians
		#0-500 regualr scaling on the mouse, max speed is 5 mm update
		#5 degs -> np.pi/180 * 5

		if mode:
			position[0] = position[0] + mouse.event[0] * .000001
			position[1] = position[1] + mouse.event[2] * .000001
			position[2] = position[2] + mouse.event[1] * .000001
		else:
			orientation[0] = 0.001 * mouse.event[4] * np.pi/180
			orientation[1] = 0.001 * mouse.event[3] * np.pi/180
			orientation[2] = -0.001 * mouse.event[5] * np.pi/180

		stdscr.addstr(10,0,str('Position 1: {:5}, Position 2: {:5}, Position 3: {:5}, Orientation 1: {:5}, Orientation 2: {:5}, Orientation 3: {:5}'.format(mouse.event[0], mouse.event[1], mouse.event[2], mouse.event[3],  mouse.event[4],  mouse.event[5])))

		position = np.clip(position, -0.5, 0.5)
		#orientation = np.clip(orientation, -np.pi/2, np.pi/2)

		position_reordered = np.array([-position[2], -position[0], position[1]])
		orientation_reordered = np.array([orientation[0], orientation[1], orientation[2]])

		orientation_mat = t3d.euler.euler2mat(orientation_reordered[0], orientation_reordered[1], orientation_reordered[2]).T @ orientation_mat
		orientation_quat = np.roll(t3d.quaternions.mat2quat(orientation_mat), -1)

		vrep_env.ik_robot.setObjectPosition(vrep_env.ik_robot.handles[7], position_reordered, relative2 = 'ik_rf7_static' )
		#vrep_env.ik_robot.setObjectOrientation(vrep_env.ik_robot.handles[7], orientation_reordered, relative2 = 'ik_rf7_static' )
		vrep_env.ik_robot.setObjectQuaternion(vrep_env.ik_robot.handles[7], orientation_quat, relative2 = 'ik_rf7_static' )

		for i in range(len(viz_handles)):
			joint_pos = vrep_env.ik_robot.getJointPosition(vrep_env.ik_robot.handles[i])[1]
			joint_data[i] = joint_pos
			stdscr.addstr(i+2, 0, "joint {}: {}".format(i+1,joint_pos))
			vrep_env.viz_robot.setJointPosition(vrep_env.viz_robot.handles[i], joint_pos)

		# Get the IK Jacobian
		res,retInts,retFloats,retStrings,retBuffer=vrep.simxCallScriptFunction(
			vrep_env.ik_robot.clientID,
			'ik_robot',
			vrep.sim_scripttype_childscript,
			'GetIkJacobian',
			[],    # inputIntsn
			[],    # inputFloats
			[],    # inputStrings
			'',    # inputBuffer
			vrep.simx_opmode_blocking
		)
		stdscr.addstr(11,0, 'Joint positions [meters, meters, radians, radians, radians, radians, meters]: ' + str(joint_data))
		stdscr.addstr(12,0, str(retInts))
		stdscr.addstr(13,0, str(retFloats[-1]))

		#stdscr.addstr(12,0,str(retInts))


		stdscr.refresh()

		time.sleep(0.01)

wrapper(main)
    

