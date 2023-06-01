'''
Created by Nicole Maggard and Michael Pham 8/19/2022
Updated for Yearling by Nicole Maggard and Rachel Sarmiento 2/4/2023
This is where the processes get scheduled, and satellite operations are handeled
''' 
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
try:
    debug_print("Boot number: " + str(c.c_boot))
    debug_print(str(gc.mem_free()) + " Bytes remaining")
    #setup global vars below:
    lora_beacon = "KN6NAQ Hello I am Yearling! IHBPFJASTMNE! KN6NAQ"

    #setup all hardware below:
    c.neopixel.auto_write=False
    #test the battery:
    c.battery_manager()
    f.beacon()
    f.listen()
    distance1=0
    distance2=0
    tries=0
    loiter_time = 30
    debug_print("Burn attempt status: " + str(c.burnarm))
    debug_print("Burn status: " + str(c.burned))
    while c.burned is False and tries < 3:
        debug_print("Burn attempt try: " + str(tries+1))
        if tries == 0:
            debug_print("Loitering for " + str(loiter_time) + " seconds")
            try:
                c.neopixel[0] = (0,0,0)
                
                purple = (200, 8, 200)
                led_off = (0,0,0)
                
                for step in range(0,loiter_time):
                    
                    c.neopixel[0] = purple
                    time.sleep(0.5)
                    c.neopixel[0] = led_off
                    time.sleep(0.5)
                    debug_print(f"Entering full flight software in... {loiter_time-step} seconds")
            except Exception as e:
                debug_print("Error in Loiter Sequence: " + ''.join(traceback.format_exception(e)))
        try:
            distance1=c.distance()
            if distance1 > c.dist and c.dist is not 0 and distance1 > 10:
                c.burned = True
                raise TypeError("Wire seems to have burned and satellite browned out")
            else:
                c.dist=int(distance1)
                c.burnarm=True
            if c.burnarm:
                #sleep for some time as we fly away from the deployment pod
                time.sleep(120) #Set to 120 for flight
                c.burnarm=False
                c.burn("1",0.5,2500,5)
                time.sleep(3)
                distance2=c.distance()
            else:
                pass
            if distance2 > distance1+2 or distance2 > 10:
                c.burned=True  
        except Exception as e:
            debug_print("Error in Burn Sequence: " + ''.join(traceback.format_exception(e)))
            debug_print("Error: " + str(e))
            if "no attribute 'LiDAR'" in str(e):
                debug_print("Burning without LiDAR")
                time.sleep(120) #Set to 120 for flight
                c.burnarm=False
                c.burned=True
                c.burn("1",0.5,2500,5)
                time.sleep(3)
            break
        tries += 1
        


    f.beacon()
    f.listen()
    f.state_of_health()
    f.listen()

    c.battery_manager()
    f.battery_heater()
    c.battery_manager() #Second check to make sure we have enough power to continue

    f.beacon()
    f.listen()
    f.state_of_health()
    f.listen()
except Exception as e:
    debug_print("Error in Boot Sequence: " + ''.join(traceback.format_exception(e)))
finally:
    debug_print("All Faces off!")
    c.all_faces_off()

def critical_power_operations():
    f.beacon()
    f.listen()
    f.state_of_health()
    f.listen()  
     
    f.Long_Hybernate()

def minimum_power_operations():
    
    f.beacon()
    f.listen()
    f.state_of_health()   
    f.listen()
    
    f.Short_Hybernate() 
        
def normal_power_operations():
    
    debug_print("Entering Norm Operations")
    FaceData=[]
    #Defining L1 Tasks
    def check_power():
        gc.collect()
        c.battery_manager()
        f.battery_heater()
        c.battery_manager() #Second check to make sure we have enough power to continue
        
        if c.power_mode == 'normal' or c.power_mode == 'maximum': 
            pwr = True
        else:
            pwr = False

        debug_print(c.power_mode)
        gc.collect()
        return pwr
    
    async def s_lora_beacon():
        
        while check_power():
            f.beacon()
            f.listen()
            f.state_of_health()   
            time.sleep(1) # Guard Time
            
            await asyncio.sleep(30)

    async def g_face_data():
        
        while check_power():

            FaceData=[]

            try:
                debug_print("Getting face data...")
                FaceData = f.all_face_data()

                debug_print(FaceData)
                
            except Exception as t:
                debug_print(f'Outta time! {t}')
            
            gc.collect()
            
            await asyncio.sleep(60)
    
    async def l_face_data():
        
        await asyncio.sleep(15)
        
        while check_power():
            try:
                debug_print("Looking to log face data...")

                try:
                    debug_print("Logging face data...")
                    c.Face_log(FaceData)
                    
                except asyncio.TimeoutError as t:
                    debug_print(f'Outta time! {t}')

            except asyncio.TimeoutError as t:
                debug_print(f'Outta time! {t}')
            
            gc.collect()
            
            await asyncio.sleep(45)
    
    async def s_face_data():

        await asyncio.sleep(20)

        while check_power():
            try:
                debug_print("Looking to send face data...")
                f.send_face()
                
            except asyncio.TimeoutError as t:
                debug_print(f'Outta time! {t}')
            
            gc.collect()
            
            await asyncio.sleep(200)

    async def s_imu_data():

        await asyncio.sleep(45)
        
        while check_power():
            
            try:
                debug_print("Looking to get imu data...")
                IMUData=[]

                debug_print("IMU has baton")
                IMUData = f.get_imu_data()
                f.send(IMUData)
                f.face_data_baton = False

            except Exception as t:
                debug_print(f'Outta time! {t}')
                
            gc.collect()
            
            await asyncio.sleep(100)
    
    async def detumble():
        
        await asyncio.sleep(300)
        
        while check_power():
            try:
                debug_print("Looking to detumble...")
                f.detumble()
                debug_print("Detumble complete")
                
            except Exception as e:
                debug_print(f'Outta time!' + ''.join(traceback.format_exception(e)))
                
            gc.collect()
            
            await asyncio.sleep(300)
    
    async def main_loop():
        #log_face_data_task = asyncio.create_task(l_face_data())
            
        t1 = asyncio.create_task(s_lora_beacon())
        t2 = asyncio.create_task(s_face_data())
        t3 = asyncio.create_task(l_face_data())
        t4 = asyncio.create_task(s_imu_data())
        t5 = asyncio.create_task(g_face_data())
        t6 = asyncio.create_task(detumble())
        
        await asyncio.gather(t1,t2,t3,t4,t5,t6)
        
    asyncio.run(main_loop())


######################### MAIN LOOP ##############################
try:
    c.all_faces_on()
    while True:
        #L0 automatic tasks no matter the battery level
        c.battery_manager()
        
        if c.power_mode == 'critical':
            critical_power_operations()
            
        elif c.power_mode == 'minimum':
            minimum_power_operations()
            
        elif c.power_mode == 'normal':
            normal_power_operations()
            
        elif c.power_mode == 'maximum':
            normal_power_operations()
            
        else:
            f.listen()
except Exception as e:
    debug_print("Error in Main Loop: " + ''.join(traceback.format_exception(e)))
finally:
    debug_print("All Faces off!")
    c.all_faces_off()
