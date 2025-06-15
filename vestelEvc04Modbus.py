#!/usr/bin/env python

from pymodbus.client import ModbusTcpClient as ModbusClient

import logging
import sys
import time

def intToTime(time:int):
    hour = int(time / 10000)
    minute = int(time/100%60)
    second = time%60
    return  "%02d:%02d:%02d" % (hour, minute, second)

def getU32(bytes, highByte:int):
    return (bytes[highByte] << 16) + bytes[highByte+1]

def convertToString(bytes):
    return ''.join(chr(byte) for byte in bytes if byte != 0)

class Evc04Charger():
    def __init__(self, host:str):
        self.host = host
        self.client =None
        self.newMaxCurrent = None
        pass

    def connect(self):
        if(self.client == None):
            self.client = ModbusClient(host=self.host, port=502, unit_id=255)
            
        time.sleep(0.01)
        # if not self.client.connected():
        self.client.connect()
        return 

    def close(self):
        self.client.close()

    def getSystemInfo(self):
        # self.connect()
        self.systemInfo = {}

        self.serial = convertToString(self.client.read_input_registers(100, 25).registers)
        self.systemInfo["serial"] = self.serial

        self.systemInfo["chargepointId"] = convertToString(self.client.read_input_registers(130, 50).registers)
        self.systemInfo["brand"] = convertToString(self.client.read_input_registers(199, 10).registers)
        
        self.model = convertToString(self.client.read_input_registers(210, 5).registers)
        self.systemInfo["model"] = self.model

        self.firmware = convertToString(self.client.read_input_registers(230, 50).registers)
        self.systemInfo["firmware"] = self.firmware

        logging.info("Connected to device %s" % self.systemInfo)
        # self.close()

    def readSystemState(self):
        systemState = {}
        systemStateResisters = self.client.read_input_registers(1000, 7)
        self.cpState = systemStateResisters.registers[0]
        systemState["state"] = self.cpState
        # 0: "Available",
        # 1: "Preparing",
        # 2: "Charging",
        # 3: "SuspendedEVSE",
        # 4: "SuspendedEV",
        # 5: "Finishing",
        # 6: "Reserved",
        # 7: "Unavailable",
        # 8: "Faulted"

        systemState["chargingState"] = systemStateResisters.registers[1]
        # 0: Not Charging, State Ax, Bx, Dx or C1
        # 1: Charging, state C2

        systemState["equipmentState"] = systemStateResisters.registers[2]
        # 0: Initializing
        # 1: Running
        # 2: Fault
        # 3: Disabled
        # 4: Updating
        self.cableState = systemStateResisters.registers[4]
        systemState["cableState"] = self.cableState
        # 0: Cable not connected
        # 1: Cable connected, vehicle not connected
        # 2: Cable connected, vehicle connected
        # 3: Cable connected, vehicle connected, cable locked

        systemState["evseFaultCode"] = systemStateResisters.registers[6]
        # 0: No fault
        # Other: Fault code
        return systemState

    def readPowerData(self):
        powerData = {}
        powerDataRegisters = self.client.read_input_registers(1008, 11)
        powerData["currentL1"] = powerDataRegisters.registers[0]
        powerData["currentL2"] = powerDataRegisters.registers[2]
        powerData["currentL3"] = powerDataRegisters.registers[4]

        powerData["voltageL1"] = powerDataRegisters.registers[6]
        powerData["voltageL2"] = powerDataRegisters.registers[8]
        powerData["voltageL3"] = powerDataRegisters.registers[10]

        powerDataRegisters = self.client.read_input_registers(1020, 14)
        powerData["powerTotal"] = getU32(powerDataRegisters.registers, 0)
        powerData["powerL1"]  = getU32(powerDataRegisters.registers, 4)
        powerData["powerL2"]  = getU32(powerDataRegisters.registers, 8)
        powerData["powerL3"]  = getU32(powerDataRegisters.registers, 12)
        powerData["powerL3"]  = getU32(powerDataRegisters.registers, 12)
        return powerData

    def readSessionData(self):
        sessionData = {}
        sessionDataRegisters = self.client.read_input_registers(1502, 12)
        sessionData["sessionEnergy"] = getU32(sessionDataRegisters.registers, 0)
        sessionData["sessionStart"] = intToTime(getU32(sessionDataRegisters.registers, 2))
        sessionData["sessionDuration"] = getU32(sessionDataRegisters.registers, 6)
        sessionData["sessionEnd"] = intToTime(getU32(sessionDataRegisters.registers, 10))
        return sessionData
    
    def readMaxCurrent(self):
        result = {}
        registers = self.client.read_holding_registers(5004, 1).registers
        logging.debug("Max Current %s" % registers)
        self.maxCurrent = registers[0]
        result['maxCurrent'] = self.maxCurrent
        return result
    
    def updateValues(self):
        # set bit to mark master as alive
        self.client.write_register(6000, 1)

        if self.newMaxCurrent != None:
            logging.info("New max current will be set to: %s " % self.newMaxCurrent)
            self.client.write_register(5004,self.newMaxCurrent)
            self.newMaxCurrent = None

    def setMaxCurrent(self, value):
        self.newMaxCurrent = value

    def readRelevantData(self):
        self.connect()
        try:
            result = {}
            result.update(self.readSystemState())
            result.update(self.readPowerData())
            result.update(self.readSessionData())
            result.update(self.readMaxCurrent())
            logging.info(result)  # Print the value read   
        except AttributeError as msg:
            logging.error(msg)
            # self.close()
            return None
        # self.close()
        return result
    

    def getFirmwareversion(self):
        return self.firmware
    
    def getModel(self):
        return self.model
    
    def getSerial(self):
        return self.serial

    def getVrmStatus(self):
        cableState = self.cableState
        if cableState == 0:
                return 0
        if cableState == 1:
                return 0
        if cableState == 2 or 3:
            logging.debug("Cable state: %s" % cableState)
            cpState = self.cpState
            if cpState == 0:
                return 1
            if cpState == 1:
                return 6
            if cpState == 2:
                return 2
            if cpState == 3:
                return 6
            if cpState == 4:
                return 20
            if cpState == 5:
                return 3
            if cpState == 6 or 7 or 8:
                return 10
                

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    charger = Evc04Charger("192.168.178.96")
    charger.connect()
    logging.info(charger.getSystemInfo())
    logging.info(charger.getSerial())
    print(charger.getSerial())
    charger.readRelevantData()