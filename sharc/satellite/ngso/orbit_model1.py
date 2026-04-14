"""Implements a Space Station Orbit model as described in Rec. ITU-R S.1325-3
"""

import numpy as np


from sharc.satellite.ngso.custom_functions import wrap2pi, eccentric_anomaly, keplerian2eci, eci2ecef
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM, KEPLER_CONST, EARTH_ROTATION_RATE


class OrbitModel():
    """Orbit Model for satellite positions."""

    def __init__(self,
                 Nsp: int,
                 Np: int,
                 phasing: float,
                 long_asc: float,
                 omega: float,
                 delta: float,
                 hp: float,
                 ha: float,
                 Mo: float,
                 *,
                 model_time_as_random_variable: bool,
                 t_min: float,
                 t_max: float | None
             ):
        """Instantiates and OrbitModel object from the Orbit parameters as specified in S.1529.

        Parameters
        ----------
        Nsp : int
            number of satellites in the orbital plane (A.4.b.4.b)
        Np : int
            number of orbital planes (A.4.b.2)
        phasing : float
            satellite phasing between planes, in degrees
        long_asc : float
            initial longitude of ascending node of the first plane, in degrees
        omega : float
            argument of perigee, in degrees
        delta : float
            orbital plane inclination, in degrees
        perigee_alt_km : float
            altitude of perigee in km
        ha : float
            altitude of apogee in km
        Mo : float
            initial mean anomaly for first satellite of first plane, in degrees
        model_time_as_random_variable: bool
            whether get_orbit_positions_random will use only time as random variable
        t_min: float
            if model_time_as_random_variable == True,
            defines the lower bound of the time distribution
        t_max: float
            if model_time_as_random_variable == True,
            defines the upper bound of the time distribution
        """
        self.Nsp = Nsp
        self.Np = Np
        self.phasing = phasing
        self.long_asc = long_asc
        self.omega_0 = omega
        self.omega = omega
        self.delta = delta
        self.perigee_alt_km = hp
        self.apogee_alt_km = ha
        self.Mo = Mo

        # Derive other orbit parameters
        self.semi_major_axis = (
            hp + ha + 2 * EARTH_RADIUS_KM) / 2  # semi-major axis, in km
        self.eccentricity = (ha + EARTH_RADIUS_KM - self.semi_major_axis) / \
            self.semi_major_axis  # orbital eccentricity (e)
        # TODO: consider J2 perturbations for mean motion and orbital period
        self.mean_motion = np.sqrt(KEPLER_CONST / self.semi_major_axis ** 3)
        # orbital period, in seconds
        self.orbital_period_sec = 2 * np.pi / self.mean_motion
        # satellite separation angle in the plane (degrees)
        self.sat_sep_angle_deg = 360 / self.Nsp
        # angle between plane intersections with the equatorial plane (degrees)
        self.orbital_plane_spacing = 360 / self.Np

        # Initial mean anomalies for all the satellites
        initial_mean_anomalies_deg = (
            Mo + np.arange(Nsp) * self.sat_sep_angle_deg + np.arange(
                self.Np)[
                :,
                np.newaxis] * self.phasing) % 360
        self.initial_mean_anomalies_rad = np.radians(
            initial_mean_anomalies_deg.flatten())

        # Initial longitudes of ascending node for all the planes
        inital_raan = (self.long_asc * np.ones(self.Nsp) + np.arange(self.Np)
                       [:, np.newaxis] * self.orbital_plane_spacing) % 360
        self.inital_raan_rad = np.radians(inital_raan.flatten())

        self.model_time_as_random_variable = model_time_as_random_variable
        self.t_min = t_min

        if t_max is not None:
            self.t_max = t_max
        else:
            # sane default
            self.t_max = t_min + self.orbital_period_sec * 1e3
            # TODO: implement 1503 secular drift to enable correct higher time ceiling
            # self.t_max = t_min + 365 * 24 * 60 * 60
            # self.t_max = sys.float_info.max

        # Calculated variables
        self.mean_anomaly = None  # computed mean anomalies
        self.raan_rad = None  # computed longitudes of the ascending node
        self.eccentric_anomaly = None  # computed eccentric anomalies
        self.true_anomaly = None  # computed true anomalies
        self.distance = None  # computed distance to Earth's center
        # computed true anomaly relative to the line of nodes
        self.true_anomaly_rel_line_nodes = None

    def get_satellite_positions_time_interval(
            self,
            initial_time_secs=0,
            interval_secs=5,
            n_periods=4) -> dict:
        """
        Return the orbit positions vector.

        Parameters
        ----------
        initial_time_secs : int, optional
            initial time instant in seconds, by default 0
        interval_secs : int, optional
            time interval between points, by default 5
        n_periods : int, optional
            number of orbital peridos, by default 4

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, sx, sy, sz
        """
        t = np.arange(
            initial_time_secs,
            n_periods *
            self.orbital_period_sec +
            interval_secs,
            interval_secs)
        return self.get_orbit_positions_time_instant(t)

    def get_orbit_positions_time_instant(self, time_instant_secs=0) -> dict:
        """Returns the Satellite positins for a given time vector within the orbit period.

        Parameters
        ----------
        time_instant_secs: np.array
            time instants inside the orbit period in seconds

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, alt, sx, sy, sz
        """
        t = np.atleast_1d(time_instant_secs)

        assert t.ndim == 1, "Input must be scalar or 1D array"

        # TODO: add J2 perturbations based on 1503
        # Mean anomaly (M)
        self.mean_anomaly = (
            self.initial_mean_anomalies_rad[:, None] + self.mean_motion * t
        ) % (2 * np.pi)

        # TODO: add J2 perturbations based on 1503
        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        self.raan_rad = self.inital_raan_rad[:, None]

        # TODO: add J2 perturbations based on 1503
        # perigee argument
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        # The time to be used for calculation of Earth's rotation angle
        earth_rotated_t = t

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def get_orbit_positions_random(
            self,
            rng: np.random.RandomState,
            n_samples=1) -> dict:
        """Returns satellite positions in a random time instant in seconds.
                Parameters
                ----------
                rng : np.random.RandomState
                    Random number generator for reproducibility
                n_samples : int
                    Number of random samples to generate, by default 1
                Returns
                -------
                dict
                    A dictionary with satellite positions in spherical and ecef coordinates.
                        lat, lon, sx, sy, sz
        """
        if self.model_time_as_random_variable:
            return self.get_orbit_positions_time_instant(
                self.t_min + (self.t_max - self.t_min) * rng.random_sample(n_samples)
            )
        # Mean anomaly (M)
        self.mean_anomaly = (self.initial_mean_anomalies_rad[:, None] +
                             2 * np.pi * rng.random_sample(n_samples)) % (2 * np.pi)

        # just selecting a random earth rotation for later coordinate transformation
        earth_rotated_t = 2 * np.pi * rng.random_sample(n_samples) / EARTH_ROTATION_RATE

        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        # FIXME: previous implementation, due to unexpected behavior, did not
        # use the drawn random samples. Choose whether to maintain behavior
        # self.raan_rad = (self.inital_raan_rad[:, None] +
        #             2 * np.pi * rng.random_sample(n_samples))
        self.raan_rad = self.inital_raan_rad[:, None]

        # perigee argument
        # NOTE: using fixed perigee argument for circular orbits always make sense
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def __get_satellite_positions_from_angles(
        self,
        mean_anomaly: np.ndarray,
        raan_rad: np.ndarray,
        omega_rad: np.array,
        earth_rotated_t: np.ndarray,
    ):
        """
        mean_anomaly:
            Mean anomaly (M)
        raan_rad: np.ndarray
            Longitudes of the ascending node (OmegaG)
        omega_rad: np.ndarray
            Perigee argument
            NOTE: doesn't matter for circular orbits
        earth_rotated_t:
            The time to be used for calculation of Earth's rotation angle
        """
        assert (raan_rad.shape == (self.Np * self.Nsp, len(earth_rotated_t))) or (
            raan_rad.shape == (self.Np * self.Nsp, 1)
        )

        # Eccentric anomaly (E)
        self.eccentric_anom = eccentric_anomaly(
            self.eccentricity, mean_anomaly)

        # True anomaly (v)
        self.true_anomaly = 2 * np.arctan(np.sqrt((1 + self.eccentricity) / (
            1 - self.eccentricity)) * np.tan(self.eccentric_anom / 2))

        self.true_anomaly = np.mod(self.true_anomaly, 2 * np.pi)

        # Distance of the satellite to Earth's center (r)
        r = self.semi_major_axis * \
            (1 - self.eccentricity ** 2) / (1 + self.eccentricity * np.cos(self.true_anomaly))

        # True anomaly relative to the line of nodes (gamma)
        self.true_anomaly_rel_line_nodes = wrap2pi(
            self.true_anomaly +
            omega_rad)  # gamma in the interval [-pi, pi]

        # Latitudes of the satellites, in radians (theta)
        # theta = np.arcsin(np.sin(gamma) * np.sin(np.radians(self.delta)))

        # Longitude variation due to angular displacement, in radians (phiS)
        # phiS = np.arccos(np.cos(gamma) / np.cos(theta)) * np.sign(gamma)

        raan_rad = wrap2pi(raan_rad)

        # POSITION CALCULATION IN ECEF COORDINATES - ITU-R S.1503
        r_eci = keplerian2eci(self.semi_major_axis,
                              self.eccentricity,
                              self.delta,
                              np.degrees(raan_rad),
                              np.degrees(omega_rad),
                              np.degrees(self.true_anomaly))

        r_ecef = eci2ecef(earth_rotated_t, r_eci)
        sx, sy, sz = r_ecef[0], r_ecef[1], r_ecef[2]
        lat = np.degrees(np.arcsin(sz / r))
        lon = np.degrees(np.arctan2(sy, sx))
        # (lat, lon, _) = ecef2lla(sx, sy, sz)

        pos_vector = {
            'lat': lat,
            'lon': lon,
            'alt': r - EARTH_RADIUS_KM,
            'sx': sx,
            'sy': sy,
            'sz': sz
        }
        return pos_vector


