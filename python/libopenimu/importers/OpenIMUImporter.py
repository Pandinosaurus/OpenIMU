from libopenimu.importers.BaseImporter import BaseImporter
from libopenimu.models.sensor_types import SensorType
from libopenimu.models.units import Units
from libopenimu.models.Recordset import Recordset
from libopenimu.models.data_formats import DataFormat
from libopenimu.tools.timing import timing
from libopenimu.db.DBManager import DBManager
from libopenimu.models.Participant import Participant

import numpy as np
import datetime

import struct
import sys
import binascii
import datetime
import string


class OpenIMUImporter(BaseImporter):
    def __init__(self, manager: DBManager, participant: Participant):
        super().__init__(manager, participant)
        print('OpenIMU Importer')
        # No recordsets when starting
        self.recordsets = []

    @timing
    def load(self, filename):
        print('OpenIMUImporter.load')
        results = {}
        with open(filename, "rb") as file:
            print('Loading File: ', filename)
            results = self.readDataFile(file)

        print('Done!')
        return results

    @timing
    def import_imu_to_database(self, timestamp, data: list):

        # Create sensors
        accelerometer_sensor = self.add_sensor_to_db(SensorType.ACCELEROMETER, 'Accelerometer',
                                                     'OpenIMU-Device',
                                                     'Unknown', 50, 1)

        accelerometer_channels = list()

        # Create channels
        accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                             DataFormat.FLOAT32, 'Accelerometer_X'))

        accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                             DataFormat.FLOAT32, 'Accelerometer_Y'))

        accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                             DataFormat.FLOAT32, 'Accelerometer_Z'))

    @timing
    def import_power_to_database(self, timestamp, data: list):
        pass

    @timing
    def import_gps_to_database(self, timestamp, data: list):
        pass

    @timing
    def import_baro_to_database(self, timestamp, data: list):
        pass


    @timing
    def import_to_database(self, result):
        print('OpenIMUImporter.import_to_database')

        for timestamp in result:
            if result[timestamp].__contains__('imu'):
                # print('contains imu')
                self.import_imu_to_database(timestamp, result[timestamp]['imu'])
            if result[timestamp].__contains__('power'):
                # print('contains power')
                self.import_power_to_database(timestamp, result[timestamp]['imu'])
            if result[timestamp].__contains__('gps'):
                # print('contains gps')
                self.import_gps_to_database(timestamp, result[timestamp]['imu'])
            if result[timestamp].__contains__('baro'):
                # print('contains baro')
                self.import_baro_to_database(timestamp, result[timestamp]['imu'])

    def processImuChunk(self, chunk, debug=False):
        data = struct.unpack("9f", chunk)

        if debug:
            print("IMU: ", data)

        return data

    def processTimestampChunk(self, chunk, debug=False):
        [timestamp] = struct.unpack("i", chunk)
        if debug:
            print(datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'))
        return timestamp

    def processGPSChunk(self, chunk, debug=False):
        data = struct.unpack("?3f", chunk)
        if debug:
            print("GPS: ", data)
        return data

    def processBarometerChunk(self, chunk, debug=False):
        data = struct.unpack("2f", chunk)
        if debug:
            print("BARO: ", data[0], data[1])
        return data

    def processPowerChunk(self, chunk, debug=False):
        data = struct.unpack("2f", chunk)
        if debug:
            print("POWER: ", data[0], data[1])
        return data

    def readDataFile(self, file, debug=False):
        n = 0
        results = {}
        timestamp = None

        # Todo better than while 1?
        while True:

            chunk = file.read(1)
            if len(chunk) < 1:
                print("Reached end of file")
                break

            (headChar) = struct.unpack("c", chunk)
            # print('headchar ', headChar)

            if headChar[0] == b'h':
                n = n + 1
                print("New log stream")
            elif headChar[0] == b't':
                n = n + 1
                chunk = file.read(struct.calcsize("i"))
                current_timestamp = self.processTimestampChunk(chunk)

                if timestamp is None:
                    timestamp = current_timestamp
                else:
                    if current_timestamp >= timestamp + 3600:  # Max 1 hour of data per timestamp
                        timestamp = current_timestamp

                # Initialize data structure at this timestamp
                if not results.__contains__(timestamp):
                    print("init timestamp = ", timestamp)
                    results[timestamp] = {}
                    results[timestamp]['gps'] = []
                    results[timestamp]['power'] = []
                    results[timestamp]['imu'] = []
                    results[timestamp]['baro'] = []

            elif headChar[0] == b'i':
                n = n + 1
                chunk = file.read(struct.calcsize("9f"))
                data = self.processImuChunk(chunk)
                if timestamp is not None:
                    results[timestamp]['imu'].append(data)

            elif headChar[0] == b'g':
                n = n + 1
                chunk = file.read(struct.calcsize("?3f"))
                data = self.processGPSChunk(chunk)
                if timestamp is not None:
                    results[timestamp]['gps'].append(data)

            elif headChar[0] == b'p':
                n = n + 1
                chunk = file.read(struct.calcsize("2f"))
                data = self.processPowerChunk(chunk)
                if timestamp is not None:
                    results[timestamp]['power'].append(data)

            elif headChar[0] == b'b':
                n = n + 1
                chunk = file.read(struct.calcsize("2f"))
                data = self.processBarometerChunk(chunk)
                if timestamp is not None:
                    results[timestamp]['baro'].append(data)

            else:
                print("Unrecognised chunk :", headChar[0])
                break

        return results