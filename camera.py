import sys
import board
import busio
import time
import digitalio
import adafruit_ov5640
import displayio
import gc
import adafruit_tca9548a # I2C Multiplexer

gc.enable()
print("memory before allocation: {}".format(gc.mem_free()))
height=640
width=480
quality=22
buf=bytearray(height*width//quality)
print("memory after allocation: {}".format(gc.mem_free()))

i2c1=busio.I2C(board.I2C1_SCL,board.I2C1_SDA)

# Initialize TCA
try:
    tca = adafruit_tca9548a.TCA9548A(i2c1,address=int(0x77))
    for channel in range(8):
        if tca[channel].try_lock():
            print("Channel {}:".format(channel))
            addresses = tca[channel].scan()
            print([hex(address) for address in addresses if address != 0x70])
            tca[channel].unlock()
except Exception as e:
    print("[ERROR][TCA]")


cam = adafruit_ov5640.OV5640(
    tca[5],
    data_pins=(
        board.D2,
        board.D3,
        board.D4,
        board.D5,
        board.D6,
        board.D7,
        board.D8,
        board.D9,
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
while True:
    time.sleep(2)
    print("memory before picture: {}".format(gc.mem_free()))
    try:
        cam.capture(buf)
        eoi = buf.find(b"\xff\xd9")
        if eoi != -1:
            # terminate the JPEG data just after the EOI marker
            print(memoryview(buf)[: eoi + 2].hex())
        else:
            print("image corrupted!")

    except Exception as e:
        print("error! " + str(e))
        gc.collect()
    print("memory after picture: {}".format(gc.mem_free()))