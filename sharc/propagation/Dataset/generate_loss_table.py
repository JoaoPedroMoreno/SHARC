# -*- coding: utf-8 -*-
"""
Generate P.619 atmospheric-gas-loss lookup tables for the Paraguay/FOZ
campaign at the DC-MSS center frequencies used in the guard-band sweep.
"""

import os
import csv
import numpy as np
from sharc.propagation.propagation_p619 import PropagationP619

# Frequencies required by the current 80-to-0 MHz guard-band sweep [MHz].
# Existing tables are preserved; only missing files are calculated.
guard_bands_MHz = list(range(80, -1, -5))
frequencies_MHz = [2197.5 - guard_band for guard_band in guard_bands_MHz]

# Constants kept from the original script
earth_station_alt_m = 200.0
earth_station_lat_deg = -25.5549751
season = "SUMMER"
city_name = "FOZ"
verbose = False

apparent_elevation = np.arange(0, 90)

# Initialize the propagation model once
random_number_gen = np.random.RandomState(101)
propagation = PropagationP619(
    random_number_gen=random_number_gen,
    earth_station_alt_m=earth_station_alt_m,
    earth_station_lat_deg=earth_station_lat_deg,
    season=season,
    mean_clutter_height="low",
    below_rooftop=0.0,
)

output_dir = os.path.dirname(__file__)

# Generate one CSV for each frequency
for frequency_MHz in frequencies_MHz:
    lookup_table_name = (
        f"{city_name}_{int(frequency_MHz)}_{int(earth_station_alt_m)}m.csv"
    )
    output_file = os.path.join(output_dir, lookup_table_name)

    if os.path.isfile(output_file):
        if verbose:
            print(f"Skipping existing table: {lookup_table_name}", flush=True)
        continue

    if verbose:
        print(
            f"Generating {lookup_table_name} "
            f"for {frequency_MHz} MHz...",
            flush=True,
        )

    with open(output_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["apparent_elevation", "loss"])

        for elevation in apparent_elevation:
            if verbose:
                print(
                    f"  Calculating elevation {elevation} deg...",
                    flush=True,
                )

            loss = propagation._get_atmospheric_gasses_loss(
                frequency_MHz=frequency_MHz,
                apparent_elevation=elevation,
                lookupTable=False,
            )

            writer.writerow([elevation, loss])
            file.flush()

    if verbose:
        print(f"Saved: {output_file}", flush=True)

if verbose:
    print("All lookup tables generated.")
