from src.sim.systems.clock import clock_system
from src.sim.systems.movement import movement_system
from src.sim.systems.sensors import sensor_system
from src.sim.systems.steering import steering_system

# Run order per step. See docs/decisions/005-entity-component-system.md.
SIMULATION_SYSTEMS = (
    steering_system,
    movement_system,
    sensor_system,
    clock_system,
)

__all__ = [
    "SIMULATION_SYSTEMS",
    "clock_system",
    "movement_system",
    "sensor_system",
    "steering_system",
]
