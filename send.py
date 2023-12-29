from pysquared import cubesat as c
import time
import os


def send_image(filepath):
<<<<<<< HEAD
    size = os.stat(filepath)[6]
    c.radio1.send(size.to_bytes(4, "big"))
=======
    size = 6576
    c.radio1.send()
>>>>>>> bbbde3a (changed where temperature is being pulled from)
    with open(filepath, "rb") as stream:
        while True:
            data = stream.read(249)
            if not data:
                break
            c.radio1.send(data)
<<<<<<< HEAD
            print('sent')
send_image('THBBlueEarthTest.jpeg')
=======
            time.sleep(2)
send_image("image.png")


    




>>>>>>> bbbde3a (changed where temperature is being pulled from)
