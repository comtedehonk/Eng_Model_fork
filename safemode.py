print("I am in safemode. Help!")
import microcontroller
import time
from pysquared import battery_voltage
from Big_Data import Get_Thermo_Data
try:
    time.sleep(10)
    microcontroller.reset()
    print('in safemode')
    
    while True:
        voltage = battery_voltage()
        temp = Get_Thermo_Data()
        if(voltage > 6 & temp > -20 & temp <50):
            break
        

        time.sleep(90)
    microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
    microcontroller.reset()

except Exception as e:
    time.sleep(10)
    microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
    microcontroller.reset()
