import numpy as np

R = 6371*1000
h = ((690 + 690)*1000)/ 2
minimun_service_angle_deg = 32

elevation_rad = np.radians(minimum_service_angle_deg)

# 1. Calcula o seno do ângulo de Nadir (alpha) usando a Lei dos Senos
sin_alpha = (R / (R + h)) * np.cos(elevation_rad)

# 2. Encontra o ângulo de Nadir em radianos
alpha_rad = np.arcsin(sin_alpha)

# 3. Calcula o ângulo central da Terra (theta ou gamma)
# pi/2 radianos = 90 graus
theta_service_raw = (np.pi / 2.0) - elevation_rad - alpha_rad

print(theta_service_raw)