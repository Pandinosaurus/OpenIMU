
"""
    Actigraph data importer
    @authors Dominic Létourneau
    @date 18/04/2018

"""

from libopenimu.importers.BaseImporter import BaseImporter
import libopenimu.importers.actigraph as actigraph


from libopenimu.models.sensor_types import SensorType
from libopenimu.models.units import Units
from libopenimu.models.data_formats import DataFormat
from libopenimu.tools.timing import datetime_from_dotnet_ticks as ticksconverter
from libopenimu.tools.timing import timing

import numpy as np
import datetime


class ActigraphImporter(BaseImporter):
    def __init__(self, db_filename):
        super().__init__(db_filename)
        print('Actigraph Importer')

    @timing
    def load(self, filename):
        print('ActigraphImporter loading:', filename)
        result = actigraph.gt3x_importer(filename)
        return result

    @timing
    def import_to_database(self, result):
        [info, data] = result

        print(info)

        # Creating recordset
        # print(info['Start Date'], info['Last Sample Time'])
        start = int(info['Start Date'])
        stop = int(info['Last Sample Time'])
        print(start, stop)
        start_timestamp = ticksconverter(start)
        end_timestamp = ticksconverter(stop)
        print(start_timestamp, end_timestamp)

        recordset = self.add_recordset_to_db(info['Subject Name'], start_timestamp, end_timestamp)
        print(recordset)

        if data.__contains__('activity'):

            print('activity found')
            # Create sensor
            accelerometer_sensor = self.add_sensor_to_db(SensorType.ACCELEROMETER, 'Accelerometer', info['Device Type'],
                                                         'Unknown', info['Sample Rate'], 1)

            accelerometer_channels = list()

            # Create channels
            accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                                 DataFormat.FLOAT32, 'Accelerometer_Y'))

            accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                                 DataFormat.FLOAT32, 'Accelerometer_X'))

            accelerometer_channels.append(self.add_channel_to_db(accelerometer_sensor, Units.GRAVITY_G,
                                                                 DataFormat.FLOAT32, 'Accelerometer_Z'))

            # Should be 1970, epoch
            last_timestamp = 0
            all_timestamps = []
            value_dict = {}

            # Import data
            for epoch in data['activity']:
                # An epoch will contain a timestamp and array with each acc_x, acc_y, acc_z

                current_timestamp = epoch[0]
                # print('current_timestamp', current_timestamp, current_timestamp == (last_timestamp + 1))

                # Check for consecutive timestamps
                create_array = current_timestamp != (last_timestamp + 1)

                # Do not allow more than one hour of consecutive data
                if create_array is not True:
                    if current_timestamp - all_timestamps[-1] >= 3600:
                        create_array = True

                # Consecutive timestamps?
                if create_array is True:
                    all_timestamps.append(current_timestamp)
                    # Create list for all values for this timestamp
                    value_dict[current_timestamp] = [list(), list(), list()]

                # Get data
                samples = epoch[1]

                # Separate write for each channel
                for index in range(0, len(accelerometer_channels)):
                    # Using last timestamp to append data
                    value_dict[all_timestamps[-1]][index].append(samples[:, index])

                # Update timestamp
                last_timestamp = current_timestamp

            # Insert into DB as chunks of data
            # print('should insert records count: ', len(all_timestamps))
            # print('should insert data count:', len(value_dict))
            for timestamp in all_timestamps:
                for index in range(0, len(value_dict[timestamp])):
                    # print(index, timestamp, len(value_dict[timestamp][index]))
                    vector = np.concatenate(value_dict[timestamp][index])
                    # print('vector: ', len(vector), vector.shape, vector.dtype)
                    if len(vector) > 0:
                        self.add_sensor_data_to_db(recordset, accelerometer_sensor, accelerometer_channels[index],
                                                   datetime.datetime.fromtimestamp(timestamp), vector)

            # Flush DB
            self.db.flush()

        if data.__contains__('battery'):
            print('battery found')
            # Create sensor
            volt_sensor = self.add_sensor_to_db(SensorType.BATTERY, 'Battery', info['Device Type'], 'Unknown',
                                                0, 1)

            # Create channel
            volt_channel = self.add_channel_to_db(volt_sensor, Units.VOLTS, DataFormat.FLOAT32, 'Battery')

            for epoch in data['battery']:
                timestamp = datetime.datetime.fromtimestamp(epoch[0])
                value = np.float32(epoch[1])
                self.add_sensor_data_to_db(recordset, volt_sensor, volt_channel, timestamp, value)

            # Flush to DB (ram)
            self.db.flush()

        if data.__contains__('lux'):
            print('lux found')
            # Create sensor
            lux_sensor = self.add_sensor_to_db(SensorType.LUX, 'Lux', info['Device Type'], 'Unknown', 1, 1)

            # Create channel
            lux_channel = self.add_channel_to_db(lux_sensor, Units.LUX, DataFormat.FLOAT32, 'Lux')

            for epoch in data['lux']:
                timestamp = datetime.datetime.fromtimestamp(epoch[0])
                value = np.float32(epoch[1])
                self.add_sensor_data_to_db(recordset, lux_sensor, lux_channel, timestamp, value)

            # Flush to DB (ram)
            self.db.flush()

        # Write data to file
        self.db.commit()