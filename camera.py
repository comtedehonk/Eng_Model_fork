import board
import busio
import time
import adafruit_ov5640
import gc
import os

gc.enable()
print("memory before allocation: {}".format(gc.mem_free()))
FACTOR = 1
height=480
width=640
quality=20
buf=bytearray(height*width//quality)
print("memory after allocation: {}".format(gc.mem_free()))

i2c0=busio.I2C(board.I2C0_SCL,board.I2C0_SDA)

cam = adafruit_ov5640.OV5640(
    i2c0,
    data_pins=(
        board.D2,
        board.D3,
        board.D4,
        board.D5,
        board.D6,
        board.D7,
        board.D8,
        board.D9  
    ),
    clock=board.PC,
    vsync=board.VS,
    href=board.HS,
    mclk=None,
    shutdown=None,
    reset=None,
    size=adafruit_ov5640.OV5640_SIZE_VGA
)

cam.colorspace = adafruit_ov5640.OV5640_COLOR_JPEG
cam.flip_y = False
cam.flip_x = False
cam.test_pattern = False

cam.effect=0
cam.exposure_value=-2
cam.white_balance=2
cam.night_mode=False
cam.quality=quality
print("memory before collection: {}".format(gc.mem_free()))
gc.collect()
print("memory after collection: {}".format(gc.mem_free()))

for i in range(0,30): 
    try:
        cam.capture(buf)
        eoi = buf.find(b"\xff\xd9")
        if eoi != -1:
            # terminate the JPEG data just after the EOI marker
            print(memoryview(buf)[: eoi + 2].hex())
            print('good image')
        else:
            print("image corrupted!")

    except Exception as e:
        print("error! " + str(e))
        gc.collect()