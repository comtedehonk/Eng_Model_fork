'''
Irvington CubeSat's Packet Class
'''

class Packet:
	'''
	Our custom packet class.
	Details of each packet categorization are below.
	
	Category     Type   Payload
	handshake1   cmd    ["#IRVCB", -1]
	handshake2   cmd    ["#IRVCBH2", -1]
	handshake3   cmd    ["#IRVCBH3", image_count]
	file_req     cmd    ["req", "all" | [packet_ids]]
	file_len     cmd    packet_count 
	file_data    data   chunk_data
	'''
	
	def __init__(self, packet_type, sequence_num, payload_id, payload):
		self.packet_type = packet_type
		self.sequence_num = sequence_num
		self.payload_id = payload_id
		self.payload = payload
	
	data_packet = 0
	cmd_packet = 1
	packet_types = ("handshake1", "handshake2", "handshake3", "file_req", "file_len", "file_data", "none", "state_of_health")

	def categorize(self):
		try:
			if self.packet_type is None:
				return "none"
			if self.packet_type == self.cmd_packet:
				if isinstance(self.payload, list) and len(self.payload) > 0:
					if self.payload[0] == "#IRVCB":
						return "handshake1"
					elif self.payload[0] == "#IRVCBH2":
						return "handshake2"
					elif self.payload[0] == "#IRVCBH3":
						return "handshake3"
					elif self.payload[0] == "req":
						return "file_req"
					elif self.payload[0] == "#IRCVBST":
						return "state_of_health"
				return "file_len"
			else:
				return "file_data"
		except Exception as e:
			print("Error categorizing packet:", e)

	@staticmethod
	def make_handshake1(payload):
		return Packet(Packet.cmd_packet, None, None, ["#IRVCB", payload])
	
	@staticmethod
	def make_handshake2():
		return Packet(Packet.cmd_packet, None, None, ["#IRVCBH2", -1])
	
	@staticmethod
	def make_handshake3(image_count):
		return Packet(Packet.cmd_packet, None, None, ["#IRVCBH3", image_count])
	
	@staticmethod
	def make_file_req(file_id, packets=None):
		req_body = "all" if packets is None else packets
		return Packet(Packet.cmd_packet, None, file_id, ["req", req_body])
	
	@staticmethod
	def make_file_len(payload_id, packet_count):
		return Packet(Packet.cmd_packet, None, payload_id, -packet_count)
	
	@staticmethod
	def make_file_data(sequence_num, payload_id, chunk):
		return Packet(Packet.data_packet, sequence_num, payload_id, chunk)
