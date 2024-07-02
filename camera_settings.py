import adafruit_ov5640

cam_settings = {
    "exposure": -3,
    "white_balance": 0,
    "night_mode": False,
    "size": adafruit_ov5640.OV5640_SIZE_VGA,
    "height": 480,
    "width": 640,
    "quality": 20,
    "buf": bytearray(480*640//20),
    "effect": 0
}