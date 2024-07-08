'''Created by Irvington Cubesat members Jerry Sun and Shreya Kolla'''
# from pysquared import cubesat
# from functions import functions as f
# import board
# import busio
# import digitalio
from traceback import format_exception

# import time
from os import listdir, remove, stat, mkdir, getcwd, rmdir, rename
from asyncio import sleep
from json import dumps
from gc import mem_free, collect

from radio_diagnostics import report_diagnostics
from icpacket import Packet

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

async def save_settings(new_settings, camera_settings, cubesat):
	# old_keys = camera_settings.keys()
	# old_keys.sort()
	# new_keys = new_settings.keys()
	# new_keys.sort()
	if set(new_settings) == set(camera_settings): # same keys
		camera_settings = new_settings
		with open("camera_settings.py", 'w') as new_settings:
			new_settings.write(f'camera_settings = {dumps(new_settings)}')
		for k in camera_settings:
   			setattr(cubesat.cam, k, camera_settings[k])
	else:
		print("received dictionary was corrupted")


def captureSingle(cam, buf, folder, name):
    print("ok: capturing test photo")
    try:
        cam.capture(buf)
    except Exception as e:
        print("error:", e)
        return
    print(f"ok: saving test photo to images/{folder}/{name}.jpeg")
    eoi = buf.find(
        b"\xff\xd9"
    )  # this can false positive, parse the jpeg for better results
    # print("ok: eoi marker (possibly inaccurate):", eoi)
    if eoi == -1:
        print("warn: IMAGE IS PROBABLY TRUNCATED")
    print(memoryview(buf).hex())
    #print(memoryview(buf)[: eoi + 2].hex())
    try:
        mkdir("images")
    except:
        print("Image Folder Exists")
    try:
        mkdir(f"images/{folder}")
    except:
        print(f"Folder {folder} Exists")
    # print(buf)
    with open(f"images/{folder}/{name}.jpeg", "wb") as photo_file:
        photo_file.write(buf[: eoi + 2])
        
    print("ok: done saving,")
    buf = bytearray(cam.buffer_size)
    

def sortThroughDir(dir):
    # Maps through dir to return sorted list of touples of name and file size
    l = sorted(
        list(
            map(
                lambda f: (
                    f,
                    stat(getcwd() + "/" + dir + "/" + f)[6],
                ),
                listdir(dir),
            )
        ),
        key=lambda x: x[1]
    )
    l.reverse()
    return l

async def capture(cubesat, cset):
	'''with open("image_count.txt", 'r') as f:
		try:
			out = f.read()
			print(out)
			count = int(out) + 1
		except:
			count = 0
	with open("image_count.txt", 'w') as f:
		f.write(str(count))'''
  
	print(mem_free())
	collect()
	buf = bytearray(cset["buffer_size"])
	print(mem_free())
	count = 3

	for i in range(0, 10):
		captureSingle(cubesat.cam, buf, f"burst{count}",  f"image{i}")
	folder = f"images/burst{count}"
	file = f"{folder}/{sortThroughDir(folder)[0][0]}"
	print(file)
	print(sortThroughDir(folder)[0][0])
	rename(file, f"images-to-send/image{count}.jpeg")
 
	for i in listdir(folder):
		remove(f"{folder}/{i}")
	rmdir(f"{folder}")

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
	IMAGE_DIRECTORY = "images-to-send" # Change when the camera code is done
	IMAGE_COUNT_FILE = "image_count.txt" # Placeholder
	
	camera_settings = cset.camera_settings

	report_diagnostics(cubesat.radio1)
	
	while True:
		try:
			print("Sending telemetry ping (handshake 1) and waiting for handshake 2")
			
			#creating telemetry payload
			t_payload = ["TEST", "TELEMETRY", "PAYLOAD"]
			# t_payload = functions.create_state_packet()
			# t_payload.extend(functions.get_imu_data())

			packet = Packet.make_handshake1(t_payload)
			await cubesat.ptp.send_packet(packet)
			packet = await cubesat.ptp.receive_packet()
			
			if not verify_packet(packet, "handshake2"):
				print(mem_free())
				await sleep(15)
				continue
				
			print("Handshake 2 received, sending handshake 3")
			
			# writing new camera settings
			if (packet.payload[1] is not None) and isinstance(packet.payload[1], dict):
				await save_settings(packet.payload[1], camera_settings, cubesat)
			
			# setting new timeout
			if packet.payload[2] is not None:
				cubesat.ptp.timeout = packet.payload[2]
			
			# if requested, take picture
			if packet.payload[3]:
				image_path = await capture(cubesat,camera_settings)
			
			# Get number of images taken
			try:
				with open(IMAGE_COUNT_FILE) as f:
					image_count = int(f.readline()) # one line with the image count
			except:
				print(f"Couldn't find {IMAGE_COUNT_FILE}, defaulting to 0")
				# image_count = len(listdir(IMAGE_DIRECTORY))
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
							remove(f"{IMAGE_DIRECTORY}/image{image_id}.jpeg")
							print(f"Removed image with id: {image_id}")
							# print(f"Would remove image with id: {image_id}, but testing")
						except:
							print(f"No image with id: {image_id} to be removed")
						continue
					else:
						await sleep(1)
						break
				
				# Get image with corresponding ID
				image_id = packet.payload_id
				image_path = f"{IMAGE_DIRECTORY}/image{image_id}.jpeg" # PLACEHOLDER
				
				request = packet.payload[1]
				print(f"Request received for image {image_id}, {request}")
				
				if request == "all":
					# to do: send time taken
					await cubesat.ftp.send_file(image_path, image_id)
				else:
					await cubesat.ftp.send_partial_file(image_path, image_id, request)
			
			await sleep(1)

		except Exception as e:
			print("Error in Main Loop:", ''.join(format_exception(e)))
