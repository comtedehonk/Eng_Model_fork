'''Created by Irvington Cubesat members Jerry Sun and Shreya Kolla'''

import board
import busio
import digitalio
import traceback

import time
import os
import asyncio
import json

import radio_diagnostics
from icpacket import Packet


import camera_settings

camera_settings = camera_settings.camera_settings


def verify_packet(packet, desired_type):
	# Verify that the packet has the desired type
	assert desired_type in Packet.packet_types, "Desired type is invalid"
	if packet.categorize() == desired_type:
		# print(f"Packet is of desired type {desired_type}")
		return True
	else:
		print(f"Packet is of undesired type {packet.categorize()}, not {desired_type}")
		return False

def save_settings(new_settings,cubesat):
	old_keys = camera_settings.keys()
	old_keys.sort()
	new_keys = new_settings.keys()
	new_keys.sort()
	if old_keys == new_keys:
		camera_settings = new_settings
		with open("camera_settings.py", 'w') as new_settings:
			new_settings.write(f'camera_settings = {json.dumps(new_settings, indent=4)}')
		for k in old_keys:
   			setattr(cubesat.cam, k, camera_settings[k])
	else:
		print("received dictionary was corrupted")


async def capture(cubesat):
	pass #returns path of best image


async def send(cubesat, functions):
	print("Irvington CubeSat's Test Satellite Board")
	
	# Constants
	# Chip's buffer size: 256 bytes
	# pycubed_rfm9x header size: 4 bytes
	# pycubed_rfm9x CRC16 checksum size: 2 bytes (DOES NOT take away from available bytes)
	# ptp header size: 6 bytes
	# max length packets are bugged (-1 byte)
	MAX_PAYLOAD_SIZE = 256 - 4 - 6 - 1 # 245
	# msgpack adds 2 bytes overhead for bytes payloads
	CHUNK_SIZE = MAX_PAYLOAD_SIZE - 2 # 243
	TEST_IMAGE_PATH = "THBBlueEarthTest.jpeg"
	
	radio_diagnostics.report_diagnostics(cubesat.radio1)
	
	while True:
		try:
			print("Sending telemetry ping (handshake 1) and waiting for handshake 2")
			
			#creating telemetry payload
			state_payload = functions.create_state_packet()
			t_payload = functions.get_imu_data() #imu data
			t_payload[0:0] = state_payload #combining state and imu data

			packet = Packet.make_handshake1(t_payload)
			await cubesat.ptp.send_packet(packet)
			packet = await cubesat.ptp.receive_packet()
			
			if not verify_packet(packet, "handshake2"): #add partial request
				await asyncio.sleep(30)
				continue
				
			print("Handshake 2 received, sending handshake 3")
			
			#writing new camera settings
			if packet.payload[1] != -1 and isinstance(packet.payload[1], dict):
				save_settings(packet.payload[1], cubesat)
				
			image_path = await capture(cubesat)

			await cubesat.ftp.send_file(image_path)

			while True:
				print("Listening for requests")
				packet = await cubesat.ptp.receive_packet()
				if not verify_packet(packet, "file_req"):
					break

				request = packet.payload[1]
				print(f"Request received for image {request}")
				
				if request == "all":
					# to do: send time taken
					await cubesat.ftp.send_file(image_path)
				else:
					await cubesat.ftp.send_partial_file(image_path, request)
			
			asyncio.sleep(1)

		except Exception as e:
			print("Error in Main Loop:", ''.join(traceback.format_exception(e)))


