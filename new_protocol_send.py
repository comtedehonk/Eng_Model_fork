'''Created by Irvington Cubesat members Jerry Sun and Shreya Kolla'''
from pysquared import cubesat
# from functions import functions as f
import board
import busio
import digitalio
import traceback

# import time
import os
import asyncio
import json

import radio_diagnostics
from icpacket import Packet
from ftp import FileTransferProtocol as FTP

import camera_settings as cset



def verify_packet(packet, desired_type):
	# Verify that the packet has the desired type
	assert desired_type in Packet.packet_types, "Desired type is invalid"
	if packet.categorize() == desired_type:
		# print(f"Packet is of desired type {desired_type}")
		return True
	else:
		print(f"Packet is of undesired type {packet.categorize()}, not {desired_type}")
		return False

def save_settings(new_settings, camera_settings, cubesat):
	if set(new_settings) == set(camera_settings): # same keys
		camera_settings = new_settings
		with open("camera_settings.py", 'w') as new_settings:
			new_settings.write(f'camera_settings = {json.dumps(new_settings, indent=4)}')
		for k in camera_settings.keys():
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
	IMAGE_DIRECTORY = "test_images" # Change when the camera code is done
	IMAGE_COUNT_FILE = "image_count.txt" # Placeholder
	
	ftp = FTP(cubesat.ptp, chunk_size=CHUNK_SIZE, packet_delay=0, log=False)
	
	camera_settings = cset.camera_settings

	radio_diagnostics.report_diagnostics(cubesat.radio1)
	
	while True:
		try:
			print("Sending telemetry ping (handshake 1) and waiting for handshake 2")
			
			#creating telemetry payload
			t_payload = ["TEST", "TELEMETRY", "PAYLOAD"]
			# state_payload = functions.create_state_packet()
			# t_payload = functions.get_imu_data() #imu data
			# t_payload[0:0] = state_payload #combining state and imu data

			packet = Packet.make_handshake1(t_payload)
			await cubesat.ptp.send_packet(packet)
			packet = await cubesat.ptp.receive_packet()
			
			if not verify_packet(packet, "handshake2"):
				await asyncio.sleep(30)
				continue
				
			print("Handshake 2 received, sending handshake 3")
			
			# writing new camera settings
			if (packet.payload[1] is not None) and isinstance(packet.payload[1], dict):
				save_settings(packet.payload[1], camera_settings, cubesat)
			
			# setting new timeout
			if packet.payload[2] is not None:
				cubesat.ptp.timeout = packet.payload[2]
			
			# if requested, take picture
			if packet.payload[3]:
				image_path = await capture(cubesat)
			
			# Get number of images taken
			try:
				print(f"Note: make the camera code track image count in {IMAGE_COUNT_FILE}")
				with open(IMAGE_COUNT_FILE) as f:
					image_count = int(f.readline()) # one line with the image count
			except:
				print(f"Couldn't find {IMAGE_COUNT_FILE}, defaulting to 0")
				# image_count = len(os.listdir(IMAGE_DIRECTORY))
				image_count = 0
			
			packet = Packet.make_handshake3(image_count)
			await cubesat.ptp.send_packet(packet)
				
			# image_path = await capture(cubesat)

			# await cubesat.ftp.send_file(image_path)

			while True:
				print("Listening for requests")
				packet = await cubesat.ptp.receive_packet()
				if not verify_packet(packet, "file_req"):
					if verify_packet(packet, "file_del"):
						image_id = packet.payload_id
						try:
							# os.remove(f"{IMAGE_DIRECTORY}/image_{image_id}.jpeg")
							# print(f"Removed image with id: {image_id}")
							print(f"Would remove image with id: {image_id}, but testing")
						except:
							print(f"No image with id: {image_id} to be removed")
					else:
						asyncio.sleep(1)
						break
				
				# Get image with corresponding ID
				image_id = packet.payload_id
				image_path = f"{IMAGE_DIRECTORY}/image_{image_id}.jpeg" # PLACEHOLDER
				
				request = packet.payload[1]
				print(f"Request received for image {image_id}, {request}")
				
				if request == "all":
					# to do: send time taken
					await ftp.send_file(image_path, image_id)
				else:
					await ftp.send_partial_file(image_path, image_id, request)
			
			asyncio.sleep(1)

		except Exception as e:
			print("Error in Main Loop:", ''.join(traceback.format_exception(e)))

async def main():
	# functions = f(cubesat)
	await send(cubesat, None)
