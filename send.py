from pysquared import cubesat as c
import functions 
import time
import os



f = functions.functions(c)
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
            f.send(data)
            time.sleep(2)

send_image("image.png")


    




