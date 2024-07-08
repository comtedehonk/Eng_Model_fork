"""
`ptp`
====================================================

Simple CircuitPython compatible packet transfer protocol
Adapted from Stanford PyGS: https://github.com/stanford-ssi/PyGS
Modified for pycubed_rfm9x

"""
from io import BytesIO
import msgpack
from icpacket import Packet

class AsyncPacketTransferProtocol:
    """A simple transfer protocol for commands and data"""

    def __init__(self, protocol, packet_size=252, timeout=1, log=False, enable_padding=False):
        self.protocol = protocol
        self.packet_size = packet_size
        self.max_packet_total_size = 252 # pycubed_rfm9x
        self.enable_padding = enable_padding
        
        self.timeout = timeout # Modified
        self.log = log
        self.MAX_SIZE = self.max_packet_total_size
        # self.tmp_stream = io.BytesIO()
        self.out_stream = BytesIO()
    
    # Constants
    data_packet = Packet.data_packet
    cmd_packet = Packet.cmd_packet
    
    header_len = 6
    MAX_SEQUENCE_NUM = 2**19-1
    MAX_PAYLOAD_ID = 2**20-1
        
    def logger(self, *messages):
        if self.log:
            for m in messages:
                print(m)
    
    def write_packet_into_out_stream(self, packet_type, payload, sequence_num, payload_id):
        self.out_stream.seek(0)
        tmp_stream = BytesIO()
        if packet_type != self.cmd_packet and packet_type != self.data_packet:
            self.logger("packet type error")
            return -1
        elif sequence_num > self.MAX_SEQUENCE_NUM:
            self.logger("sequence num error")
            return -1
        elif payload_id > self.MAX_PAYLOAD_ID:
            self.logger("payload id error")
            return -1
        else:
            msgpack.pack(payload, tmp_stream)
            payload_len = tmp_stream.tell()
            # If padding is enabled, append \x00 bytes until payload is of length 252
            # if self.enable_padding and payload_len < self.packet_size:
                # self.tmp_stream.write(b"\x00"*(self.packet_size - payload_len))
            tmp_stream.seek(0)
            if payload_len > self.packet_size:
                self.logger(f"packet too long ({payload_len} bytes, limit is {self.packet_size})")
                return -1
            
            header = (packet_type << 47) | (payload_len << 39) | (sequence_num << 20) | payload_id
            self.logger(f"header: {header}")
            self.logger(f"packet type: {packet_type}", f"payload len: {payload_len}",
                f"sequence num: {sequence_num}", f"payload ID: {payload_id}")
            # self.logger(f"pycubed sending packet: {self.tmp_stream.getvalue()}")
            
            self.out_stream.write((header % (1 << 48)).to_bytes(6, "big"))
            self.out_stream.write(tmp_stream.read(payload_len))
            self.out_stream.seek(0)
            return payload_len
    
    async def send_packet(self, packet, with_ack=False):
        packet_type = packet.packet_type
        sequence_num = packet.sequence_num
        if sequence_num is None:
            sequence_num = self.MAX_SEQUENCE_NUM
        payload_id = packet.payload_id
        if payload_id is None:
            payload_id = self.MAX_PAYLOAD_ID
        payload = packet.payload
        payload_len = self.write_packet_into_out_stream(
            packet_type, payload, sequence_num, payload_id
        )
        if payload_len == -1:
            return False
        
        self.out_stream.seek(0)
        raw_data = self.out_stream.read(self.MAX_SIZE)
        self.logger(f"wrote data: {raw_data}")
        if with_ack:
            self.protocol.send_with_ack(raw_data)
        else:
            self.protocol.send(raw_data)
        self.out_stream.seek(0)
        return True
    
    # send_packet_sync function
    
    async def receive_packet(self, with_ack=False, timeout=None):
        if timeout is None:
            timeout = self.timeout
        packet = self.protocol.receive(timeout=timeout, with_ack=with_ack)
        if packet is None:
            return Packet(None, None, None, None)
        
        header = int.from_bytes(packet[0:6], "big")
        packet_type = header >> 47
        payload_len = (header >> 39) & (2**8 - 1)
        sequence_num = (header >> 20) & (2**19 - 1)
        payload_id = header & (2**20 - 1)
        self.logger(f"header: {header}")
        self.logger(f"packet type: {packet_type}", f"payload len: {payload_len}",
            f"sequence num: {sequence_num}", f"payload ID: {payload_id}")
        # future optim: tmp_stream in this function can be preallocated
        tmp_stream = BytesIO()
        tmp_stream.write(packet[6:6 + payload_len])
        # self.logger(f"tmp stream before write: {self.tmp_stream.getvalue()}")
        # self.tmp_stream.seek(0)
        # self.logger(f"payload_packed: {self.tmp_stream.read(payload_len)}")
        tmp_stream.seek(0)
        try:
            payload = msgpack.unpack(tmp_stream)  # TODO make this the same?
        except TypeError:
            print(f"Unexpected structure: {tmp_stream.getvalue()}")
            return None
        except ValueError:
            print(f"Failed to decode: {tmp_stream.getvalue()}")
            return None
        except Exception as e:
            print(f"Unknown exception: {tmp_stream.getvalue()} {e}")
            return None
        else:
            # if packet_type == self.cmd_packet:
            #   print("pycubed sending ACK")
            #   self.protocol.send(b"ACK")
            # self.tmp_stream = io.BytesIO()
            # self.tmp_stream.seek(0)
            self.logger(f"payload: {payload}")
            return Packet(packet_type, sequence_num, payload_id, payload)
