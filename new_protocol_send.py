
import board
import busio
import digitalio
import traceback

import time
import os
import asyncio

import radio_diagnostics
from icpacket import Packet
from ftp import FileTransferProtocol as FTP

def verify_packet(packet, desired_type):
	# Verify that the packet has the desired type
	assert desired_type in Packet.packet_types, "Desired type is invalid"
	if packet.categorize() == desired_type:
		# print(f"Packet is of desired type {desired_type}")
		return True
	else:
		print(f"Packet is of undesired type {packet.categorize()}, not {desired_type}")
		return False

async def send(cubesat, t_payload):
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
	
	ftp = FTP(cubesat.ptp, chunk_size=CHUNK_SIZE, packet_delay=0, log=False)
	
	radio_diagnostics.report_diagnostics(cubesat.radio1)
	
	while True:
		try:
			print("Sending telemetry ping (handshake 1) and waiting for handshake 2")
			packet = Packet.make_handshake1(t_payload)
			await cubesat.ptp.send_packet(packet)
			packet = await cubesat.ptp.receive_packet()
			if not verify_packet(packet, "handshake2"):
				continue
				
			print("Handshake 2 received, sending handshake 3")
			
			# Get number of images taken
			image_count = len(os.listdir("test_images")) # PLACEHOLDER
			packet = Packet.make_handshake3(image_count)
			await cubesat.ptp.send_packet(packet)
			
			while True:
				print("Listening for requests")
				packet = await cubesat.ptp.receive_packet()
				if not verify_packet(packet, "file_req"):
					break
				
				# Get image with corresponding ID
				image_id = packet.payload_id
				image_path = f"test_images/test_image_{image_id}.jpeg" # PLACEHOLDER
				
				request = packet.payload[1]
				print(f"Request received for image {image_id}, {request}")
				
				if request == "all":
					# to do: send time taken
					await ftp.send_file(image_path, image_id)
				else:
					await ftp.send_partial_file(image_path, image_id, request)
		
		except Exception as e:
			print("Error in Main Loop:", ''.join(traceback.format_exception(e)))


