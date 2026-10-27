"""Pure 3D camera geometry used by the software-rendered lottery scene."""
import math


def rotate_point(x, y, z, angle):
    x, z = x * math.cos(angle) + z * math.sin(angle), -x * math.sin(angle) + z * math.cos(angle)
    tilt = 0.25
    return x, y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)


def project_point(x, y, z, center=(170, 160), scale=106, camera=4.0):
    if camera + z <= 0:
        raise ValueError('Point is behind the camera.')
    perspective = camera / (camera + z)
    return center[0] + scale * x * perspective, center[1] + scale * y * perspective, perspective


def advance_particle(position, velocity, radius=0.86):
    x, y, z = position
    vx, vy, vz = velocity
    vx, vy, vz = vx - 0.0014 * z, vy + 0.0003, vz + 0.0014 * x
    speed = math.sqrt(vx * vx + vy * vy + vz * vz)
    if speed > 0.043:
        vx, vy, vz = (v * 0.043 / speed for v in (vx, vy, vz))
    x, y, z = x + vx, y + vy, z + vz
    distance = math.sqrt(x * x + y * y + z * z)
    if distance > radius:
        nx, ny, nz = x / distance, y / distance, z / distance
        dot = vx * nx + vy * ny + vz * nz
        if dot > 0:
            vx, vy, vz = vx - 2 * dot * nx, vy - 2 * dot * ny, vz - 2 * dot * nz
        x, y, z = nx * radius, ny * radius, nz * radius
    return (x, y, z), (vx, vy, vz)
