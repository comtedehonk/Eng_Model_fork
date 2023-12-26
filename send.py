from pysquared import cubesat as c
import time
import os


def send_image(filepath):
    size = os.stat(filepath)[6]
    c.radio1.send(size.to_bytes(4, "big"))
    with open(filepath, "rb") as stream:
        while True:
            data = stream.read(249)
            if not data:
                break
            c.radio1.send(data)
            print('sent')
send_image('THBBlueEarthTest.jpeg')
