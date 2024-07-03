import adafruit_ov5640

camera_settings = {
    "effect": 0,
    "exposure_value": -3,
    "white_balance": 0,
    "size": adafruit_ov5640.OV5640_SIZE_VGA,
    "buffer_size": 480*640//20,
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "sharpness": 0,
    "flip_x": False,
    "flip_y":False,
    "test_pattern": False,
    "night_mode": False,
    "MAX_FILESIZE": 120000
}