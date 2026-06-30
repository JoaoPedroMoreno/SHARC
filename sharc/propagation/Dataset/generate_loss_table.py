# -*- coding: utf-8 -*-
"""
Created on Thu Aug 31 12:59:12 2017

"""

import os
import csv
import numpy as np
from sharc.propagation.propagation_p619 import PropagationP619

# Constants
frequency_MHz = 2155.0
earth_station_alt_m = 200.0
earth_station_lat_deg = -25.5549751
season = "SUMMER"
city_name = "FOZ"
verbose = False

apparent_elevation = np.arange(0, 90)

# Initialize the propagation model
random_number_gen = np.random.RandomState(101)
propagation = PropagationP619(
    random_number_gen=random_number_gen,
    earth_station_alt_m=earth_station_alt_m,
    earth_station_lat_deg=earth_station_lat_deg,
    season=season,
    mean_clutter_height='low',
    below_rooftop=0.0,
)

output_dir = os.path.dirname(__file__)
lookup_table_name = f'{city_name}_{int(frequency_MHz)}_{int(earth_station_alt_m)}m.csv'
output_file = os.path.join(output_dir, lookup_table_name)

# Calculate the loss for each elevation angle and write incrementally.
# Set verbose=True above if you want progress messages while generating.
with open(output_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['apparent_elevation', 'loss'])
    for elevation in apparent_elevation:
        if verbose:
            print(f"Calculating elevation {elevation} deg...", flush=True)
        loss = propagation._get_atmospheric_gasses_loss(
            frequency_MHz=frequency_MHz,
            apparent_elevation=elevation,
            lookupTable=False,
        )
        writer.writerow([elevation, loss])
        file.flush()

if verbose:
    print(f"Results saved to {output_file}")
