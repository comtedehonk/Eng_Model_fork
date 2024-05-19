import pysquared_rfm9x
import board
import busio
import digitalio
import traceback

import time
import os


spi0   = busio.SPI(board.SPI0_SCK,board.SPI0_MOSI,board.SPI0_MISO)
_rf_cs1 = digitalio.DigitalInOut(board.SPI0_CS0)
_rf_cs1.switch_to_output(value=True)
_rf_rst1 = digitalio.DigitalInOut(board.RF1_RST)
_rf_rst1.switch_to_output(value=True)
radio1 = pysquared_rfm9x.RFM9x(spi0,_rf_cs1, _rf_rst1, 437.4, code_rate=8, baudrate=1320000)
radio1.tx_power=23
radio1.spreading_factor = 8
radio1.node = 0xfa
radio1.destination = 0xfb
radio1.enable_crc=True
radio1.ack_delay=0.2

while True:
    try:
        radio1.send("Health of Cubesat: Healthy Haha")
        initial_packet = radio1.receive(timeout=10)
        print("received nothing")
        if initial_packet is None:
            continue
        print(initial_packet)
        if initial_packet != b'IRVCB':
            continue
        filepath = "THBBlueEarthTest.jpeg"
        size = os.stat(filepath)[6]
        
        with open(filepath, "rb") as image:
            radio1.send(bytearray([1]) + bytearray(size.to_bytes(4, "little")) + bytearray(image.read(244)))
            print("sent")
            packet_count = (size-1)//244+1
            for packet_index in range(2, packet_count+1):
                radio1.send(bytearray([1]) + bytearray(packet_index.to_bytes(4, "little")) + \
                    bytearray(image.read(244)))
                print("sent")
        radio1.send("Done")
        
        print("Sent image")
            
    except Exception as e:
        print("Error in Main Loop: "+ ''.join(traceback.format_exception(e)))


def send_image(filepath):
    size = os.stat(filepath)[6]
    radio1.send(size.to_bytes(4, "big"))
    with open(filepath, "rb") as stream:
        while True:
            data = stream.read(249)
            if not data:
                break
            radio1.send(data)
            print('sent')

