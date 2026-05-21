"""Backend wrapper for the satellite map simulation."""

from sharc.satellite.ngso.backend.orbit_backend_service import (
    FOOTPRINT_MODES,
    PROFILES,
    OrbitSimulationBackend,
    SimulationProfile,
    build_simulation,
    default_param_file,
)

__all__ = [
    "PROFILES",
    "FOOTPRINT_MODES",
    "OrbitSimulationBackend",
    "SimulationProfile",
    "build_simulation",
    "default_param_file",
]

r'''
Legacy implementation kept below only as historical reference.

import imageio.v2 as imageio
import numpy as np
import pyvista as pv
from PIL import Image
from shapely.geometry import Point

from sharc.satellite.ngso.constants import (EARTH_RADIUS_KM,
                                            EARTH_ROTATION_RATE, KEPLER_CONST)
from sharc.satellite.ngso.custom_functions import (eccentric_anomaly, eci2ecef,
                                                   keplerian2eci, wrap2pi)


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

    param_file = (
        r"C:\GitHub\SHARC\sharc\campaigns\01_DC_MSS_to_EESS\Script\Base.yaml"
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

    topology_params = parameters.imt.topology
    bs_lat_deg = topology_params.central_latitude
    bs_lon_deg = topology_params.central_longitude
    bs_alt_m  = topology_params.central_altitude  # provavelmente em metros
    bs_alt_km = bs_alt_m / 1000.0
    
    # ================================
    # CONFIGURAÇÃO
    # ================================
    EARTH_RADIUS_KM = 6371
    RELIEF_SCALE_KM = 6   # 6 km = realista (Everest ~8.8 km)

    # ================================
    # CRIAR ESFERA BASE
    # ================================
    earth = pv.Sphere(
        radius=EARTH_RADIUS_KM,
        theta_resolution=800,
        phi_resolution=800
    )

    points = earth.points.copy()
    x, y, z = points[:,0], points[:,1], points[:,2]

    # ================================
    # CARREGAR HEIGHTMAP
    # ================================
    heightmap = np.array(Image.open("earth_heightmap.jpg").convert("L"))

    if len(heightmap.shape) == 3:
        heightmap = heightmap[:,:,0]

    heightmap = heightmap.astype(float)
    heightmap -= heightmap.min()
    heightmap /= heightmap.max()

    img_h, img_w = heightmap.shape

    # ================================
    # CONVERTER CADA VÉRTICE EM LAT/LON
    # ================================
    lon = (np.arctan2(y, x) + np.pi) / (2*np.pi)
    lat = (np.arcsin(z / EARTH_RADIUS_KM) + np.pi/2) / np.pi

    u = (lon * img_w).astype(int) % img_w
    v = ((1 - lat) * img_h).astype(int) % img_h

    elevation = heightmap[v, u]

    # ================================
    # APLICAR RELEVO REAL
    # ================================
    normals = points / np.linalg.norm(points, axis=1)[:,None]
    displacement = elevation * RELIEF_SCALE_KM

    earth.points = points + normals * displacement[:,None]

    # ================================
    # TEXTURA BLUE MARBLE
    # ================================
    texture = pv.read_texture("blue_marble.jpg")

    earth.active_texture_coordinates = np.column_stack((lon, lat))

    # ================================
    # RENDERIZAÇÃO
    # ================================
    plotter = pv.Plotter()

    plotter.add_mesh(
        earth,
        texture=texture,
        smooth_shading=True,
        ambient=0.2,
        diffuse=0.9,
        specular=0.2,
        specular_power=20
    )

    plotter.enable_eye_dome_lighting()

    plotter.set_background("black")

    light = pv.Light(
        position=(100000, 100000, 100000),
        focal_point=(0,0,0),
        color="white",
        intensity=1.2
    )
    plotter.add_light(light)

   # ================================
    # INICIALIZAÇÃO FIXA (Apenas a estação no chão não se move)
    # ================================
    lat_rad = np.radians(bs_lat_deg)
    lon_rad = np.radians(bs_lon_deg)
    r = EARTH_RADIUS_KM + bs_alt_km
    bs_x = r * np.cos(lat_rad) * np.cos(lon_rad)
    bs_y = r * np.cos(lat_rad) * np.sin(lon_rad)
    bs_z = r * np.sin(lat_rad)

    bs_point = pv.PolyData([[bs_x, bs_y, bs_z]])
    plotter.add_mesh(bs_point, color="#1f77b4", point_size=15, render_points_as_spheres=True)

    # ===============================
    # PARÂMETROS DE VISUALIZAÇÃO
    # ===============================
    MODO_VISUALIZACAO = "SERVICE_GRID"
    BEAMWIDTH_DEG = 87.44  
    NUM_PONTOS_FOOTPRINT = 60

    # --- INICIALIZAÇÃO DO SERVICE GRID (Mosaico Hexagonal) ---
    if MODO_VISUALIZACAO == "SERVICE_GRID":
        grid_cells_polys = []
        grid_centers = []
        grid_lonlat = [] 
        
        HEX_SIZE = 0.216 
        lat_min, lat_max = -60, 15
        lon_min, lon_max = -85, -30
        
        dy = HEX_SIZE * 1.5
        dx = HEX_SIZE * np.sqrt(3)

        y_steps = int((lat_max - lat_min) / dy)
        x_steps = int((lon_max - lon_min) / dx)

        for row in range(y_steps):
            for col in range(x_steps):
                lat_c = lat_min + row * dy
                lon_c = lon_min + col * dx
                
                if row % 2 == 1:
                    lon_c += dx / 2.0
                    
                hex_pts = []
                for i in range(6):
                    angle_deg = 60 * i
                    angle_rad = np.radians(angle_deg)
                    v_lat = lat_c + HEX_SIZE * np.sin(angle_rad)
                    v_lon = lon_c + HEX_SIZE * np.cos(angle_rad)
                    
                    v_lat_rad, v_lon_rad = np.radians(v_lat), np.radians(v_lon)
                    px = (EARTH_RADIUS_KM + 10) * np.cos(v_lat_rad) * np.cos(v_lon_rad)
                    py = (EARTH_RADIUS_KM + 10) * np.cos(v_lat_rad) * np.sin(v_lon_rad)
                    pz = (EARTH_RADIUS_KM + 10) * np.sin(v_lat_rad)
                    hex_pts.append([px, py, pz])
                
                grid_cells_polys.append(hex_pts)
                
                lat_c_rad, lon_c_rad = np.radians(lat_c), np.radians(lon_c)
                cx = (EARTH_RADIUS_KM + 10) * np.cos(lat_c_rad) * np.cos(lon_c_rad)
                cy = (EARTH_RADIUS_KM + 10) * np.cos(lat_c_rad) * np.sin(lon_c_rad)
                cz = (EARTH_RADIUS_KM + 10) * np.sin(lat_c_rad)
                grid_centers.append([cx, cy, cz])
                grid_lonlat.append((lon_c, lat_c))

        grid_centers = np.array(grid_centers)
        grid_ativos = np.zeros(len(grid_centers), dtype=bool)

        print("Calculando zonas de back-off de fronteira (50km)... Isso pode levar alguns segundos.")
        import geopandas as gpd
        
        url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
        world = gpd.read_file(url)
        paises_simulacao = ['Brazil', 'Argentina', 'Uruguay', 'Paraguay', 'Bolivia', 'Chile', 'Peru']
        paises_gdf = world[world['NAME'].isin(paises_simulacao)]
        
        paises_metric = paises_gdf.to_crs(epsg=3857)
        fronteiras_metric = paises_metric.geometry.boundary
        zona_50km_metric = fronteiras_metric.buffer(50000).union_all()
        
        pontos_geom = [Point(lon, lat) for lon, lat in grid_lonlat]
        pontos_gdf = gpd.GeoDataFrame(geometry=pontos_geom, crs="EPSG:4326")
        pontos_metric = pontos_gdf.to_crs(epsg=3857)
        
        grid_is_border = pontos_metric.geometry.intersects(zona_50km_metric).values
        print("Cálculo de fronteiras concluído!")

    # ==========================================
    # CONFIGURAR A CÂMERA PARA A AMÉRICA DO SUL
    # ==========================================
    lat_cam, lon_cam = np.radians(-20), np.radians(-60)
    distancia_cam = EARTH_RADIUS_KM * 3.5 
    
    cam_x = distancia_cam * np.cos(lat_cam) * np.cos(lon_cam)
    cam_y = distancia_cam * np.cos(lat_cam) * np.sin(lon_cam)
    cam_z = distancia_cam * np.sin(lat_cam)

    plotter.camera.position = (cam_x, cam_y, cam_z)
    plotter.camera.focal_point = (0, 0, 0)
    plotter.camera.up = (0, 0, 1) 

    # ==========================================
    # PREPARAR A GRAVAÇÃO DO VÍDEO
    # ==========================================
    plotter.show(auto_close=False, interactive_update=True)
    
    caminho_video = r"C:\GitHub\SHARC\sharc\campaigns\01_DC_MSS_to_EESS\Videos\simulacao_dinamica.mp4"
    plotter.open_movie(caminho_video, framerate=24)

    num_frames = positions["sx"].shape[1]
    print(f"Iniciando gravação de {num_frames} frames...")

    # Variáveis para apagar os desenhos a cada frame
    ator_grid_normal = None
    ator_grid_borda = None
    ator_satelites_base = None
    atores_sat_selecao = []
    atores_linhas = []

    # ==========================================
    # LOOP NO TEMPO (A Mágica do Vídeo)
    # ==========================================
    for t in range(num_frames):
        # A) Limpar os desenhos dinâmicos do frame anterior
        if ator_grid_normal:
            plotter.remove_actor(ator_grid_normal)
            ator_grid_normal = None
        if ator_grid_borda:
            plotter.remove_actor(ator_grid_borda)
            ator_grid_borda = None
        if ator_satelites_base:
            plotter.remove_actor(ator_satelites_base)
            ator_satelites_base = None
            
        for ator in atores_sat_selecao:
            plotter.remove_actor(ator)
        atores_sat_selecao.clear()
        
        for ator in atores_linhas:
            plotter.remove_actor(ator)
        atores_linhas.clear()

        # B) Pegar as posições dinâmicas do instante 't'
        sx_t = positions["sx"][:, t]
        sy_t = positions["sy"][:, t]
        sz_t = positions["sz"][:, t]

        # C) Desenhar as bolinhas roxas dos satélites (Agora se movendo!)
        sat_points = np.column_stack((sx_t, sy_t, sz_t))
        sat_poly = pv.PolyData(sat_points)
        ator_satelites_base = plotter.add_mesh(sat_poly, color="#a282c0", point_size=8, render_points_as_spheres=True)

        grid_ativos = np.zeros(len(grid_centers), dtype=bool)
        satelites_ativos_coords = []

        # D) Calcular coberturas e desenhar as linhas de visada da estação terrestre
        bs = np.array([bs_x, bs_y, bs_z])
        
        for i in range(len(sx_t)):
            pos_sat = np.array([sx_t[i], sy_t[i], sz_t[i]])
            distancia_sat = np.linalg.norm(pos_sat)
            sat_ativo = False
            
            # --- Linha vermelha para a estação (agora dinâmica) ---
            dist_to_bs = np.linalg.norm(pos_sat - bs)
            if dist_to_bs < 3000:
                line = pv.Line(bs, pos_sat)
                ator_l = plotter.add_mesh(line, color="red", line_width=3)
                atores_linhas.append(ator_l)
            
            # --- Lógica da Área de Serviço ---
            nadir_x, nadir_y, nadir_z = pos_sat[0], pos_sat[1], pos_sat[2]
            lon_nadir_deg = np.degrees(np.arctan2(nadir_y, nadir_x))
            lat_nadir_deg = np.degrees(np.arcsin(nadir_z / distancia_sat))
            
            if not (-85 <= lon_nadir_deg <= -20 and -60 <= lat_nadir_deg <= 20):
                continue
                
            max_angulo_feixe = np.degrees(np.arcsin(EARTH_RADIUS_KM / distancia_sat))
            angulo_feixe_atual = BEAMWIDTH_DEG / 2
            
            if angulo_feixe_atual < max_angulo_feixe:
                gama = np.arcsin((distancia_sat / EARTH_RADIUS_KM) * np.sin(np.radians(angulo_feixe_atual)))
                angulo_central = gama - np.radians(angulo_feixe_atual)
                pos_nadir_terra = (pos_sat / distancia_sat) * EARTH_RADIUS_KM
                
                nadir_norm = pos_nadir_terra / np.linalg.norm(pos_nadir_terra)
                
                for g_idx, pt in enumerate(grid_centers):
                    pt_norm = pt / np.linalg.norm(pt)
                    cos_theta = np.clip(np.dot(nadir_norm, pt_norm), -1.0, 1.0)
                    theta = np.arccos(cos_theta)
                    
                    if theta <= angulo_central:
                        grid_ativos[g_idx] = True
                        sat_ativo = True
                        
            if sat_ativo:
                satelites_ativos_coords.append(pos_sat)

        # E) Construir e desenhar o Service Grid
        pts_ativos_normal, faces_ativos_normal = [], []
        pts_ativos_borda, faces_ativos_borda = [], []
        offset_an, offset_ab = 0, 0
        
        for idx, hex_pts in enumerate(grid_cells_polys):
            if grid_ativos[idx]:
                if grid_is_border[idx]:
                    pts_ativos_borda.extend(hex_pts)
                    faces_ativos_borda.extend([6, offset_ab, offset_ab+1, offset_ab+2, offset_ab+3, offset_ab+4, offset_ab+5])
                    offset_ab += 6
                else:
                    pts_ativos_normal.extend(hex_pts)
                    faces_ativos_normal.extend([6, offset_an, offset_an+1, offset_an+2, offset_an+3, offset_an+4, offset_an+5])
                    offset_an += 6

        if len(pts_ativos_normal) > 0:
            mesh_an = pv.PolyData(np.array(pts_ativos_normal), np.array(faces_ativos_normal))
            ator_grid_normal = plotter.add_mesh(mesh_an, color="#FF9900", opacity=0.6, show_edges=True, edge_color="black", line_width=2)
            
        if len(pts_ativos_borda) > 0:
            mesh_ab = pv.PolyData(np.array(pts_ativos_borda), np.array(faces_ativos_borda))
            ator_grid_borda = plotter.add_mesh(mesh_ab, color="#FFFFFF", opacity=0.8, show_edges=True, edge_color="black", line_width=2)

        # F) Desenhar as caixas de seleção nos satélites trabalhando
        for pos in satelites_ativos_coords:
            plano = pv.Plane(center=pos, direction=pos, i_size=800, j_size=800, i_resolution=1, j_resolution=1)
            quadrado_vazado = plano.extract_feature_edges()
            ator_sq = plotter.add_mesh(quadrado_vazado, color="#00FF00", line_width=4, render_lines_as_tubes=True)
            atores_sat_selecao.append(ator_sq)

        # G) Gravar o frame atual
        plotter.write_frame()
        print(f"Frame {t+1}/{num_frames} renderizado.")

    # ==========================================
    # FINALIZAR
    # ==========================================
    plotter.close()
    print("Vídeo salvo com sucesso na pasta de output!")

if __name__ == "__main__":
    main()
'''
