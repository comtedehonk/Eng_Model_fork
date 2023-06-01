'''
In this method the PyCubed will wait a pre-allotted loiter time before proceeding to execute
main. This loiter time is to allow for a keyboard interupt if needed. 

Authors: Nicole Maggard, Michael Pham, and Rachel Sarmiento
'''

import time
import board
import microcontroller
print('='*31)
print("Hello World! I am Yearling SN6!")
print('='*31)

#Main code commented out to stop transmissions. 
'''try:
    import main

except Exception as e:    
    print(e)
    time.sleep(10)
    microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
    microcontroller.reset()'''