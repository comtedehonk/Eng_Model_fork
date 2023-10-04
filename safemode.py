print("I am in safemode. Help!")
import microcontroller
import time
from pysquared import battery_voltage, cubesat
from Big_Data import Get_Thermo_Data
try:
    time.sleep(10)
    microcontroller.reset()
    print('in safemode')
    
    while True:
        voltage = battery_voltage()
        temp = cubesat.IMU.mcp.temperature
        if(voltage > cubesat.NORMAL_BATTERY_VOLTAGE & temp > -20 & temp <35):
            break
        

        time.sleep(90)
    microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
    microcontroller.reset()

except Exception as e:
    print(f"The error is: {e}")
    time.sleep(10)
    microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
    microcontroller.reset()
