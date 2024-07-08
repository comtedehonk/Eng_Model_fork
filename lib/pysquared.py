"""
CircuitPython driver for PySquared satellite board.
PySquared Hardware Version: mainboard-v01
CircuitPython Version: 8.0.0 alpha
Library Repo:

* Author(s): Nicole Maggard, Michael Pham, and Rachel Sarmiento
"""

#height=640
#width=480
#quality=54
#buf=bytearray(height*width//quality)

# Common CircuitPython Libs
import board, microcontroller
import busio, time, traceback
import digitalio
from debugcolor import co
import gc
from ptp import AsyncPacketTransferProtocol as APTP
from ftp import FileTransferProtocol as FTP



gc.enable()

# Hardware Specific Libs
import pysquared_rfm9x  # Radio
import neopixel         # RGB LED
import adafruit_tca9548a # I2C Multiplexer
import adafruit_pct2075 # Temperature Sensor
import adafruit_vl6180x # LiDAR Distance Sensor for Antenna
import adafruit_lsm303_accel
import adafruit_lis2mdl
from adafruit_lsm6ds import lsm6dsox
import adafruit_ov5640

# CAN Bus Import
from adafruit_mcp2515 import MCP2515 as CAN

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

#SEND_BUFF=bytearray(252)

class Satellite:
    # General NVM counters
    c_boot      = multiBitFlag(register=_BOOTCNT, lowest_bit=0,num_bits=8)
    c_vbusrst   = multiBitFlag(register=_VBUSRST, lowest_bit=0,num_bits=8)
    c_state_err = multiBitFlag(register=_STATECNT,lowest_bit=0,num_bits=8)
    c_distance  = multiBitFlag(register=_DIST,    lowest_bit=0,num_bits=8)
    c_ichrg     = multiBitFlag(register=_ICHRG,   lowest_bit=0,num_bits=8)

    # Define NVM flags
    f_softboot  = bitFlag(register=_FLAG,bit=0)
    f_solar     = bitFlag(register=_FLAG,bit=1)
    f_burnarm   = bitFlag(register=_FLAG,bit=2)
    f_brownout  = bitFlag(register=_FLAG,bit=3)
    f_triedburn = bitFlag(register=_FLAG,bit=4)
    f_shtdwn    = bitFlag(register=_FLAG,bit=5)
    f_burned    = bitFlag(register=_FLAG,bit=6)
    f_fsk       = bitFlag(register=_FLAG,bit=7)

    def debug_print(self,statement):
        if self.debug:
            print(co("[pysquared]" + str(statement), "red", "bold"))

    def __init__(self):
        """
        Big init routine as the whole board is brought up.
        """
        self.debug=True #Define verbose output here. True or False
        self.BOOTTIME= 1577836800
        self.debug_print(f'Boot time: {self.BOOTTIME}s')
        self.CURRENTTIME=self.BOOTTIME
        self.UPTIME=0
        self.heating=False
        self.is_licensed=True
        self.NORMAL_TEMP=20
        self.NORMAL_BATT_TEMP=1#Set to 0 BEFORE FLIGHT!!!!!
        self.NORMAL_MICRO_TEMP=20
        self.NORMAL_CHARGE_CURRENT=0.5
        self.NORMAL_BATTERY_VOLTAGE=6.9#6.9
        self.CRITICAL_BATTERY_VOLTAGE=6.6#6.6
        #self.buf=memoryview(buf)
        self.data_cache={}
        self.filenumbers={}
        self.image_packets=0
        self.urate = 115200
        self.vlowbatt=6.0
        #self.send_buff = memoryview(SEND_BUFF)
        self.micro=microcontroller
        self.radio_cfg = {
                        'id':   0xfa,
                        'gs':   0xfb,
                        'id':   0xfa,
                        'gs':   0xfb,
                        'freq': 437.4,
                        'sf':   8,
                        'bw':   125,
                        'cr':   8,
                        'pwr':  23,
                        'st' :  80000
        }
        self.hardware = {
                       'ACCEL':  False,
                       'GYRO':   False,
                       'MAG':    False,
                       'Radio1': False,
                       'SDcard': False,
                       'CAN':    False,
                       'LiDAR':  False,
                       'WDT':    False,
                       'SOLAR':  False,
                       'PWR':    False,
                       'FLD':    False,
                       'TEMP':   False,
                       'Face0':  False,
                       'Face1':  False,
                       'Face2':  False,
                       'Face3':  False,
                       'Face4':  False,
                       'Camera': False,
                       }

        # Define SPI,I2C,UART | paasing I2C1 to BigData
        try:
            self.i2c0 = busio.I2C(board.I2C0_SCL,board.I2C0_SDA,timeout=5)
            self.spi0 = busio.SPI(board.SPI0_SCK,board.SPI0_MOSI,board.SPI0_MISO)
            self.i2c1 = busio.I2C(board.I2C1_SCL,board.I2C1_SDA,timeout=5,frequency=100000)
            self.uart = busio.UART(board.TX,board.RX,baudrate=self.urate)
        except Exception as e:
            self.debug_print("ERROR INITIALIZING BUSSES: " + ''.join(traceback.format_exception(e)))

        if self.c_boot > 250:
            self.c_boot=0

        if self.f_fsk:
            self.debug_print("Fsk going to false")
            self.f_fsk=False
        
        if self.f_softboot:
            self.f_softboot=False

        # Define radio
        _rf_cs1 = digitalio.DigitalInOut(board.SPI0_CS0)
        _rf_rst1 = digitalio.DigitalInOut(board.RF1_RST)
        self.radio1_DIO0=digitalio.DigitalInOut(board.RF1_IO0)
        self.radio1_DIO4=digitalio.DigitalInOut(board.RF1_IO4)
        _rf_cs1.switch_to_output(value=True)
        _rf_rst1.switch_to_output(value=True)
        self.radio1_DIO0.switch_to_input()
        self.radio1_DIO4.switch_to_input()

        # Initialize CAN Transceiver
        try:
            self.spi0cs2 = digitalio.DigitalInOut(board.SPI0_CS2)
            self.spi0cs2.switch_to_output()
            self.can_bus = CAN(self.spi0, self.spi0cs2, loopback=True, silent=True)
            self.hardware['CAN']=True

        except Exception as e:
            self.debug_print("[ERROR][CAN TRANSCEIVER]" + ''.join(traceback.format_exception(e)))

        # Initialize Neopixel
        try:
            self.neopixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2, pixel_order=neopixel.GRB)
            self.neopixel[0] = (0,0,255)
            self.hardware['Neopixel'] = True
        except Exception as e:
            self.debug_print('[WARNING][Neopixel]' + ''.join(traceback.format_exception(e)))

        # Initialize IMU
        try:
            self.accel = adafruit_lsm303_accel.LSM303_Accel(self.i2c1)
            self.hardware['ACCEL'] = True
        except Exception as e:
            self.debug_print('[ERROR][ACCEL]' + ''.join(traceback.format_exception(e)))
        try:
            self.mag = adafruit_lis2mdl.LIS2MDL(self.i2c1)
            self.hardware['MAG'] = True
        except Exception as e:
            self.debug_print('[ERROR][MAG]' + ''.join(traceback.format_exception(e)))
        try:
            self.gyro = lsm6dsox.LSM6DSOX(self.i2c1,address=0x6b)
            self.hardware['GYRO'] = True
        except Exception as e:
            self.debug_print('[ERROR][GYRO]' + ''.join(traceback.format_exception(e)))

        # Initialize PCT2075 Temperature Sensor
        try:
            self.pct = adafruit_pct2075.PCT2075(self.i2c1, address=0x4F)
            self.hardware['TEMP'] = True
        except Exception as e:
            self.debug_print('[ERROR][TEMP SENSOR]' + ''.join(traceback.format_exception(e)))

        # Initialize TCA
        try:
            self.tca = adafruit_tca9548a.TCA9548A(self.i2c1,address=int(0x77))
            for channel in range(8):
                if self.tca[channel].try_lock():
                    self.debug_print("Channel {}:".format(channel))
                    addresses = self.tca[channel].scan()
                    print([hex(address) for address in addresses if address != 0x70])
                    self.tca[channel].unlock()
        except Exception as e:
            self.debug_print("[ERROR][TCA]" + ''.join(traceback.format_exception(e)))

        # Initialize LiDAR
        '''try:
            self.LiDAR = adafruit_vl6180x.VL6180X(self.i2c1,offset=0)
            self.hardware['LiDAR'] = True
        except Exception as e:
            self.debug_print('[ERROR][LiDAR]' + ''.join(traceback.format_exception(e)))
            '''
        # Initialize radio #1 - UHF
        try:
            self.radio1 = pysquared_rfm9x.RFM9x(self.spi0, _rf_cs1, _rf_rst1,self.radio_cfg['freq'],code_rate=8,baudrate=1320000)
            # Default LoRa Modulation Settings
            # Frequency: 437.4 MHz, SF7, BW125kHz, CR4/8, Preamble=8, CRC=True
            self.radio1.dio0=self.radio1_DIO0
            #self.radio1.dio4=self.radio1_DIO4
            self.radio1.max_output=True
            self.radio1.tx_power=self.radio_cfg['pwr']
            self.radio1.spreading_factor=self.radio_cfg['sf']
            self.radio1.node=self.radio_cfg['id']
            self.radio1.destination=self.radio_cfg['gs']
            self.radio1.enable_crc=True
            self.radio1.ack_delay=0.2
            if self.radio1.spreading_factor > 9: self.radio1.preamble_length = self.radio1.spreading_factor
            self.hardware['Radio1'] = True
        except Exception as e:
            self.debug_print('[ERROR][RADIO 1]' + ''.join(traceback.format_exception(e)))
        
        #initialize ptp
        try:
            self.ptp = APTP(self.radio1, packet_size=245, timeout=13.7, log=False)
            self.ftp = FTP(self.ptp, chunk_size =243, packet_delay=0, log=False )
        except Exception as e:
            print(e)
        
        # Initialize OV5640 self.camera
        try:
            self.cam = adafruit_ov5640.OV5640(
                self.i2c0,
                data_pins=(
                    board.D2,
                    board.D3,
                    board.D4,
                    board.D5,
                    board.D6,
                    board.D7,
                    board.D8,
                    board.D9,
                ),
                clock=board.PC,
                vsync=board.VS,
                href=board.HS,
                mclk=None,
                shutdown=None,
                reset=None,
                size=adafruit_ov5640.OV5640_SIZE_QVGA
            )
            self.cam.colorspace = adafruit_ov5640.OV5640_COLOR_JPEG
            self.cam.flip_y = False
            self.cam.flip_x = False
            self.cam.test_pattern = False

            self.cam.effect=0
            self.cam.exposure_value=-2
            self.cam.white_balance=2
            self.cam.night_mode=False
            self.cam.quality=20
            self.hardware['Camera'] = True
        except Exception as e:
            self.debug_print('[ERROR][OV5640]' + ''.join(traceback.format_exception(e)))

        # Prints init state of PySquared hardware
        self.debug_print(str(self.hardware))

        # set PyCubed power mode
        self.power_mode = 'normal'

    def reinit(self,dev):
        if dev=='pwr':
            self.pwr.__init__(self.i2c1)
        elif dev=='fld':
            self.faces.__init__(self.i2c1)
        elif dev=='lidar':
            self.LiDAR.__init__(self.i2c1)
        else:
            self.debug_print('Invalid Device? ->' + str(dev))

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
    def RGB(self):
        return self.neopixel[0]
    @RGB.setter
    def RGB(self,value):
        if self.hardware['Neopixel']:
            try:
                self.neopixel[0] = value
            except Exception as e:
                self.debug_print('[ERROR]' + ''.join(traceback.format_exception(e)))
        else:
            self.debug_print('[WARNING] neopixel not initialized')

    @property
    def uptime(self):
        self.CURRENTTIME=const(time.time())
        return self.CURRENTTIME-self.BOOTTIME

    @property
    def reset_vbus(self):
        # unmount SD card to avoid errors
        if self.hardware['SDcard']:
            try:
                umount('/sd')
                self.spi.deinit()
                time.sleep(3)
            except Exception as e:
                self.debug_print('error unmounting SD card' + ''.join(traceback.format_exception(e)))
        try:
            self._resetReg.drive_mode=digitalio.DriveMode.PUSH_PULL
            self._resetReg.value=1
        except Exception as e:
            self.debug_print('vbus reset error: ' + ''.join(traceback.format_exception(e)))
    
    @property
    def internal_temperature(self):
        return self.pct.temperature

    def distance(self):
        if self.hardware['LiDAR']:
            try:
                distance_mm = 0
                for _ in range(10):
                    distance_mm += self.LiDAR.range
                    time.sleep(0.01)
                self.debug_print('distance measured = {0}mm'.format(distance_mm/10))
                return distance_mm/10
            except Exception as e:
                self.debug_print('LiDAR error: ' + ''.join(traceback.format_exception(e)))
        else:
            self.debug_print('[WARNING] LiDAR not initialized')
        return 0
    
    def check_reboot(self):
        self.UPTIME=self.uptime
        self.debug_print(str("Current up time: "+str(self.UPTIME)))
        if self.UPTIME>86400:
            self.reset_vbus()


print("Initializing CubeSat")
cubesat = Satellite()