def main():
    """Main function to test the OrbitModel class and plot ground tracks.

    This function creates an instance of the OrbitModel class with specified parameters,
    retrieves satellite positions over a specified time interval, and plots the ground tracks
    of the satellites using Plotly.
    """
    import plotly.graph_objects as go

    orbit_params = {
        "Nsp": 1,
        "Np": 28,
        "phasing": 1.5,
        "long_asc": 0,
        "omega": 0,
        "delta": 53,
        "hp": 525,
        "ha": 525,
        "Mo": 0,
        "model_time_as_random_variable": False,
        "t_min": 0.0,
        "t_max": None
    }

    print("Orbit parameters:")
    print(orbit_params)
    param_file = (
        r"C:\GitHub\SHARC\sharc\campaigns\01_DC_MSS_to_EESS\input\VicB_BO_SA_PB50_MB0_A40_LF20.yaml"
    )
    from sharc.parameters.parameters import Parameters
    parameters = Parameters()
    parameters.set_file_name(param_file)
    parameters.read_params()

    # Instantiate the OrbitModel
    # orbit_model = OrbitModel(**orbit_params)
    orbit_model_params = parameters.mss_d2d.orbits[0]
    orbit_model = OrbitModel(
        Nsp=orbit_model_params.sats_per_plane,  # Satellites per plane
        Np=orbit_model_params.n_planes,  # Number of orbital planes
        phasing=orbit_model_params.phasing_deg,  # Phasing angle in degrees
        long_asc=orbit_model_params.long_asc_deg,  # Longitude of ascending node in degrees
        omega=orbit_model_params.omega_deg,  # Argument of perigee in degrees
        delta=orbit_model_params.inclination_deg,  # Orbital inclination in degrees
        hp=orbit_model_params.perigee_alt_km,  # Perigee altitude in kilometers
        ha=orbit_model_params.apogee_alt_km,  # Apogee altitude in kilometers
        Mo=orbit_model_params.initial_mean_anomaly,  # Initial mean anomaly in degrees
        # whether to use only time as random variable
        model_time_as_random_variable=orbit_model_params.model_time_as_random_variable,
        t_min=orbit_model_params.t_min,
        t_max=orbit_model_params.t_max,
    )

    # Get satellite positions over time
    positions = orbit_model.get_satellite_positions_time_interval(n_periods=1)

    # Extract latitude and longitude
    latitudes = positions['lat']
    longitudes = positions['lon']

    # Create a plotly figure
    # fig = go.Figure()

    # # Add traces for each satellite
    # for i in range(latitudes.shape[0]):
    #     # for i in range(10, 20):
    #     fig.add_trace(go.Scattergeo(
    #         lon=longitudes[i],
    #         lat=latitudes[i],
    #         mode='lines',
    #         name=f'Satellite {i + 1}'
    #     ))

    # # Update layout for better visualization
    # fig.update_layout(
    #     title="Satellite Ground Tracks",
    #     showlegend=False,
    #     geo=dict(
    #         projection_type="equirectangular",
    #         showland=True,
    #         landcolor="rgb(243, 243, 243)",
    #         countrycolor="rgb(204, 204, 204)"
    #     )
    # )

    # # Show the plot
    # fig.show()


    # # Adiciona os rastros (linhas) e a posição atual (pontos) para cada satélite
    # for i in range(latitudes.shape[0]):
    #     # Desenha a linha da órbita
    #     fig.add_trace(go.Scattergeo(
    #         lon=longitudes[i],
    #         lat=latitudes[i],
    #         mode='lines',
    #         line=dict(width=1),
    #         name=f'Órbita {i + 1}',
    #         showlegend=False
    #     ))
        
    #     # Desenha o Satélite (um ponto na posição inicial t=0)
    #     fig.add_trace(go.Scattergeo(
    #         lon=[longitudes[i][0]],
    #         lat=[latitudes[i][0]],
    #         mode='markers',
    #         marker=dict(size=6, color='red', symbol='circle'),
    #         name=f'Satélite {i + 1}',
    #         showlegend=False
    #     ))

    # # Transforma em um Globo 3D focado no Brasil
    # fig.update_layout(
    #     title="Constelação DC-MSS (Visão 3D - Brasil)",
    #     geo=dict(
    #         projection_type="orthographic", # Isso transforma no globo 3D!
    #         center=dict(lat=-15.7801, lon=-47.9292), # Centralizado em Brasília
    #         projection_scale=2.5, # Dá um zoom para focar no país
    #         showland=True,
    #         landcolor="rgb(212, 212, 212)",
    #         showcountries=True,
    #         countrycolor="rgb(50, 50, 50)",
    #         showocean=True,
    #         oceancolor="rgb(200, 230, 255)"
    #     ),
    #     margin=dict(l=0, r=0, t=40, b=0)
    # )

    # # Show the plot
    # fig.show()

    # 1. Pegar a posição de TODOS os satélites no instante inicial (t=0)
    # latitudes e longitudes são matrizes, pegamos apenas a primeira coluna [:, 0]
    lats_t0 = latitudes[:, 0]
    lons_t0 = longitudes[:, 0]

    # 2. Coordenadas da Earth Station (Brasília)
    es_lat = -15.7801
    es_lon = -47.9292

    # 3. Encontrar qual é o satélite que está mais perto de Brasília no t=0
    # (Usamos a distância euclidiana simples apenas para achar o índice)
    dist = np.sqrt((lats_t0 - es_lat)**2 + (lons_t0 - es_lon)**2)
    idx_closest = np.argmin(dist)
    sat_lat = lats_t0[idx_closest]
    sat_lon = lons_t0[idx_closest]

    fig = go.Figure()

    # 4. Adicionar as Órbitas (linhas finas de fundo para dar contexto)
    for i in range(latitudes.shape[0]):
        fig.add_trace(go.Scattergeo(
            lon=longitudes[i],
            lat=latitudes[i],
            mode='lines',
            line=dict(width=0.5, color='gray'),
            opacity=0.3,
            showlegend=False,
            hoverinfo='skip'
        ))

    # 5. Adicionar a "Nuvem" com todos os satélites (Triângulos roxos)
    fig.add_trace(go.Scattergeo(
        lon=lons_t0,
        lat=lats_t0,
        mode='markers',
        marker=dict(size=5, color='#9467bd', symbol='triangle-up'),
        name='Constelação DC-MSS'
    ))

    # 6. Adicionar a Earth Station (Bolinha Azul)
    fig.add_trace(go.Scattergeo(
        lon=[es_lon],
        lat=[es_lat],
        mode='markers',
        marker=dict(size=8, color='#1f77b4', symbol='circle'),
        name='Earth Station (Brasília)'
    ))

    # 7 e 8. Desenhar FOOTPRINTS vazados apenas para os satélites visíveis na região
    angles = np.linspace(0, 2*np.pi, 100)
    raio_footprint = 18 # Raio de cobertura em graus
    raio_de_visao_do_grafico = 35 # Filtro: Só desenha se estiver perto da América do Sul

    foi_pra_legenda_link = False
    foi_pra_legenda_footprint = False

    for idx in range(len(lats_t0)):
        s_lat = lats_t0[idx]
        s_lon = lons_t0[idx]
        
        # Distância do satélite para Brasília
        dist_graus = np.sqrt((s_lat - es_lat)**2 + (s_lon - es_lon)**2)
        
        # Só desenha os footprints que estão na face da Terra que estamos olhando
        if dist_graus <= raio_de_visao_do_grafico:
            
            # 1. Desenha a borda do Footprint (Sem preenchimento bugado)
            fp_lats = s_lat + raio_footprint * np.sin(angles)
            fp_lons = s_lon + raio_footprint * np.cos(angles)
            
            fig.add_trace(go.Scattergeo(
                lon=fp_lons,
                lat=fp_lats,
                mode='lines',
                line=dict(width=1.5, color='orange'), # Apenas a linha externa!
                name='Footprint DC-MSS',
                showlegend=not foi_pra_legenda_footprint
            ))
            foi_pra_legenda_footprint = True

            # 2. Se o satélite estiver cobrindo Brasília exatamente, traça o Link
            if dist_graus <= raio_footprint:
                fig.add_trace(go.Scattergeo(
                    lon=[es_lon, s_lon],
                    lat=[es_lat, s_lat],
                    mode='lines',
                    line=dict(width=2, color='red', dash='dot'),
                    name='Link Ativo (Visada)',
                    showlegend=not foi_pra_legenda_link
                ))
                foi_pra_legenda_link = True
                
    # 9. Configurar o layout: O MAPA MUNDI 3D Lindo!
    # 9. Configurar o layout: MODO ESPAÇO (Dark/Tech Theme)
    fig.update_layout(
        title="Modelo de Coexistência DC-MSS e Estação Terrena",
        paper_bgcolor="black", # Pinta o fundo do navegador de preto (O Espaço!)
        plot_bgcolor="black",
        font=dict(color="white"), # Deixa as letras brancas para dar leitura
        showlegend=True,
        legend=dict(
            yanchor="top", y=0.9, xanchor="left", x=0.05, 
            bgcolor="rgba(20, 20, 20, 0.8)", # Fundo da legenda semi-transparente escuro
            bordercolor="gray", borderwidth=1
        ),
        geo=dict(
            bgcolor="black", # Fundo do ambiente 3D
            projection_type="orthographic",
            center=dict(lat=es_lat, lon=es_lon),
            projection_scale=1.5,
            showland=True,
            landcolor="#2d4a34", # Verde escuro lembrando relevo/topografia
            showocean=True,
            oceancolor="#051021", # Azul marinho abissal
            showcountries=True,
            countrycolor="#555555", # Fronteiras mais discretas
            showcoastlines=True,
            coastlinecolor="#777777",
            resolution=50
        ),
        margin=dict(l=0, r=0, t=50, b=0) # Margem superior levemente maior para o título não colar
    )

    fig.show()


if __name__ == "__main__":
    main()
