"""
Mixeur audio : son du PC Linux (réseau) + son de ce PC (loopback)
-> envoyé sur l'appareil de sortie de votre choix.

Installation (Windows) :
    pip install soundcard numpy

Lancement :
    python mixer_pc1.py

IMPORTANT : pour éviter un écho/larsen, la source "son de ce PC" et la
"sortie" doivent être deux appareils DIFFÉRENTS.
Exemple : vos applications jouent sur "Haut-parleurs" (source loopback)
et le mix part sur "Casque Bluetooth" (sortie).
"""
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import soundcard as sc

RATE = 48000
CHANNELS = 2
BLOCK = 1024
MAX_BUFFER_FRAMES = RATE // 5  # 200 ms max, on jette l'excédent


class RingBuffer:
    """Tampon de trames float32 (N, 2) avec limite de latence."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = np.zeros((0, CHANNELS), dtype=np.float32)

    def push(self, frames):
        with self.lock:
            self.data = np.concatenate((self.data, frames))
            if len(self.data) > MAX_BUFFER_FRAMES:
                self.data = self.data[-MAX_BUFFER_FRAMES:]

    def pull(self, n):
        with self.lock:
            out = np.zeros((n, CHANNELS), dtype=np.float32)
            take = min(n, len(self.data))
            if take:
                out[:take] = self.data[:take]
                self.data = self.data[take:]
            return out

    def clear(self):
        with self.lock:
            self.data = np.zeros((0, CHANNELS), dtype=np.float32)


class Engine:
    def __init__(self):
        self.running = False
        self.net_buf = RingBuffer()
        self.loop_buf = RingBuffer()
        self.vol_net = 1.0
        self.vol_loop = 1.0
        self.net_active = False
        self.threads = []
        self.sock = None

    def start(self, port, loop_speaker, out_speaker):
        self.running = True
        self.net_buf.clear()
        self.loop_buf.clear()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.settimeout(0.5)

        self.threads = [
            threading.Thread(target=self._net_loop, daemon=True),
            threading.Thread(target=self._out_loop, args=(out_speaker,), daemon=True),
        ]
        if loop_speaker is not None:
            self.threads.append(
                threading.Thread(target=self._loopback_loop, args=(loop_speaker,), daemon=True)
            )
        for t in self.threads:
            t.start()

    def stop(self):
        self.running = False
        for t in self.threads:
            t.join(timeout=2)
        if self.sock:
            self.sock.close()
            self.sock = None
        self.threads = []
        self.net_active = False

    def _net_loop(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(65536)
            except socket.timeout:
                self.net_active = False
                continue
            except OSError:
                break
            self.net_active = True
            pcm = np.frombuffer(data[: len(data) // 4 * 4], dtype="<i2")
            frames = (pcm.astype(np.float32) / 32768.0).reshape(-1, CHANNELS)
            self.net_buf.push(frames)

    def _loopback_loop(self, speaker):
        try:
            mic = sc.get_microphone(speaker.id, include_loopback=True)
            with mic.recorder(samplerate=RATE, channels=CHANNELS, blocksize=BLOCK) as rec:
                while self.running:
                    block = rec.record(numframes=BLOCK)
                    self.loop_buf.push(block.astype(np.float32))
        except Exception as e:  # noqa: BLE001
            print("Erreur loopback :", e)

    def _out_loop(self, speaker):
        try:
            with speaker.player(samplerate=RATE, channels=CHANNELS, blocksize=BLOCK) as player:
                while self.running:
                    a = self.net_buf.pull(BLOCK) * self.vol_net
                    b = self.loop_buf.pull(BLOCK) * self.vol_loop
                    mix = np.clip(a + b, -1.0, 1.0)
                    player.play(mix)
        except Exception as e:  # noqa: BLE001
            print("Erreur sortie :", e)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mixeur audio PC1 + PC Linux")
        self.geometry("460x380")
        self.resizable(False, False)
        self.engine = Engine()

        self.speakers = sc.all_speakers()
        names = [s.name for s in self.speakers]

        pad = {"padx": 12, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=8)

        ttk.Label(frm, text="Port d'écoute (flux du PC Linux) :").grid(row=0, column=0, sticky="w", **pad)
        self.port_var = tk.StringVar(value="5004")
        ttk.Entry(frm, textvariable=self.port_var, width=8).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Son de CE PC (capturer la sortie de) :").grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        self.loop_var = tk.StringVar(value="(aucun)")
        self.loop_cb = ttk.Combobox(frm, textvariable=self.loop_var, values=["(aucun)"] + names,
                                    state="readonly", width=52)
        self.loop_cb.grid(row=2, column=0, columnspan=2, **pad)

        ttk.Label(frm, text="Envoyer le mix vers (sortie) :").grid(row=3, column=0, columnspan=2, sticky="w", **pad)
        default = sc.default_speaker().name
        self.out_var = tk.StringVar(value=default)
        self.out_cb = ttk.Combobox(frm, textvariable=self.out_var, values=names,
                                   state="readonly", width=52)
        self.out_cb.grid(row=4, column=0, columnspan=2, **pad)

        ttk.Label(frm, text="Volume PC Linux :").grid(row=5, column=0, sticky="w", **pad)
        self.s_net = ttk.Scale(frm, from_=0, to=2, value=1, command=self._vol)
        self.s_net.grid(row=5, column=1, sticky="ew", **pad)

        ttk.Label(frm, text="Volume ce PC :").grid(row=6, column=0, sticky="w", **pad)
        self.s_loop = ttk.Scale(frm, from_=0, to=2, value=1, command=self._vol)
        self.s_loop.grid(row=6, column=1, sticky="ew", **pad)

        self.btn = ttk.Button(frm, text="Démarrer", command=self.toggle)
        self.btn.grid(row=7, column=0, columnspan=2, pady=12)

        self.status = ttk.Label(frm, text="Arrêté")
        self.status.grid(row=8, column=0, columnspan=2)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(500, self.refresh_status)

    def _find(self, name):
        for s in self.speakers:
            if s.name == name:
                return s
        return None

    def _vol(self, _=None):
        self.engine.vol_net = float(self.s_net.get())
        self.engine.vol_loop = float(self.s_loop.get())

    def toggle(self):
        if self.engine.running:
            self.engine.stop()
            self.btn.config(text="Démarrer")
            self.status.config(text="Arrêté")
            return

        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Erreur", "Port invalide.")
            return

        out = self._find(self.out_var.get())
        loop = self._find(self.loop_var.get())
        if out is None:
            messagebox.showerror("Erreur", "Choisissez un appareil de sortie.")
            return
        if loop is not None and loop.id == out.id:
            if not messagebox.askyesno(
                "Attention",
                "La source 'ce PC' et la sortie sont identiques : cela créera un écho.\nContinuer quand même ?",
            ):
                return
        try:
            self._vol()
            self.engine.start(port, loop, out)
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le port {port} :\n{e}")
            return
        self.btn.config(text="Arrêter")

    def refresh_status(self):
        if self.engine.running:
            net = "reçu" if self.engine.net_active else "en attente du PC Linux…"
            self.status.config(text=f"En marche - flux Linux : {net}")
        self.after(500, self.refresh_status)

    def on_close(self):
        if self.engine.running:
            self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
