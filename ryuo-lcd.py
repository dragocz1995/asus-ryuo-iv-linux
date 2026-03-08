#!/usr/bin/env python3
"""ASUS ROG RYUO IV LCD - Send sensor data via USB HID (hidapi)"""
import json, time, struct, os, sys
import hid

VID = 0x0B05
PID = 0x1C76

def get_sensors():
    cpu_temp = gpu_temp = 0.0
    gpu_fan = gpu_power = gpu_usage = cpu_usage = freq = 0

    for hwmon in os.listdir('/sys/class/hwmon/'):
        path = f'/sys/class/hwmon/{hwmon}'
        try: name = open(f'{path}/name').read().strip()
        except: continue
        if name == 'k10temp':
            try: cpu_temp = int(open(f'{path}/temp3_input').read().strip()) / 1000
            except: pass
        if name == 'amdgpu' and os.path.exists(f'{path}/fan1_input'):
            try: gpu_temp = int(open(f'{path}/temp1_input').read().strip()) / 1000
            except: pass
            try: gpu_fan = int(open(f'{path}/fan1_input').read().strip())
            except: pass
            try: gpu_power = int(float(open(f'{path}/power1_average').read().strip()) / 1e6)
            except: pass

    with open('/proc/stat') as f: l1 = f.readline().split()
    time.sleep(0.05)
    with open('/proc/stat') as f: l2 = f.readline().split()
    d_idle = int(l2[4]) - int(l1[4])
    d_tot = sum(int(l2[i])-int(l1[i]) for i in range(1,len(l1)))
    cpu_usage = int(100 * (1 - d_idle / max(1, d_tot)))
    try: freq = int(open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq').read()) // 1000
    except: pass
    try: gpu_usage = int(open('/sys/class/drm/card1/device/gpu_busy_percent').read())
    except: pass

    with open('/proc/meminfo') as f:
        mi = {}
        for line in f:
            p = line.split(':')
            mi[p[0].strip()] = int(p[1].strip().split()[0])
    total_mem = mi['MemTotal'] * 1024
    used_mem = (mi['MemTotal'] - mi['MemAvailable']) * 1024

    return {
        "cpu": {"temperature": cpu_temp, "usage": cpu_usage, "load": cpu_usage,
                "power": 0, "voltage": 0.0, "speedAverage": freq, "fanAverage": 0},
        "gpu": {"temperature": str(gpu_temp), "usage": gpu_usage, "load": gpu_usage,
                "fan": gpu_fan, "power": gpu_power, "speed": 0, "voltage": 0.0},
        "memory": {"total": total_mem, "used": used_mem,
                   "load": int(used_mem*100/max(1,total_mem)), "speed": 7600, "temperature": 0.0},
        "motherboard": {"temperature": 0.0},
        "network": {"download": 0, "upload": 0},
        "disk": {"total": 0, "used": 0, "load": 0, "activity": 0,
                 "readSpeed": 0, "writeSpeed": 0, "temperature": 0},
        "fans": [],
        "timeZone": "Europe/Prague",
        "timestamp": int(time.time() * 1000)
    }

def checksum(data):
    return sum(data) & 0xFF

def escape_bytes(data):
    r = bytearray()
    for b in data:
        if b == 0x5A: r.extend(b'\x5B\x01')
        elif b == 0x5B: r.extend(b'\x5B\x02')
        else: r.append(b)
    return bytes(r)

def build_packet(content_json, msg_id, cmd_type="all"):
    # First line: {requestState} {cmdType} {version}
    # requestState must equal "POST" exactly (not "POST1.0")
    # cmdType must be "all" for sensor data, "waterBlockScreenId" for config
    # IMPORTANT: LCD uses \r\n (CRLF) line endings, not \n!
    CR = "\r\n"
    header_str = f"POST {cmd_type} 1{CR}"
    header_str += f"ContentType=json{CR}"
    header_str += f"ContentLength={len(content_json)}{CR}"
    header_str += f"AckNumber={msg_id}{CR}"
    header_str += f"Counter=0{CR}"
    header_str += f"Date=0{CR}"
    header_str += f"FileName=0{CR}"
    header_str += f"FileSize=0{CR}"
    header_str += f"SeqNumber=0{CR}"
    header_str += f"msgId=0{CR}"
    header_str += f"ContentRange=0{CR}"
    header_str += f"{CR}"
    header_str += content_json

    content = header_str.encode('utf-8')
    raw = struct.pack('>H', len(content) + 5) + content
    raw += struct.pack('B', checksum(raw))
    return b'\x5A' + escape_bytes(raw) + b'\x5A'

def send_packet(dev, packet):
    """Send a framed packet as HID report (report ID 0x00 + 1024 bytes)"""
    report = bytes([0x00]) + packet + b'\x00' * (1024 - len(packet))
    dev.write(report[:1025])

def send_screen_config(dev, msg_id):
    """Send ScreenConfig to tell LCD which theme/layout to display"""
    config = {
        "id": "Customization",
        "screenMode": "Full Screen",
        "ratio": "2:1",
        "media": ["RYUO_IV_HW_Info_04.mp4"],
        "playMode": "Cycle",
        "settings": {
            "titleColor": "#E5252B",
            "contentColor": "#FFFFFF",
            "filter": {"value": None, "opacity": 100},
            "badges": []
        },
        "sysinfoDisplay": [
            "CPU Temperature", "GPU Temperature",
            "CPU Speed Average", "GPU Speed",
            "CPU Load", "GPU Load"
        ]
    }
    content = json.dumps(config, separators=(',', ':'))
    packet = build_packet(content, msg_id, cmd_type="waterBlockScreenId")
    send_packet(dev, packet)
    print(f"Sent ScreenConfig: {config['id']}")

def main():
    print("Opening RYUO IV HID device...")
    dev = hid.device()
    dev.open(VID, PID)
    dev.set_nonblocking(1)
    print(f"Connected: {dev.get_manufacturer_string()} {dev.get_product_string()}")

    msg_id = 0
    config_sent = False

    # Send screen config FIRST before any sensor data
    send_screen_config(dev, msg_id)
    msg_id += 1
    time.sleep(2)

    while True:
        try:
            sensors = get_sensors()
            content = json.dumps(sensors, separators=(',', ':'))
            packet = build_packet(content, msg_id, cmd_type="all")
            send_packet(dev, packet)
            msg_id += 1

            # Resend config every 60 packets to handle app restarts
            if msg_id % 60 == 0:
                time.sleep(1)
                send_screen_config(dev, msg_id)
                msg_id += 1

            if msg_id % 10 == 0:
                print(f"Sent {msg_id} updates | CPU: {sensors['cpu']['temperature']}°C {sensors['cpu']['usage']}% | GPU: {sensors['gpu']['temperature']}°C {sensors['gpu']['usage']}%")
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(3)

    dev.close()
    print("Done.")

if __name__ == '__main__':
    main()
