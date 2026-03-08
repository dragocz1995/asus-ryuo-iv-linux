# ASUS ROG RYUO IV LCD — Linux Driver

Sends live system sensor data (CPU/GPU temperature, usage, clock speed, memory) to the ASUS ROG RYUO IV AIO cooler's built-in LCD display on Linux.

Reverse-engineered from the Windows "ASUS Info Hub" Electron app and the Android HomeUI APK running on the LCD.

![ASUS ROG RYUO IV](https://rog.asus.com/cooler/all-in-one/rog-ryuo-iv/spec/)

## Features

- CPU temperature, usage, clock speed
- GPU temperature, usage, fan speed, power draw
- Memory usage
- Customizable background video (5 built-in presets)
- Automatic video looping
- Systemd service for autostart on boot

## Supported Hardware

- **AIO**: ASUS ROG RYUO IV (USB HID `0B05:1C76`)
- **Tested on**: Fedora 43, AMD Ryzen + AMD GPU (amdgpu driver)
- Should work on other Linux distros with minor adjustments to sensor paths

## Requirements

```bash
pip install hidapi
```

Or on Fedora:

```bash
sudo dnf install python3-hidapi
```

## Installation

1. Copy the script:

```bash
sudo cp ryuo-lcd.py /usr/local/bin/ryuo-lcd.py
sudo chmod +x /usr/local/bin/ryuo-lcd.py
```

2. Install the systemd service:

```bash
sudo cp ryuo-lcd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ryuo-lcd.service
```

3. Check status:

```bash
sudo systemctl status ryuo-lcd.service
sudo journalctl -u ryuo-lcd.service -f
```

## Configuration

### Change background video

Edit `/usr/local/bin/ryuo-lcd.py` and change the `media` field. Available preset videos:

| Video | Description |
|-------|-------------|
| `RYUO_IV_HW_Info_01.mp4` | Preset 1 |
| `RYUO_IV_HW_Info_02.mp4` | Preset 2 |
| `RYUO_IV_HW_Info_03.mp4` | Preset 3 |
| `RYUO_IV_HW_Info_04.mp4` | Preset 4 |
| `RYUO_IV_HW_Info_05.mp4` | Preset 5 |

Then restart the service:

```bash
sudo systemctl restart ryuo-lcd.service
```

### Change displayed sensors

Edit the `sysinfoDisplay` array. Available values:

- `CPU Temperature`, `GPU Temperature`
- `CPU Load`, `GPU Load`
- `CPU Speed Average`, `GPU Speed`
- `CPU Usage`, `GPU Usage`
- `CPU Voltage`
- `Date&Time`

### Sensor paths (adjust for your hardware)

- **CPU temp**: Uses `k10temp` driver (`temp3_input`) — AMD Ryzen
- **GPU temp**: Uses `amdgpu` driver (`temp1_input` = edge temperature)
- **GPU fan/power**: From `amdgpu` hwmon
- For Intel/NVIDIA, you'll need to adjust the sensor reading paths in `get_sensors()`

## How It Works

The RYUO IV LCD is an Android 13 device connected via USB HID. Communication uses a custom binary protocol:

1. **Framing**: `0x5A` start/end markers with escape sequences (`0x5B01` = `0x5A`, `0x5B02` = `0x5B`)
2. **Header**: HTTP-like text protocol with CRLF line endings (`POST {cmdType} 1\r\n`)
3. **Payload**: JSON sensor data or screen configuration
4. **Checksum**: Single byte (`sum & 0xFF`)

Two command types are used:
- `waterBlockScreenId` — sets the display layout, video background, and which sensors to show
- `all` — sends live sensor data updates (every ~1 second)

## Protocol Details

The LCD runs an Android app called "HomeUI" that receives data via a serial service. The protocol was reverse-engineered by decompiling both the Windows Electron app (`ASUS Info Hub`) and the Android APKs (`HomeUI.apk`, `SerialService.apk`).

Key findings:
- Request state must be exactly `POST` (not `POST1.0`)
- Line endings must be `\r\n` (CRLF), not `\n`
- HID reports are 1025 bytes (1 byte report ID `0x00` + 1024 bytes data)
- LCD has a 5-second disconnect timeout — if no data is received, it reverts to standby
- `playMode` supports `Single`, `Random`, and `Cycle` (not "loop")
- Preset videos are stored on the LCD at `/sdcard/pcMediaPreset/`

## License

MIT

## Credits

Reverse-engineered with the help of Claude (Anthropic).
