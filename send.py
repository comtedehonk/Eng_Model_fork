from pysquared import cubesat as c
import time
import os
from adafruit_bno08x import BNO_REPORT_ACCELEROMETER
import math

#initializing imu
bno = BNO08X_I2C(c.i2c1)
bno.enable_feature(BNO_REPORT_ACCELEROMETER)


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

while True:
    accel = bno.acceleration
    print(f'x : {accel[0]}, y : {accel[1]}, z: {accel[2]}')
    threshold = math.sqrt(math.pow(accel[0], 2)+ math.pow(accel[1], 2) + math.pow(accel[2], 2)) 
    print(threshold)
    time.sleep(3)