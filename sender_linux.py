#!/usr/bin/env python3
"""
Envoie le son du PC Linux vers le PC 1 via UDP.

Prérequis : pulseaudio-utils (la commande `parec`), présent par défaut avec
PulseAudio et PipeWire.  Installation si besoin :
    sudo apt install pulseaudio-utils

Usage :
    python3 sender_linux.py IP_DU_PC1 [port] [peripherique_monitor]

Exemples :
    python3 sender_linux.py 192.168.1.20
    python3 sender_linux.py 192.168.1.20 5004
    python3 sender_linux.py 192.168.1.20 5004 alsa_output.pci-0000_00_1f.3.analog-stereo.monitor

Pour lister les sources disponibles :  pactl list short sources
"""
import socket
import subprocess
import sys

CHUNK = 1920  # 10 ms de son (48 kHz, stéréo, 16 bits)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ip = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5004
    device = sys.argv[3] if len(sys.argv) > 3 else "@DEFAULT_MONITOR@"

    cmd = [
        "parec", "-d", device,
        "--format=s16le", "--rate=48000", "--channels=2",
        "--latency-msec=20",
    ]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    print(f"Envoi du son vers {ip}:{port}  (source : {device})")
    print("Ctrl+C pour arrêter.")
    try:
        while True:
            data = proc.stdout.read(CHUNK)
            if not data:
                break
            sock.sendto(data, (ip, port))
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        sock.close()


if __name__ == "__main__":
    main()
