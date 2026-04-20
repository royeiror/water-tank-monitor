"""Constants for Water Tank Monitor."""

DOMAIN = "water_tank_monitor"

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

# Services
SERVICE_CALIBRATE_FULL = "calibrate_full"
SERVICE_CALIBRATE_EMPTY = "calibrate_empty"
SERVICE_SET_VOLUME = "set_volume"
SERVICE_RESET_CALIBRATION_BOUNDS = "reset_calibration_bounds"

# Service Fields
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_VOLUME = "volume"

# Signal names
SIGNAL_RESET_BOUNDS = "water_tank_monitor_reset_bounds"
SIGNAL_CALIBRATION_UPDATE = "water_tank_monitor_calibration_update"

# Analytics Defaults
DEFAULT_DETECTION_THRESHOLD = 20.0  # L/h
DEFAULT_MIN_SUPPLY_LITERS = 10.0   # Min liters to count as a "Supply Event"
DEFAULT_ROLLING_DAYS = 7           # Days for consumption averaging

# Event Categories
EVENT_TYPE_SUPPLY = "supply"
EVENT_TYPE_DRAIN = "drain"

DRAIN_CAT_FLUSH = "toilet_flush"
DRAIN_CAT_SHOWER = "shower"
DRAIN_CAT_LAUNDRY = "laundry"
DRAIN_CAT_OTHER = "other"

# Storage Keys (in config entry)
CONF_SUPPLY_HISTORY = "supply_history"
CONF_CONSUMPTION_HISTORY = "consumption_history"
CONF_DETECTION_THRESHOLD = "detection_threshold"
