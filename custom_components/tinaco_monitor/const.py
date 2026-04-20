"""Constants for Tinaco Monitor."""

DOMAIN = "tinaco_monitor"

# Config entry keys
CONF_DISTANCE_SENSOR = "distance_sensor"
CONF_MIN_DISTANCE = "min_distance"
CONF_MAX_DISTANCE = "max_distance"
CONF_TANK_CAPACITY = "tank_capacity"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_CRITICAL_THRESHOLD = "critical_threshold"

# Defaults
DEFAULT_MIN_DISTANCE = 0.10      # meters — distance when tank is FULL
DEFAULT_MAX_DISTANCE = 1.20      # meters — distance when tank is EMPTY
DEFAULT_TANK_CAPACITY = 700.0    # liters
DEFAULT_LOW_THRESHOLD = 20       # percent
DEFAULT_CRITICAL_THRESHOLD = 10  # percent
FULL_THRESHOLD = 95.0            # percent — considered "full"

# Fill rate calculation
FILL_RATE_WINDOW = 10  # number of readings to keep for derivative
