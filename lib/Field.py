'''
This class handles communications

Authors: Nicole Maggard, Michael Pham, and Rachel Sarmiento
'''

import time
from debugcolor import co
import traceback

class Field():

    def debug_print(self,statement):
        if self.debug:
            print(co("[Field]" + statement, 'pink', 'bold'))
    def __init__(self,cubesat,debug):
        self.debug=debug
        self.cubesat=cubesat
        try:
            self.cubesat.enable_rf.value=True
            self.cubesat.radio1.spreading_factor=8
            self.cubesat.radio1.tx_power=23
            self.cubesat.radio1.low_datarate_optimize=False
            self.cubesat.radio1.node=0xfb
            self.cubesat.radio1.destination=0xfa
            self.cubesat.radio1.receive_timeout=10
            self.cubesat.radio1.enable_crc=True
            if self.cubesat.radio1.spreading_factor>8:
                self.cubesat.radio1.low_datarate_optimize=True
        except Exception as e:
            self.debug_print("Error Defining Radio features: " + ''.join(traceback.format_exception(e)))

    def fieldSide(self,msg,packlow,packhigh):

        pLow = str(packlow)   

        pHigh = str(packhigh)

        if packhigh < 10:
            pHigh = "00" + pHigh
        elif packhigh < 100:
            pHigh = "0" + pHigh
        else:
            pass

        self.debug_print("Sending packet " + pLow + "/" + pHigh + ": ")
        self.cubesat.radio1.send("packet" + pLow + "/" + pHigh + ": " + msg, keep_listening=True)

        self.debug_print("Listening for transmissions, " + str(self.cubesat.radio1.receive_timeout))
        heard_something = self.cubesat.radio1.await_rx(timeout=20)

        if heard_something:
            response = self.cubesat.radio1.receive(keep_listening=True)

            if response is not None :
                response_string = ''.join([chr(b) for b in response])
                if response_string == "True":
                    self.debug_print("packet received")
                    self.debug_print('msg: {}, RSSI: {}'.format(response_string,self.cubesat.radio1.last_rssi-137))
                    return True

                else:
                    self.debug_print("something, but not what we were looking for: \"",response_string,"\"")
                    return False

    #Function to send Spresense and Face data over radio:
    def Data_Transmit(self, type, data, packets=6):
        if type == "Face":
            count=1
            for i in data:
                self.debug_print(f"Sending face ", count, "/", packets, ": ", i)
                logic=self.fieldSide(str(i),count,packets)
                if not logic:
                    self.debug_print("I'm breaking from transmission!")
                    return False
                count+=1
            return True
        elif type == "Error":
            count=1
            for i in data:
                if self.debug :print(f"Sending Error ", count, "/", packets, ": ", i)
                logic=self.fieldSide(i,count,packets)
                if not logic:
                    self.debug_print("I'm breaking from transmission!")
                    return False
                count+=1
            return True
        else:
            self.debug_print(f"No type with name: ", type, " nothing transmitted")
            return False
    
    def Beacon(self, msg):
        try:
            self.debug_print("I am beaconing: " + str(msg))
            self.cubesat.radio1.send(msg)
        except Exception as e:
            self.debug_print("Tried Beaconing but encountered error: ".join(traceback.format_exception(e)))

    def troubleshooting(self):
        # this is for troubleshooting comms
        pass

    def __del__(self):
        self.debug_print("Object Destroyed!")