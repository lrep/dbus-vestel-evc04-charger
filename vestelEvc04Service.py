#!/usr/bin/env python3

"""
A class to put a simple service on the dbus, according to victron standards, with constantly updating
paths. See example usage below. It is used to generate dummy data for other processes that rely on the
dbus. See files in dbus_vebus_to_pvinverter/test and dbus_vrm/test for other usage examples.

To change a value while testing, without stopping your dummy script and changing its initial value, write
to the dummy data via the dbus. See example.

https://github.com/victronenergy/dbus_vebus_to_pvinverter/tree/master/test
"""
from gi.repository import GLib
import platform
import argparse
import logging
import sys
import os
import pymodbus
import configparser # for config/ini file
from  vestelEvc04Modbus import Evc04Charger

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

class VestelEvc04Service(object):
    def __init__(self, servicename, deviceinstance, paths, productname='Vestel EVC04', connection='Vestel EVC04 Service'):
        config = self._getConfig()

        deviceinstance = int(config['DEFAULT']['Deviceinstance'])
        host = config['ONPREMISE']['Host']
        
        self._dbusservice = VeDbusService("{}.evc04_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        self.evc04Charger = Evc04Charger(host)
        self.evc04Charger.connect()
        
        self.evc04Charger.getSystemInfo()

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', self.evc04Charger.getFirmwareversion())
        self._dbusservice.add_path('/Model', self.evc04Charger.getModel())

        for path, settings in self._paths.items():
            self._dbusservice.add_path(path, settings['initial'], writeable=False, onchangecallback=self._handlechangedvalue)

        self._dbusservice.add_path('/SetCurrent', None, writeable=True, onchangecallback=self._handleCurrentChanged)

        refreshRate = int(config['DEFAULT']['RefreshRate'])
        MIN_REFRESH_RATE = 250
        if not refreshRate or refreshRate < MIN_REFRESH_RATE:
            refreshRate = MIN_REFRESH_RATE
        GLib.timeout_add(refreshRate, self._update) # pause at least 250ms before the next request

    def update(self, path, value):
        self._dbusservice[path] = value
        logging.debug("%s: %s" % (path, value))

    def _update(self):
        try:
            # self.evc04Charger.connect()
            evc04Data = self.evc04Charger.readRelevantData()
            if evc04Data == None:  
                logging.debug("Will skip an update")
                return True
            
            self.update('/Ac/Energy/Forward', evc04Data['sessionEnergy']/1000)
            self.update('/Ac/Power', evc04Data['powerTotal'])
            self.update('/Ac/L1/Power', evc04Data['powerL1'])
            self.update('/Ac/L2/Power', evc04Data['powerL2'])
            self.update('/Ac/L3/Power', evc04Data['powerL3'])
            self.update('/Status', self.evc04Charger.getVrmStatus())
            self.update('/MaxCurrent', self.evc04Charger.maxCurrent)
            self.update('/ChargingTime', evc04Data['sessionDuration'])

            self.evc04Charger.updateValues()
        except pymodbus.exceptions.ConnectionException as msg:
            logging.warn("Cannot connect to evc04 %s" % self.evc04Charger.host)
        # self.evc04Charger.close()
        return True

    def _handlechangedvalue(self, path, value):
        logging.warn("someone else updated %s to %s" % (path, value))
        return True # accept the change
    
    def _handleCurrentChanged(self, path, value):
        logging.info("Max current will be changed to %s" % value)
        self.evc04Charger.setMaxCurrent(value)
        return True

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config

# === All code below is to simply run it from the commandline for debugging purposes ===

# It will created a dbus service called com.victronenergy.pvinverter.output.
# To try this on commandline, start this program in one terminal, and try these commands
# from another terminal:
# dbus com.victronenergy.pvinverter.output
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward GetValue
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward SetValue %20
#
# Above examples use this dbus client: http://code.google.com/p/dbus-tools/wiki/DBusCli
# See their manual to explain the % in %20

def main():
    #configure logging
    logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S',
                                level=logging.INFO,
                                handlers=[
                                    logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                    logging.StreamHandler()
                                ])
    logging.basicConfig(level=logging.INFO)
    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    pvac_output = VestelEvc04Service(
        servicename='com.victronenergy.evcharger',
        deviceinstance=0,
        paths={
    '/Ac/Power':                            {'initial': 0},
    '/Ac/L1/Power':                         {'initial': 0},
    '/Ac/L2/Power':                         {'initial': 0},
    '/Ac/L3/Power':                         {'initial': 0},
    '/Ac/Energy/Forward':                   {'initial': 1},
    '/Current':                             {'initial': 6},
    '/MaxCurrent':                          {'initial': 16},

    '/AutoStart':                           {'initial': 1},
    '/ChargingTime':                        {'initial': 0},
    '/EnableDisplay':                       {'initial': 1},
    '/Mode':                                {'initial': 0},
    '/Role':                                {'initial': 0},
    '/StartStop':                           {'initial': 1},
    '/Position':                            {'initial': 1},
    
    '/Status':                              {'initial': 1}
        })

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()