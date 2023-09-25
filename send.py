from pysquared import cubesat as c
import time


def send_image(filepath):
    count = 0
    with open(filepath, "rb") as stream:
        while True:
            data = stream.read(252)
            if not data:
                break
            c.radio1.send(data)
            count = count +1
            time.sleep(2)
    return count
send_image("image.png")


    




