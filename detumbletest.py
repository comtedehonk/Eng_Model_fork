from pysquared import cubesat as c
import asyncio
import time
import traceback
import gc #Garbage collection
import functions
from debugcolor import co
def debug_print(statement):
    if c.debug:
        print(co("[MAIN]" + statement, 'blue', 'bold'))
f=functions.functions(c)
while True:
    try:
        f.detumble()
        f.send("Detumble finished")
        c.RGB=(255,255,0)
        time.sleep(5)
    except Exception as e: 
        debug_print(f"There is an error: {e}")
        traceback.print_exc()
    
