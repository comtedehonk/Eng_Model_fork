from pysquared import cubesat as c
import time
import os


def send_image(filepath):
    size = os.path.getsize(filepath)
    #password = 13
    packet = size.to_bytes(6, byteorder = "big")
    packet = bytearray(packet)
    packet[0] = 13 #password
    packet[1] = 1 #indicator for images
    f.send(packet)
    with open(filepath, "rb") as stream:
        while True:
            data = stream.read(252)
            if not data:
                break
            c.radio1.send(data)
            time.sleep(2)

send_image("image.png")


    




