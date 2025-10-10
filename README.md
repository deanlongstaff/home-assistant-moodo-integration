<div align="center">

# Moodo Integration for Home Assistant

<img src="https://i.postimg.cc/Dy6KTTzc/deanlongstaff-home-assistant-moodo-integration.png" alt="Logo" width="560" />
<br><br>

[![HACS Custom][hacs_shield]][hacs]
[![GitHub Latest Release][releases_shield]][latest_release]
[![HA integration usage][ha_analytics_shield]][ha_analytics]
[![Buy Me A Coffee][buy_me_a_coffee_shield]][buy_me_a_coffee]

### Control your Moodo smart aroma diffusers with Home Assistant

A custom integration providing real-time control and monitoring of Moodo devices via WebSocket and REST API

</div>

---

## About Moodo

Moodo is a smart aroma diffuser that allows you to create custom scent combinations using up to 4 interchangeable fragrance capsules. With adjustable fan speeds and multiple modes, Moodo provides personalized aromatherapy for your home, controllable through various smart home platforms.

## Installation

You can install this integration via [HACS](#hacs) or [manually](#manual).

### HACS

1. Open HACS in your Home Assistant instance
2. Click on the three dots menu in the top right corner
3. Select **Custom repositories**
4. Add this repository URL: `https://github.com/deanlongstaff/home-assistant-moodo-integration`
5. Select category: **Integration**
6. Click **Add**
7. Close the custom repositories dialog
8. Search for "Moodo" in HACS
9. Click **Download**
10. Restart Home Assistant

Configure the integration via the integrations page or press the blue button below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=moodo)

### Manual

Copy the `custom_components/moodo` to your custom_components folder and reboot Home Assistant. Configure the Moodo integration either via the integrations page or press the blue button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=moodo)

---

## Features

This integration provides comprehensive control over your Moodo devices through multiple Home Assistant platforms:

### Fan Control

- **Power On/Off**: Turn your Moodo device on or off
- **Fan Speed Control**: Adjust fan intensity from 1-100%

### Mode Selection

- **Diffuser Mode**: Standard aromatherapy diffusion
- **Purifier Mode**: Air purification functionality (requires Moodo AIR capsules and compatible device)

### Advanced Settings

- **Shuffle Mode**: Automatically rotate between different scent presets
- **Interval Mode**: Schedule timed diffusion intervals with work/sleep cycles
- **Interval Types**: Choose from three interval patterns:
  - **Powerful** (10 min on / 5 min off) - Maximum fragrance intensity
  - **Efficient** (10 min on / 10 min off) - Balanced performance and capsule longevity
  - **Saver** (5 min on / 10 min off) - Extended capsule life with gentle diffusion

### Individual Slot Control

- **Four Scent Slots**: Control each of the 4 fragrance capsule slots independently
- **Per-Slot Intensity**: Adjust the intensity (0-100%) for each slot
- **Custom Blending**: Create unlimited scent combinations by mixing slots at different levels

### Sensors

- **Device Status**: Monitor online/offline status
- **Capsule Levels**: Monitor remaining capsule life
- **Battery Level**: Track battery percentage

## Configuration

Enter your Moodo account credentials when prompted:

- **Email**: Your Moodo account email
- **Password**: Your Moodo account password

The integration will automatically discover all Moodo devices associated with your account.

## Entities Created

For each Moodo device, the following entities are created:

### Fan Entity

- `fan.<device_name>` - Main device control with speed adjustment

### Switch Entities

- `switch.<device_name>_shuffle` - Enable/disable shuffle mode
- `switch.<device_name>_interval` - Enable/disable interval mode

### Select Entities

- `select.<device_name>_mode` - Choose between diffuser and purifier modes
- `select.<device_name>_preset` - Select a preset scent profile. Available options depend on the inserted capsules
- `select.<device_name>_interval_type` - Select interval timing pattern (when interval mode is enabled)

### Number Entities

- `number.<device_name>_capsule_1_intensity` - Capsule 1 intensity control (0-100%)
- `number.<device_name>_capsule_2_intensity` - Capsule 2 intensity control (0-100%)
- `number.<device_name>_capsule_3_intensity` - Capsule 3 intensity control (0-100%)
- `number.<device_name>_capsule_4_intensity` - Capsule 4 intensity control (0-100%)

