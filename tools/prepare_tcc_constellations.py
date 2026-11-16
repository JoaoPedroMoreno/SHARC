"""Prepare t=0 orbital illustrations using campaign parameters and OrbitModel."""
from pathlib import Path
import importlib.util
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharc.parameters.parameters_orbit import ParametersOrbit
from sharc.satellite.ngso.orbit_model import OrbitModel


def main():
    source = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/generate.py"
    spec = importlib.util.spec_from_file_location("campaign07_figure_parameters", source)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    output = ROOT / "figuras/tcc_constellations_capture"
    output.mkdir(exist_ok=True)
    for altitude in (340, 525):
        cfg = generator.build(altitude, 20, .2, "BASELINE")
        orbit = cfg["imt"]["topology"]["mss_dc"]["orbits"][0]
        p = ParametersOrbit()
        for key, value in orbit.items():
            setattr(p, key, value)
        model = OrbitModel(Nsp=p.sats_per_plane, Np=p.n_planes,
            phasing=p.phasing_deg, long_asc=p.long_asc_deg, omega=p.omega_deg,
            delta=p.inclination_deg, hp=p.perigee_alt_km, ha=p.apogee_alt_km,
            Mo=p.initial_mean_anomaly, model_time_as_random_variable=p.model_time_as_random_variable,
            t_min=p.t_min, t_max=p.t_max)
        positions = model.get_orbit_positions_time_instant(0)
        satellites = np.column_stack([np.asarray(positions[key]).ravel() for key in ("lon", "lat", "alt")])
        assert len(satellites) == p.n_planes * p.sats_per_plane
        assert np.isfinite(satellites).all()
        assert np.allclose(satellites[:, 2], altitude, atol=1e-6)
        payload = dict(altitude_km=altitude, orbital_parameters=orbit,
                       time_seconds=0, satellite_count=len(satellites), satellites=satellites.tolist(),
                       source=str(source.relative_to(ROOT)),
                       model="sharc/satellite/ngso/orbit_model.py")
        (output / f"orbit_{altitude}km.json").write_text(json.dumps(payload), encoding="utf-8")
        print(altitude, len(satellites), p.inclination_deg)


if __name__ == "__main__":
    main()
