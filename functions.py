'''
This is the class that contains all of the functions for our CubeSat. 
We pass the cubesat object to it for the definitions and then it executes 
our will.
Authors: Nicole Maggard, Michael Pham, and Rachel Sarmiento
'''
import time
import alarm
import gc
import traceback
from debugcolor import co

class functions:

    def debug_print(self,statement):
        if self.debug:
            print(co("[Functions]" + statement, 'green', 'bold'))
    def __init__(self,cubesat):
        self.cubesat = cubesat
        self.debug = cubesat.debug
        self.debug_print("Initializing Functionalities")
        self.Errorcount=0
        self.facestring=[]
        self.last_battery_temp = 20
        self.face_data_baton = False
        self.detumble_enable_z = True
        self.detumble_enable_x = True
        self.detumble_enable_y = True
        try:
            self.cubesat.all_faces_on()
        except Exception as e:
            self.debug_print("Couldn't turn faces on: " + ''.join(traceback.format_exception(e)))
    
    '''
    Satellite Management Functions
    '''
    def battery_heater(self):
        """
        Battery_Heater Function. Called to turn on the battery heater for 30s.
        NOTE: we may want to add functionality to see if thermocouple has been reliable
        if a particular nvm flag gets flipped, then we may want to run heater on a timer
        """
        try:
            import Big_Data
            self.cubesat.all_faces_on()
            
            self.face_toggle("Face1",True)
            a=Big_Data.AllFaces(self.debug)
            a.Get_Thermo_Data()
            corrected_temp= a.Face0.couple[0]-a.Face0.couple[2]
            
            if corrected_temp < self.cubesat.NORMAL_BATT_TEMP:
                
                self.cubesat.heater_on()
                for _ in range (0,30):
                    corrected_temp= a.Face0.couple[0]-a.Face0.couple[2]
                    self.debug_print(f"Uncorrected: {a.Get_Thermo_Data()}")
                    self.debug_print(f"Corrected: {corrected_temp}")
                    time.sleep(1) 
                self.cubesat.heater_off()
                
                del a
                del Big_Data
                return True
            else: 
                self.debug_print("Battery is already warm enough")
                del a
                del Big_Data
                return False
        except Exception as e:
            self.debug_print("Big_Data error" + ''.join(traceback.format_exception(e)))
            return False
    
    def current_check(self):
        return self.cubesat.current_draw
    
    def test_faces(self):    
        try:
            self.cubesat.all_faces_on()
            a = self.all_face_data()
            
            self.last_battery_temp= a[1][5][0]-a[1][5][2]
            
            #Iterate through a and determine if any of the values are None
            #Add a counter to keep track of which iternation we are on
            count = 0 
            for face in a:
                if len(face) == 0:
                    self.debug_print("Face " + str(count) + " is None")
                    self.cubesat.hardware[f'Face{count}'] = False
                    count += 1
                else:
                    self.cubesat.hardware[f'Face{count}'] = True
                    count += 1
            
            self.debug_print(self.cubesat.hardware)
            
            del a
        except Exception as e:
            self.debug_print("An Error occured while trying to test faces: " + ''.join(traceback.format_exception(e)))

    '''
    Radio Functions
    '''  
    def send(self,msg):
        """Calls the RFM9x to send a message. Currently only sends with default settings.
        
        Args:
            msg (String,Byte Array): Pass the String or Byte Array to be sent. 
        """
        import Field
        self.field = Field.Field(self.cubesat,self.debug)
        self.field.fieldSide(str(msg),1,1)
        self.debug_print(f"Sent Packet: " + str(msg))
        del self.field
        del Field

    def beacon(self):
        """Calls the RFM9x to send a beacon. """
        import Field
        try:
            lora_beacon = "KN6NAQ Hello I am Yearling! I am in: " + str(self.cubesat.power_mode) +" power mode. V_Batt = " + str(self.cubesat.battery_voltage) + "V. IHBPFJASTMNE! KN6NAQ"
        except Exception as e:
            self.debug_print("Error with obtaining power data: " + ''.join(traceback.format_exception(e)))
            lora_beacon = "KN6NAQ Hello I am Yearling! I am in: " + "an unidentified" +" power mode. V_Batt = " + "Unknown" + ". IHBPFJASTMNE! KN6NAQ"

        self.field = Field.Field(self.cubesat,self.debug)
        self.field.Beacon(lora_beacon)
        del self.field
        del Field

    def state_of_health(self):
        import Field
        self.test_faces()
        self.state_list=[]
        #list of state information 
        try:
            self.state_list = [
                f"PM:{self.cubesat.power_mode}",
                f"VB:{self.cubesat.battery_voltage}",
                f"TB:{self.last_battery_temp}", 
                f"ID:{self.cubesat.current_draw}",
                f"VS:{self.cubesat.system_voltage}",
                f"MT:{self.cubesat.micro.cpu.temperature}",
            ]
        except Exception as e:
            self.debug_print("Couldn't aquire data for the state of health: " + ''.join(traceback.format_exception(e)))
        
        self.field = Field.Field(self.cubesat,self.debug)
        self.field.Beacon("Yearling State of Health 1/2" + str(self.state_list))
        self.field.Beacon("2/2" + str(self.cubesat.hardware))
        del self.field
        del Field

    def send_face(self):
        """Calls the data transmit function from the field class
        """
        import Field
        self.field = Field.Field(self.cubesat,self.debug)
        self.debug_print("Sending Face Data")
        self.field.Data_Transmit("Face", self.facestring, 6)
        del self.field
        del Field
    
    def send_face_data_small(self):
        self.debug_print("Trying to get the data! ")
        data = self.all_face_data()
        i = 0
        try:
            for face in data:
                self.debug_print(face)
                self.cubesat.radio1.send("Face Data: " + str(i) + " " + str(face))
                i+=1
            return True
        except Exception as e:
            self.debug_print("Error sending face data: " + ''.join(traceback.format_exception(e)))
            return False
    
    def listen(self):
        import cdh
        #This just passes the message through. Maybe add more functionality later. 
        self.CDH=cdh.cdh(self.cubesat,self.debug)
        try:
            self.cubesat.radio1.receive_timeout=10
            received = self.cubesat.radio1.receive(keep_listening=True)
        except Exception as e:
            self.debug_print("An Error has occured while listening: " + ''.join(traceback.format_exception(e)))
            received=None
        time.sleep(10)
        if received is not None:
            self.debug_print(f"Recieved Packet: ",received)
            self.CDH.message_handler(received)
            return True
        del cdh
        
        return False

        
    
    '''
    Big_Data Face Functions
    change to remove fet values, move to pysquared
    '''  
    def face_toggle(self,face,state):
        dutycycle = 0x0000
        if state:
            duty_cycle=0xffff
        
        if   face == "Face0": self.cubesat.Face0.duty_cycle = duty_cycle      
        elif face == "Face1": self.cubesat.Face0.duty_cycle = duty_cycle
        elif face == "Face2": self.cubesat.Face0.duty_cycle = duty_cycle      
        elif face == "Face3": self.cubesat.Face0.duty_cycle = duty_cycle           
        elif face == "Face4": self.cubesat.Face0.duty_cycle = duty_cycle          
        elif face == "Face5": self.cubesat.Face0.duty_cycle = duty_cycle
    
    def all_face_data(self):
        
        self.cubesat.all_faces_on()
        try:
            import Big_Data
            a = Big_Data.AllFaces(self.debug,self.cubesat.tca)
            
            self.facestring = a.Face_Test_All()
            
            del a
            del Big_Data
        except Exception as e:
            self.debug_print("Big_Data error" + ''.join(traceback.format_exception(e)))
        
        return self.facestring
    
    def get_imu_data(self):
        
        self.cubesat.all_faces_on()
        try:
            import Big_Data
            a = Big_Data.AllFaces(self.debug)
            
            data = a.Get_IMU_Data()
            
            del a
            del Big_Data
        except Exception as e:
            self.debug_print("Big_Data error" + ''.join(traceback.format_exception(e)))
        
        return data
    
    def OTA(self):
        # resets file system to whatever new file is received
        pass

    '''
    Logging Functions
    '''  
    def log_face_data(self,data):
        
        self.debug_print("Logging Face Data")
        try:
                self.cubesat.Face_log(data)
        except:
            try:
                self.cubesat.new_file(self.cubesat.Facelogfile)
            except Exception as e:
                self.debug_print('SD error: ' + ''.join(traceback.format_exception(e)))
        
    def log_error_data(self,data):
        
        self.debug_print("Logging Error Data")
        try:
                self.cubesat.log(data)
        except:
            try:
                self.cubesat.new_file(self.cubesat.logfile)
            except Exception as e:
                self.debug_print('SD error: ' + ''.join(traceback.format_exception(e)))
    
    '''
    Misc Functions
    '''  
    #Goal for torque is to make a control system 
    #that will adjust position towards Earth based on Gyro data
    def detumble(self,dur = 7, margin = 0.2, seq = 118):
        
        self.cubesat.all_faces_on()
        try:
            import Big_Data
        except Exception as e:
            self.debug_print("Big_Data error: " + ''.join(traceback.format_exception(e)))
            return
        a = Big_Data.AllFaces(self.debug)
        
        def do_detumble():
            data=a.Get_IMU_Data()
            self.debug_print(f"IMU Data: {data}")
            
            a.sequence=seq
            
            detumble_check(data)
            
            data2 = a.Get_IMU_Data()
            self.debug_print(f"IMU Data: {data}")
            
            margin_check(data,data2)
        
        def margin_check(data,data2):
            if data2[0][2] > data[0][2] + margin or data2[0][2] < data[0][2] - margin:
                self.detumble_enable_z = False
            else: 
                self.detumble_enable_z = True
                
            if data2[0][0] > data[0][0] + margin or data2[0][0] < data[0][0] - margin:
                self.detumble_enable_x = False
            else: 
                self.detumble_enable_x = True
                
            if data2[0][1] > data[0][1] + margin or data2[0][1] < data[0][1] - margin:
                self.detumble_enable_y = False
            else: 
                self.detumble_enable_y = True
            
        def detumble_check(data):
            if self.detumble_enable_z == False:
                self.debug_print("Detumble Blocked")
                return False
            elif self.detumble_enable_z == True:
                
                self.debug_print("Detumbling Z")
                if data[0][2] > 0.2:
                    a.drvz_actuate(dur)
                elif data[0][2] < -0.2:
                    a.drvz_actuate(dur)
    
    
            if self.detumble_enable_x == False:
                self.debug_print("Detumble Blocked")
                return False
            elif self.detumble_enable_x == True:
                self.debug_print("Detumbling X")
                if data[0][0] > 0.2:
                    a.drvx_actuate(dur)
                elif data[0][0] < -0.2:
                    a.drvx_actuate(dur)
                    
                    
            if self.detumble_enable_y == False:
                self.debug_print("Detumble Blocked")
                return False
            elif self.detumble_enable_y == True:
                self.debug_print("Detumbling Y")
                if data[0][1] > 0.2:
                    a.drvy_actuate(dur)
                elif data[0][1] < -0.2:
                    a.drvy_actuate(dur)
                    
            return True     
            
        try:
            self.debug_print("Attempting")
            do_detumble()
        except Exception as e:
            self.debug_print('Detumble error: ' + ''.join(traceback.format_exception(e)))
        
        del a
        del Big_Data
    
    def Short_Hybernate(self):
        self.debug_print("Short Hybernation Coming UP")
        gc.collect()
        #all should be off from cubesat powermode
        time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 120)#change to 2 min when not testing
        # Exit the program, and then deep sleep until the alarm wakes us.
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
        return True
    
    def Long_Hybernate(self):
        self.debug_print("LONG Hybernation Coming UP")
        gc.collect()
        #all should be off from cubesat powermode
        time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 600)
        # Exit the program, and then deep sleep until the alarm wakes us.
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
        return True
    