### Sensor Entities

- `sensor.<device_name>_battery` - Battery level percentage
- `sensor.<device_name>_charging_status` - Battery charging status
- `sensor.<device_name>_adapter_status` - The power adapter status
- `sensor.<device_name>__active_preset` - The active scent preset
- `sensor.<device_name>_capsule_1_type` - The type of the capsule inserted in slot 1
- `sensor.<device_name>_capsule_2_type` - The type of the capsule inserted in slot 2
- `sensor.<device_name>_capsule_3_type` - The type of the capsule inserted in slot 3
- `sensor.<device_name>_capsule_4_type` - The type of the capsule inserted in slot 4
- `sensor.<device_name>_capsule_1_remaining` - The remaining life of the capsule in slot 1
- `sensor.<device_name>_capsule_2_remaining` - The remaining life of the capsule in slot 2
- `sensor.<device_name>_capsule_3_remaining` - The remaining life of the capsule in slot 3
- `sensor.<device_name>_capsule_4_remaining` - The remaining life of the capsule in slot 4

## Troubleshooting

### Device shows as unavailable

- Check that your Moodo device is powered on and connected to Wi-Fi
- Verify your Moodo account credentials are correct
- Restart the integration from the Integrations page

### Changes not syncing

- Try restarting your Moodo device
- Try reloading the integration

Unfortunately the Moodo API isn't the most performant, so you may encounter some delays if performing too many actions at once.

### Authentication errors

- Ensure your Moodo account credentials are up to date

### Capsules shown in wrong order

If the capsule slots appear in a different order than expected, this is due to Moodo's device orientation design. You can change which side of your device is considered the "front" in the official Moodo mobile app:

1. Open the Moodo mobile app
2. Select the **Profile** tab (far right)
3. Tap on **My devices**
4. Tap on your Moodo device's name
5. Tap on either arrow near the device image to rotate the orientation
6. Return to the main page

The capsule order in Home Assistant will match the orientation set in the Moodo app.

## Development

### Running Tests

This integration includes comprehensive unit tests. To run them:

1. **Install test dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements_test.txt
   ```

2. **Run all tests:**

   ```bash
   pytest tests/
   ```

3. **Run specific test file:**

   ```bash
   pytest tests/test_switch.py
   ```

4. **Run with verbose output:**

   ```bash
   pytest tests/ -v
   ```

5. **Run with coverage report:**
   ```bash
   pytest tests/ --cov=custom_components.moodo --cov-report=term-missing
   ```

### Test Coverage

The test suite covers:

- Integration setup and configuration
- API client functionality
- Data coordinator updates and WebSocket handling
- Switch platform (shuffle and interval modes)
- Sensor platform (device status, battery, capsules)
- Fan platform (power and speed control)
- Select platform (mode, preset, interval type)
- Number platform (capsule intensity control)
- Error handling and edge cases

## Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/deanlongstaff/home-assistant-moodo-integration/issues).

## Credits

Developed by [@deanlongstaff](https://github.com/deanlongstaff)

## License

This is a custom integration provided free for use with Home Assistant and Moodo devices. This project is not affiliated with, endorsed by, or connected to Moodoin any way. All product names, logos, and brands are property of their respective owners.

---

[hacs_shield]: https://img.shields.io/static/v1.svg?label=HACS&message=Custom&style=popout&color=orange&labelColor=41bdf5&logo=HomeAssistantCommunityStore&logoColor=white
[hacs]: https://hacs.xyz/docs/faq/custom_repositories
[latest_release]: https://github.com/deanlongstaff/home-assistant-moodo-integration/releases/latest
[releases_shield]: https://img.shields.io/github/release/deanlongstaff/home-assistant-moodo-integration.svg?style=popout
[ha_analytics_shield]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.moodo.total
[ha_analytics]: https://analytics.home-assistant.io
[buy_me_a_coffee_shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=popout&logo=buy-me-a-coffee&logoColor=black
[buy_me_a_coffee]: https://buymeacoffee.com/deanlongstaff
