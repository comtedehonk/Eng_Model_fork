"""
Irvington CubeSat's file transfer protocol for CircuitPython
Inspired by `ftp` from Stanford PyGS
"""
import os
import math
import time 
import asyncio
from icpacket import Packet

class FileTransferProtocol:

	def __init__(self, ptp, chunk_size=252, packet_delay=0, request_size=10, log=False):
		self.ptp = ptp
		self.log = log
		self.request_file_cmd = 's'
		self.request_partial_file_cmd = 'e'
		self.chunk_size = chunk_size # Modified
		self.packet_delay = packet_delay # Modified
		
		if request_size > 48:
			print("Warning: Request size should not exceed 48 on PyCubed")
		self.request_size = request_size

	async def request_file(self, remote_path, local_path, retries=3):
		if self.log: print("PyCubed requesting file now")
		await self.ptp.send_packet(
			self.ptp.cmd_packet,
			[self.request_file_cmd, remote_path],
		)
		missing = await self.receive_file(local_path)
	   
		while retries:
			if self.log: print(f"missing: {missing}")
			if self.log: print(f"retries remaining: {retries}")
			if missing == set():
				return True
			self.ptp.send_packet(
				self.ptp.cmd_packet,
				[self.request_partial_file_cmd, remote_path, list(missing)]
			)
			missing = await self.receive_partial_file(local_path, missing)
			retries -= 1
		return False
	
	async def receive_file(self, local_path):
		num_packets, sequence_number, payload_id = await self.ptp.receive_packet()
		num_packets = abs(num_packets)
		if self.log: print(f"expecting to receive {num_packets} packets")
		with open(local_path, 'ab+') as f:
			missing = {i for i in range(num_packets)}
			for packet_num in range(num_packets):
				chunk, packet_num_recvc, payload_id  = await self.ptp.receive_packet()
				missing.remove(packet_num_recvc)
				f.write(chunk)
				os.sync()
			return missing
	
	async def _request_partial(self, file_id, missing):
		request = []
		for i in range(len(missing)):
			if missing[i] == 1:
				request.append(i)
				if len(request) == self.request_size: # Request at most request_size packets
					break
		packet = Packet.make_file_req(file_id, request)
		await self.ptp.send_packet(packet)
		return len(request)
		
	
	async def request_file_custom(self, file_id, filename, local_path, retry_limit=None, defer_assembly=False):
		'''
		Request the file specified by its unique file_id, storing it as filename.
		The local_path directory is used to store packets, metadata, and the complete file.
		'''
		# Make local_path directory
		try:
			os.mkdir(local_path)
		except:
			pass
		
		if retry_limit is None: retry_limit = float("inf")
		retries = 0
		
		# Get packet count and packet status and send the first request
		# State: num_packets, missing, waiting_on
		ls = os.listdir(local_path)
		if "packet_status.txt" in ls: # file has been requested before
			with open(f"{local_path}/packet_status.txt") as f:
				num_packets = int(f.readline())
				missing = list(map(int, f.readline().strip()))
			if missing.count(1) == 0:
				print(f"File {file_id} has no missing packets")
				return True
			
			print(f"Requesting part of file {file_id}, {missing}")
			waiting_on = await self._request_partial(file_id, missing)
		
		else: # file has not been requested before
			packet = Packet.make_file_req(file_id) # request all
			print(f"Requesting all of file {file_id}")
			await self.ptp.send_packet(packet)
			
			header_packet = await self.ptp.receive_packet()
			if header_packet.categorize() != "file_len":
				print(f"Packet of type {header_packet.categorize()} (not file_len) received")
				return False
			
			assert header_packet.payload_id == file_id, "File IDs don't match"
			num_packets = abs(header_packet.payload)
			if self.log:
				print(f"File {file_id} contains {num_packets} packets")
			missing = [1]*num_packets
			waiting_on = num_packets
		
		# Receive file data
		while True:
			received_packets = await self.receive_file_custom(waiting_on, local_path)
			
			# to do: replace this with a check for no acknowledgement of the request
			if len(received_packets) == 0:
				print("No response to request, ending attempts")
				return False
			
			# Update missing
			for rec in received_packets:
				missing[rec] = 0
			
			# Update packet status
			with open(f"{local_path}/packet_status.txt", "w") as f:
				f.write(str(num_packets))
				f.write("\n")
				f.write(''.join(map(str, missing)))
			
			if missing.count(1) == 0: # All packets received
				if not defer_assembly:
					# Assemble file
					with open(f"{local_path}/{filename}", "wb") as f:
						for i in range(num_packets):
							with open(f"{local_path}/packet_{i}", "rb") as g:
								f.write(g.read(self.chunk_size))
				if self.log: print(f"File {file_id} has been completely received")
				return True
			
			# Not all packets received
			if retries >= retry_limit:
				print(f"Retry limit reached ({retry_limit})")
				return False
			retries += 1
			if self.log: print(f"missing: {missing}, requesting partial (attempt {retries})")
			waiting_on = await self._request_partial(file_id, missing)
	
	async def receive_file_custom(self, incoming_packets, local_path, timeout=10):
		received_packets = []
		last_time = time.monotonic()
		for packet_num in range(incoming_packets):
			packet = await self.ptp.receive_packet()
			if packet.categorize() != "file_data":
				print(f"Packet of type {packet.categorize()} (not file_data) received")
				if time.monotonic() - last_time >= timeout:
					print(f"No valid packets received in the past {timeout} seconds, breaking")
					break
				continue
			
			# Packet received
			last_time = time.monotonic()
			with open(f"{local_path}/packet_{packet.sequence_num}", "wb") as f:
				f.write(packet.payload)
			received_packets.append(packet.sequence_num)
			if self.log:
				print(f"Packet {packet.sequence_num} received ({len(received_packets)}/{incoming_packets})")
		return received_packets
	
	def assemble_file(self, filename, local_path):
		"""
		Assemble the packets stored at local_path and store as local_path/filename.
		To be used when requesting files with defer_assembly=True
		"""
		with open(f"{local_path}/packet_status.txt") as f:
			num_packets = int(f.readline())
			missing = list(map(int, f.readline().strip()))
		assert missing.count(1) == 0, "File has missing packets"
		with open(f"{local_path}/{filename}", "wb") as f:
			for i in range(num_packets):
				with open(f"{local_path}/packet_{i}", "rb") as g:
					f.write(g.read(self.chunk_size))
		return True
	
	async def receive_file_sync(self, local_path):
		num_packets, sequence_number = self.ptp.receive_packet_sync()
		num_packets = abs(num_packets)
		if self.log: print(f"expecting to receive {num_packets} packets")
		with open(local_path, 'ab+') as f:
			missing = {i for i in range(num_packets)}
			for packet_num in range(num_packets):
				chunk, packet_num_recvc  = self.ptp.receive_packet_sync()
				missing.remove(packet_num_recvc)
				f.write(chunk)
				os.sync()
			return missing

	async def receive_partial_file(self, local_path, missing):
		_, _, _ = await self.ptp.receive_packet()
		missing_immutable = tuple(missing)
		for expected_packet_num in missing_immutable:
			chunk, recv_packet_num, payload_id  = await self.ptp.receive_packet()
			missing.remove(int(recv_packet_num))
			location = self.packet_size * recv_packet_num
			self.insert_into_file(chunk, local_path, location)
			os.sync()
		return missing

	def insert_into_file(self, data, filename, location):
		"""Insert data into a file, and be worried about running out of RAM
		"""
		with open(filename, 'rb+') as fh:
			fh.seek(location)
			with open('tmpfile', 'wb+') as th:
				for chunk, _ in self._read_chunks(fh, self.chunk_size): 
					print(chunk)
					th.write(chunk)
				fh.seek(location)
				fh.write(data)
		
		with open(filename, 'ab+') as fh:
			fh.seek(location + len(data))
			with open('tmpfile', 'rb+') as th:
				for chunk, _ in self._read_chunks(th, self.chunk_size): 
					print(chunk)
					fh.write(chunk)
		os.remove('tmpfile')
	
	async def send_partial_file(self, filename, file_id, request):
		with open(filename, "rb") as f:
			for packet_num in request:
				if self.packet_delay > 0:
					await asyncio.sleep(self.packet_delay)
				print(f"Sending packet {packet_num+1}")
				f.seek(self.chunk_size * packet_num)
				chunk = f.read(self.chunk_size)
				packet = Packet.make_file_data(packet_num, file_id, chunk)
				success = await self.ptp.send_packet(packet)
				if not success:
					print(f"Failed to send packet {packet_num+1}")
				else:
					print(f"Packet {packet_num+1} sent")
	
	async def send_file(self, filename, file_id):
		"""Send a file

		Args:
			filename (str): path to file that will be sent
			chunk_size (int, optional): chunk sizes that will be sent. Defaults to 64.
		"""
		with open(filename, 'rb') as f:
			stats = os.stat(filename)
			filesize = stats[6]
			
			# send the number of packets for the client
			print("Sending packet count and file ID")
			packet_count = math.ceil(filesize / self.chunk_size)
			packet = Packet.make_file_len(file_id, packet_count)
			await self.ptp.send_packet(packet)
			# await self.ptp.send_packet(
				# self.ptp.data_packet,
				 # - packet_count,
				# payload_id=file_id
			# )

			# send all the chunks
			for chunk, packet_num in self._read_chunks(f, self.chunk_size):
				if self.packet_delay > 0:
					await asyncio.sleep(self.packet_delay)
				print(f"Sending packet {packet_num+1}")
				# success = await self.ptp.send_packet(
					# self.ptp.data_packet,
					# chunk,
					# sequence_num=packet_num,
					# payload_id=file_id
				# )
				packet = Packet.make_file_data(packet_num, file_id, chunk)
				success = await self.ptp.send_packet(packet)
				if not success:
					print(f"Failed to send packet {packet_num+1}")
				else:
					print(f"Packet {packet_num+1} of {packet_count} sent")

	def send_file_sync(self, filename, file_id=None):
		"""Send a file

		Args:
			filename (str): path to file that will be sent
			chunk_size (int, optional): chunk sizes that will be sent. Defaults to 64.
		"""
		with open(filename, 'rb') as f:
			stats = os.stat(filename)
			filesize = stats[6]
			
			# send the number of packets for the client
			print("sending number of packets!!!!!")
			self.ptp.send_data_packet_sync(
				 - math.ceil(filesize / self.chunk_size),
				payload_id=file_id
			)
			print("ok")

			# send all the chunks
			for chunk, packet_num in self._read_chunks(f, self.chunk_size):
				self.ptp.send_data_packet_sync(
					chunk,
					sequence_num=packet_num,
					payload_id=file_id
				)
				
	def _read_chunks(self, infile, chunk_size):
		"""Generator that reads chunks of a file

		Args:
			infile (str): path to file that will be read
			chunk_size (int, optional): chunk sizes that will be returned. Defaults to 64.

		Yields:
			bytes: chunk of file
		"""
		counter = 0
		while True:
			chunk = infile.read(chunk_size)
			if chunk:
				yield (chunk, counter)
			else:
				break
			counter += 1

