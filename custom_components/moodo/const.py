"""Constants for the Moodo integration."""

DOMAIN = "moodo"

# REST API Configuration
API_BASE_URL = "https://rest.moodo.co/api"
API_TIMEOUT = 10

# Update intervals
UPDATE_INTERVAL = 30  # seconds

# Config flow
CONF_TOKEN = "token"

# Device status
BOX_STATUS_OFF = 0
BOX_STATUS_ON = 1

# Box modes
BOX_MODE_DIFFUSER = "diffuser"
BOX_MODE_PURIFIER = "purifier"

# Slot IDs
SLOT_IDS = [0, 1, 2, 3]

# Platforms
PLATFORMS = ["fan", "switch", "select", "number", "sensor"]
