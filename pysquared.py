"""
CircuitPython driver for PySquared satellite board.
PySquared Hardware Version: mainboard-v01
CircuitPython Version: 8.0.0 alpha
Library Repo: 

* Author(s): Nicole Maggard, Michael Pham, and Rachel Sarmiento
"""
# Common CircuitPython Libs
import board, microcontroller
import busio, time, sys, traceback
from storage import mount,umount,VfsFat
import digitalio, sdcardio, pwmio
from debugcolor import co
import gc

# Hardware Specific Libs
import pysquared_rfm9x # Radio
import neopixel # RGB LED
import adafruit_pca9685 # LED Driver
import adafruit_vl6180x # LiDAR Distance Sensor for Antenna
import ina219 # Power Monitor


import adafruit_tca9548a # I2C Multiplexer

# Common CircuitPython Libs
from os import listdir,stat,statvfs,mkdir,chdir
from bitflags import bitFlag,multiBitFlag,multiByte
from micropython import const


# NVM register numbers
_BOOTCNT  = const(0)
_VBUSRST  = const(6)
_STATECNT = const(7)
_TOUTS    = const(9)
_ICHRG    = const(11)
_DIST     = const(13)
_FLAG     = const(16)

SEND_BUFF=bytearray(252)

class Satellite:
    # General NVM counters
    c_boot      = multiBitFlag(register=_BOOTCNT, lowest_bit=0,num_bits=8)
    c_vbusrst   = multiBitFlag(register=_VBUSRST, lowest_bit=0,num_bits=8)
    c_state_err = multiBitFlag(register=_STATECNT,lowest_bit=0,num_bits=8)
    c_distance  = multiBitFlag(register=_DIST,    lowest_bit=0,num_bits=8)
    c_ichrg     = multiBitFlag(register=_ICHRG,   lowest_bit=0,num_bits=8)

    # Define NVM flags
    f_lowbatt  = bitFlag(register=_FLAG,bit=0)
    f_solar    = bitFlag(register=_FLAG,bit=1)
    f_burnarm  = bitFlag(register=_FLAG,bit=2)
    f_lowbtout = bitFlag(register=_FLAG,bit=3)
    f_gpsfix   = bitFlag(register=_FLAG,bit=4)
    f_shtdwn   = bitFlag(register=_FLAG,bit=5)
    f_burned   = bitFlag(register=_FLAG,bit=6)

    #Turns all of the Faces On (Defined before init because this fuction is called by the init)
    def all_faces_on(self):
        #Faces MUST init in this order or the uController will brown out. Cause unknown
        self.Face0.duty_cycle = 0xffff
        self.hardware['Face0']=True
        self.Face1.duty_cycle = 0xffff
        self.hardware['Face1']=True
        self.Face2.duty_cycle = 0xffff
        self.hardware['Face2']=True
        self.Face3.duty_cycle = 0xffff
        self.hardware['Face3']=True
        self.Face4.duty_cycle = 0xffff
        self.hardware['Face4']=True

    def all_faces_off(self):
        #De-Power Faces 
        self.Face0.duty_cycle = 0x0000
        time.sleep(0.1)
        self.hardware['Face0']=False
        self.Face1.duty_cycle = 0x0000
        time.sleep(0.1)
        self.hardware['Face1']=False
        self.Face2.duty_cycle = 0x0000
        time.sleep(0.1)
        self.hardware['Face2']=False
        self.Face3.duty_cycle = 0x0000
        time.sleep(0.1)
        self.hardware['Face3']=False
        self.Face4.duty_cycle = 0x0000
        time.sleep(0.1)
        self.hardware['Face4']=False

    def debug_print(self,statement):
        if self.debug:
            print(co("[pysquared]" + statement, "red", "bold"))

    def __init__(self):
        """
        Big init routine as the whole board is brought up.
        """
        self.BOOTTIME= const(time.time())
        self.NORMAL_TEMP=20
        self.NORMAL_BATT_TEMP=20
        self.NORMAL_MICRO_TEMP=20
        self.NORMAL_CHARGE_CURRENT=0.5
        self.NORMAL_BATTERY_VOLTAGE=6.8
        self.CRITICAL_BATTERY_VOLTAGE=6.5
        self.data_cache={}
        self.filenumbers={}
        self.image_packets=0
        self.urate = 115200
        self.vlowbatt=6.0
        self.send_buff = memoryview(SEND_BUFF)
        self.debug=True #Define verbose output here. True or False
        self.micro=microcontroller
        self.hardware = {
                       'IMU':    False,
                       'Radio1': False,
                       'SDcard': False,
                       'LiDAR':  False,
                       'WDT':    False,
                       'PWR':    False,
                       'FLD':    False,
                       'Face0':  False,
                       'Face1':  False,
                       'Face2':  False,
                       'Face3':  False,
                       'Face4':  False,
                       }  



        # Define burn wires:
        self._relayA = digitalio.DigitalInOut(board.BURN_RELAY)
        self._relayA.switch_to_output(drive_mode=digitalio.DriveMode.OPEN_DRAIN)
        self._resetReg = digitalio.DigitalInOut(board.VBUS_RESET)
        self._resetReg.switch_to_output(drive_mode=digitalio.DriveMode.OPEN_DRAIN)


        # Define SPI,I2C,UART | paasing I2C1 to BigData
        try:
            self.i2c0  = busio.I2C(board.SCL0,board.SDA0,timeout=5)
            self.spi0   = busio.SPI(board.SPI0_SCK,board.SPI0_MOSI,board.SPI0_MISO)
            self.i2c1  = busio.I2C(board.SCL1,board.SDA1,timeout=5)
            self.spi1   = busio.SPI(board.SPI1_SCK,board.SPI1_MOSI,board.SPI1_MISO)
            self.uart  = busio.UART(board.TX,board.RX,baudrate=self.urate)
        except Exception as e:
            self.debug_print("ERROR INITIALIZING BUSSES: " + ''.join(traceback.format_exception(e)))

        # Initialize LED Driver
        try:
            self.faces = adafruit_pca9685.PCA9685(self.i2c0, address=int(0x56))
            self.faces.frequency = 60
            self.hardware['FLD'] = True
        except Exception as e:
            self.debug_print('[ERROR][LED Driver]' + ''.join(traceback.format_exception(e)))
        
        # Initialize all of the Faces and their sensors
        try:
            self.Face0 = self.faces.channels[0]
            self.Face1 = self.faces.channels[1]
            self.Face2 = self.faces.channels[2]
            self.Face3 = self.faces.channels[3]
            self.Face4 = self.faces.channels[4]
            self.all_faces_on()
        except Exception as e:
            self.debug_print("ERROR INITIALIZING FACES: " + ''.join(traceback.format_exception(e)))

        # Define filesystem stuff
        self.logfile="/error/log.txt"
        self.Facelogfile="/data/FaceData.txt"

        """ # Define I2C Reset
        self._i2c_reset = digitalio.DigitalInOut(board.I2C_RESET)
        self._i2c_reset.switch_to_output(value=True) """

        # Define radio
        _rf_cs1 = digitalio.DigitalInOut(board.SPI0_CS)
        _rf_rst1 = digitalio.DigitalInOut(board.RF_RESET)
        self.enable_rf = digitalio.DigitalInOut(board.ENABLE_RF)
        self.radio1_DIO0=digitalio.DigitalInOut(board.RF_IO0)
        
        # self.enable_rf.switch_to_output(value=False) # if U21
        self.enable_rf.switch_to_output(value=True) # if U7
        _rf_cs1.switch_to_output(value=True)
        _rf_rst1.switch_to_output(value=True)
        self.radio1_DIO0.switch_to_input()
        
        # Define Heater Pins 
        self.heater_en = self._relayA
        self.heater_en.direction = digitalio.Direction.OUTPUT
        self.heater_en.value = False
        
        '''self.heater_ctrl = digitalio.DigitalInOut(board.BURN_ENABLE)
        self.heater_ctrl.direction = digitalio.Direction.OUTPUT
        self.heater_ctrl.value = False'''

        # Initialize SD card (always init SD before anything else on spi bus)
        try:
            # Baud rate depends on the card, 4MHz should be safe
            _sd = sdcardio.SDCard(self.spi1, board.SPI1_CS, baudrate=4000000)
            _vfs = VfsFat(_sd)
            mount(_vfs, "/sd")
            self.fs=_vfs
            sys.path.append("/sd")
            self.hardware['SDcard'] = True
        except Exception as e:
            self.debug_print('[ERROR][SD Card]' + ''.join(traceback.format_exception(e)))

        # Initialize Neopixel
        try:
            self.neopixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2, pixel_order=neopixel.GRB)
            self.neopixel[0] = (0,0,0)
            self.hardware['Neopixel'] = True
        except Exception as e:
            self.debug_print('[WARNING][Neopixel]' + ''.join(traceback.format_exception(e)))


        # Initialize TCA
        try:
            self.tca = adafruit_tca9548a.TCA9548A(self.i2c0,address=int(0x77))
            for channel in range(8):
                if self.tca[channel].try_lock():
                    self.debug_print("Channel {}:".format(channel))
                    addresses = self.tca[channel].scan()
                    print([hex(address) for address in addresses if address != 0x70])
                    self.tca[channel].unlock()
        except Exception as e:
            self.debug_print("[ERROR][TCA]" + ''.join(traceback.format_exception(e))) 

        # Initialize Power Monitor update to utilize multiplexer on BIG_DATA
        try:
            self.pwr = ina219.INA219(self.tca[5])
            self.pwr.sense_resistor = 0.002
            self.hardware['PWR'] = True
        except Exception as e:
            self.debug_print('[ERROR][Power Monitor]' + ''.join(traceback.format_exception(e)))

        # Initialize LiDAR
        try:
            self.LiDAR = adafruit_vl6180x.VL6180X(self.i2c1)
            self.hardware['LiDAR'] = True
        except Exception as e:
            self.debug_print('[ERROR][LiDAR]' + ''.join(traceback.format_exception(e)))

        # Initialize radio #1 - UHF
        try:
            self.radio1 = pysquared_rfm9x.RFM9x(self.spi0, _rf_cs1, _rf_rst1,437.4,code_rate=8,baudrate=1320000)
            # Default LoRa Modulation Settings
            # Frequency: 437.4 MHz, SF7, BW125kHz, CR4/8, Preamble=8, CRC=True
            self.radio1.dio0=self.radio1_DIO0
            self.radio1.enable_crc=True
            self.radio1.ack_delay=0.2
            self.radio1.sleep()
            self.hardware['Radio1'] = True
        except Exception as e:
            self.debug_print('[ERROR][RADIO 1]' + ''.join(traceback.format_exception(e)))

        self.enable_rf.value = False
    

        # Prints init state of PyCubed hardware
        self.debug_print(str(self.hardware))

        # set PyCubed power mode
        self.power_mode = 'normal'

    def reinit(self,dev):
        dev=dev.lower()
        if dev=='pwr':
            self.pwr.__init__(self.i2c1)
        elif dev=='fld':
            self.faces.__init__(self.i2c1)
        elif dev=='imu':
            self.IMU.__init__(self.i2c1)
        else:
            self.debug_print('Invalid Device? ->' + str(dev))


    '''
    Code to toggle on / off individual faces
    '''
    @property
    def burnarm(self):
        return self.f_burnarm
    @burnarm.setter
    def burnarm(self, value):
        self.f_burnarm = value

    @property
    def burned(self):
        return self.f_burned
    @burned.setter
    def burned(self, value):
        self.f_burned = value

    @property
    def dist(self):
        return self.c_distance
    @dist.setter
    def dist(self, value):
        self.c_distance = int(value)
    
    @property
    def Face0_state(self):
        return self.hardware['Face0']

    @Face0_state.setter
    def Face0_state(self,value):
        if value:
            try:
                self.Face0 = 0xFFFF
                self.hardware['Face0'] = True
                self.debug_print("z Face Powered On")
            except Exception as e:
                self.debug_print('[WARNING][Face0]' + ''.join(traceback.format_exception(e)))
                self.hardware['Face0'] = False
        else:
            self.Face0 = 0x0000
            self.hardware['Face0'] = False
            self.debug_print("z+ Face Powered Off")
    
    @property
    def Face1_state(self):
        return self.hardware['Face1']

    @Face1_state.setter
    def Face1_state(self,value):
        if value:
            try:
                self.Face1 = 0xFFFF
                self.hardware['Face1'] = True
                self.debug_print("z- Face Powered On")
            except Exception as e:
                self.debug_print('[WARNING][Face1]' + ''.join(traceback.format_exception(e)))
                self.hardware['Face1'] = False
        else:
            self.Face1 = 0x0000
            self.hardware['Face1'] = False
            self.debug_print("z- Face Powered Off")
    
    @property
    def Face2_state(self):
        return self.hardware['Face2']

    @Face2_state.setter
    def Face2_state(self,value):
        if value:
            try:
                self.Face2 = 0xFFFF
                self.hardware['Face2'] = True
                self.debug_print("y+ Face Powered On")
            except Exception as e:
                self.debug_print('[WARNING][Face2]' + ''.join(traceback.format_exception(e)))
                self.hardware['Face2'] = False
        else:
            self.Face2 = 0x0000
            self.hardware['Face2'] = False
            self.debug_print("y+ Face Powered Off")

    @property
    def Face3_state(self):
        return self.hardware['Face3']

    @Face3_state.setter
    def Face3_state(self,value):
        if value:
            try:
                self.Face3 = 0xFFFF
                self.hardware['Face3'] = True
                self.debug_print("x- Face Powered On")
            except Exception as e:
                self.debug_print('[WARNING][Face3]' + ''.join(traceback.format_exception(e)))
                self.hardware['Face3'] = False
        else:
            self.Face3 = 0x0000
            self.hardware['Face3'] = False
            self.debug_print("x- Face Powered Off")

    @property
    def Face4_state(self):
        return self.hardware['Face4']

    @Face4_state.setter
    def Face4_state(self,value):
        if value:
            try:
                self.Face4 = 0xFFFF
                self.hardware['Face4'] = True
                self.debug_print("x+ Face Powered On")
            except Exception as e:
                self.debug_print('[WARNING][Face4]' + ''.join(traceback.format_exception(e)))
                self.hardware['Face4'] = False
        else:
            self.Face4 = 0x0000
            self.hardware['Face4'] = False
            self.debug_print("x+ Face Powered Off")   

    @property
    def RGB(self):
        return self.neopixel[0]
    @RGB.setter
    def RGB(self,value):
        if self.hardware['Neopixel']:
            try:
                self.neopixel[0] = value
            except Exception as e:
                self.debug_print('[WARNING]' + ''.join(traceback.format_exception(e)))

    @property
    def battery_voltage(self):
        if self.hardware['PWR']:
            voltage=0
            try:
                for _ in range(50):
                    voltage += self.pwr.bus_voltage
                return voltage/50 + 0.2 # volts and corection factor
            except Exception as e:
                self.debug_print('[WARNING][PWR Monitor]' + ''.join(traceback.format_exception(e)))
        else:
            self.debug_print('[WARNING] Power monitor not initialized')

    @property
    def system_voltage(self):
        if self.hardware['PWR']:
            voltage=0
            try:
                for _ in range(50):
                    voltage += (self.pwr.bus_voltage+self.pwr.shunt_voltage)
                return voltage/50 # volts
            except Exception as e:
                self.debug_print('[WARNING][PWR Monitor]' + ''.join(traceback.format_exception(e)))
        else:
            self.debug_print('[WARNING] Power monitor not initialized')

    @property
    def current_draw(self):
        """
        current draw from batteries
        NOT accurate if powered via USB
        """
        if self.hardware['PWR']:
            idraw=0
            try:
                for _ in range(50): # average 50 readings
                    idraw+=self.pwr.current
                return (idraw/50)
            except Exception as e:
                self.debug_print('[WARNING][PWR Monitor]' + ''.join(traceback.format_exception(e)))
        else:
            self.debug_print('[WARNING] Power monitor not initialized')

    @property
    def charge_current(self):
        """
        LTC4121 solar charging IC with charge current monitoring
        See Programming the Charge Current section
        """
        _charge = 0
        if self.solar_charging:
            _charge = self._ichrg.value * 3.3 / 65536
            _charge = ((_charge*988)/3010)*1000
        return _charge # mA

    @property
    def solar_charging(self):
        return not self._chrg.value

    @property
    def reset_vbus(self):
        # unmount SD card to avoid errors
        '''if self.hardware['SDcard']:
            try:
                umount('/sd')
                self.spi.deinit()
                time.sleep(3)
            except Exception as e:
                print('vbus reset error?' + ''.join(traceback.format_exception(e)))
                pass'''
        self._resetReg.drive_mode=digitalio.DriveMode.PUSH_PULL
        self._resetReg.value=1

    def distance(self):
        distance_mm = 0
        for _ in range(10):
            distance_mm += self.LiDAR.range
            time.sleep(0.01)
        self.debug_print('distance measured = {0}mm'.format(distance_mm/10))
        return distance_mm/10

    def log(self, msg):
        if self.hardware['SDcard']:
            with open(self.logfile, "a+") as f:
                t=int(time.monotonic())
                f.write('{}, {}\n'.format(t,msg))
    
    def Face_log(self, msg):
        if self.hardware['SDcard']:
            with open(self.Facelogfile, "a+") as f:
                t=int(time.monotonic())
                for face in msg:
                    f.write('{}, {}\n'.format(t,face))

    def print_file(self,filedir=None,binary=False):
        if filedir==None:
            return
        self.debug_print('\n--- Printing File: {} ---'.format(filedir))
        if binary:
            with open(filedir, "rb") as file:
                self.debug_print(file.read())
                self.debug_print('')
        else:
            with open(filedir, "r") as file:
                for line in file:
                    self.debug_print(line.strip())

    def timeout_handler(self):
        self.debug_print('Incrementing timeout register')
        if (self.micro.nvm[_TOUTS] + 1) >= 255:
            self.micro.nvm[_TOUTS]=0
            # soft reset
            self.micro.on_next_reset(self.micro.RunMode.NORMAL)
            self.micro.reset()
        else:
            self.micro.nvm[_TOUTS] += 1
            
    def heater_on(self):
        self.heater_en.value = True
        self.heater_ctrl.value = True
        
    def heater_off(self):
        self.heater_en.value = False
        self.heater_ctrl.value = False

    #Function is designed to read battery data and take some action to maintaint

    def battery_manager(self):
        self.debug_print(f'Started to manage battery')
        try:
            vbatt=self.battery_voltage
            #ichrg=self.charge_current
            idraw=self.current_draw
            vsys=self.system_voltage
            micro_temp=self.micro.cpu.temperature
            batt_temp= 30  #TESTTEST TEST TEST Positon 1 is the tip temperature
            
            self.debug_print('BATTERY Temp: {} C'.format(batt_temp))
            self.debug_print('MICROCONTROLLER Temp: {} C'.format(micro_temp))
        except Exception as e:
            self.debug_print("Error obtaining battery data: " + ''.join(traceback.format_exception(e)))

        try:
            if batt_temp < self.NORMAL_BATT_TEMP or micro_temp < self.NORMAL_MICRO_TEMP:
                #turn on heat pad
                self.debug_print("Turning heatpad on")
            elif batt_temp > self.NORMAL_TEMP :
                #make sure heat pad is lowered?
                if batt_temp > self.NORMAL_TEMP + 20 :
                    #turn heat pad off
                    self.debug_print(f'Initiating Battery Protection Protocol due to overheatting')

            #self.debug_print(f"charge current: ",ichrg, "A, and battery voltage: ",vbatt, "V")
            self.debug_print("draw current: {}mA, and battery voltage: {}V".format(idraw,vbatt))
            self.debug_print("system voltage: {}V".format(vsys))
            # if idraw>ichrg:
            #     self.debug_print("Beware! The Satellite is drawing more power than receiving")

            if vbatt < self.NORMAL_BATTERY_VOLTAGE:
                self.powermode('min')
                self.debug_print('CONTEXT SHIFT INTO MINIMUM POWER MODE: Attempting to shutdown unnecessary systems...')
            elif vbatt < self.CRITICAL_BATTERY_VOLTAGE:
                self.powermode('crit')
                self.debug_print('CONTEXT SHIFT INTO CRITICAL POWER MODE: Attempting to shutdown ALL systems...')
            elif vbatt > self.NORMAL_BATTERY_VOLTAGE+.5:
                self.powermode('max')
                self.debug_print('CONTEXT SHIFT INTO NORMAL POWER MODE: Attempting to revive necessary systems...')
            elif vbatt < self.NORMAL_BATTERY_VOLTAGE+.3 and self.power_mode=='maximum':
                self.powermode('norm')
                self.debug_print('CONTEXT SHIFT INTO MAXIMUM POWER MODE: Attempting to revive all systems...')
            
        except Exception as e:
            self.debug_print("Error in Battery Manager: " + ''.join(traceback.format_exception(e)))

    def powermode(self,mode):
        """
        Configure the hardware for minimum or normal power consumption
        Add custom modes for mission-specific control
        """
        if 'crit' in mode:
            self.RGB = (0,0,0)
            self.neopixel.brightness=0
            if self.hardware['Radio1']:
                self.radio1.sleep()
            self.enable_rf.value = False
            self.power_mode = 'critical'

        elif 'min' in mode:
            self.RGB = (0,0,0)
            self.neopixel.brightness=0
            if self.hardware['Radio1']:
                self.radio1.sleep()
            self.enable_rf.value = False

            self.power_mode = 'minimum'

        elif 'norm' in mode:
            self.enable_rf.value = True
            self.power_mode = 'normal'
            # don't forget to reconfigure radios, gps, etc...

        elif 'max' in mode:
            self.enable_rf.value = True
            self.power_mode = 'maximum'
    

    def new_file(self,substring,binary=False):
        '''
        substring something like '/data/DATA_'
        directory is created on the SD!
        int padded with zeros will be appended to the last found file
        '''
        if self.hardware['SDcard']:
            ff=''
            n=0
            _folder=substring[:substring.rfind('/')+1]
            _file=substring[substring.rfind('/')+1:]
            self.debug_print('Creating new file in directory: /sd{} with file prefix: {}'.format(_folder,_file))
            try: chdir('/sd'+_folder)
            except OSError:
                self.debug_print('Directory {} not found. Creating...'.format(_folder))
                try: mkdir('/sd'+_folder)
                except Exception as e:
                    self.debug_print("Error with creating new file: " + ''.join(traceback.format_exception(e)))
                    return None
            for i in range(0xFFFF):
                ff='/sd{}{}{:05}.txt'.format(_folder,_file,(n+i)%0xFFFF)
                try:
                    if n is not None:
                        stat(ff)
                except:
                    n=(n+i)%0xFFFF
                    # print('file number is',n)
                    break
            self.debug_print('creating file...'+str(ff))
            if binary: b='ab'
            else: b='a'
            with open(ff,b) as f:
                f.tell()
            chdir('/')
            return ff

    def burn(self,burn_num,dutycycle=0,freq=1000,duration=1):
        """
        Operate burn wire circuits. Wont do anything unless the a nichrome burn wire
        has been installed.

        IMPORTANT: See "Burn Wire Info & Usage" of https://pycubed.org/resources
        before attempting to use this function!

        burn_num:  (string) which burn wire circuit to operate, must be either '1' or '2'
        dutycycle: (float) duty cycle percent, must be 0.0 to 100
        freq:      (float) frequency in Hz of the PWM pulse, default is 1000 Hz
        duration:  (float) duration in seconds the burn wire should be on
        """
        # convert duty cycle % into 16-bit fractional up time
        dtycycl=int((dutycycle/100)*(0xFFFF))
        self.debug_print('----- BURN WIRE CONFIGURATION -----')
        self.debug_print('\tFrequency of: {}Hz\n\tDuty cycle of: {}% (int:{})\n\tDuration of {}sec'.format(freq,(100*dtycycl/0xFFFF),dtycycl,duration))
        # create our PWM object for the respective pin
        # not active since duty_cycle is set to 0 (for now)
        if '1' in burn_num:
            burnwire = pwmio.PWMOut(board.BURN_ENABLE, frequency=freq, duty_cycle=0)
        elif '2' in burn_num:
            burnwire = pwmio.PWMOut(board.BURN2, frequency=freq, duty_cycle=0)
        else:
            return False
        # Configure the relay control pin & open relay
        self._relayA.drive_mode=digitalio.DriveMode.PUSH_PULL
        self._relayA.value = 1
        self.RGB=(255,0,0)
        # Pause to ensure relay is open
        time.sleep(0.5)
        # Set the duty cycle over 0%
        # This starts the burn!
        burnwire.duty_cycle=dtycycl
        time.sleep(duration)
        # Clean up
        self._relayA.value = 0
        burnwire.duty_cycle=0
        self.RGB=(0,0,0)
        burnwire.deinit()
        self._relayA.drive_mode=digitalio.DriveMode.OPEN_DRAIN
        return True
    

print("Initializing CubeSat")
cubesat = Satellite()


