import numpy as np
from scipy.io import wavfile
import os

# Parameters for the Geiger counter click
sample_rate = 44100  # Hz (standard audio sample rate)

# List of click variations
click_variations = [
    {
        "filename": "geiger_click1.wav",
        "duration": 0.002,  # shorter, softer
        "frequency": 1000,
        "sine_amp": 0.2,
        "noise_amp": 0.3,
        "decay": 16,
        "double": False
    },
    {
        "filename": "geiger_click2.wav",
        "duration": 0.004,  # higher frequency
        "frequency": 3000,
        "sine_amp": 0.4,
        "noise_amp": 0.2,
        "decay": 12,
        "double": False
    },
    {
        "filename": "geiger_click3.wav",
        "duration": 0.003,  # pure noise
        "frequency": 0,
        "sine_amp": 0.0,
        "noise_amp": 0.5,
        "decay": 10,
        "double": False
    },
    {
        "filename": "geiger_click4.wav",
        "duration": 0.008,  # longer, damped
        "frequency": 1200,
        "sine_amp": 0.3,
        "noise_amp": 0.3,
        "decay": 6,
        "double": False
    },
    {
        "filename": "geiger_click5.wav",
        "duration": 0.002,  # double click
        "frequency": 1200,
        "sine_amp": 0.3,
        "noise_amp": 0.3,
        "decay": 12,
        "double": True
    },
    # New variations below
    {
        "filename": "geiger_click6.wav",
        "duration": 0.005,  # longer, low freq, soft
        "frequency": 700,
        "sine_amp": 0.15,
        "noise_amp": 0.2,
        "decay": 8,
        "double": False
    },
    {
        "filename": "geiger_click7.wav",
        "duration": 0.004,  # slightly longer for smoother attack
        "frequency": 4000,
        "sine_amp": 0.25,   # lower amplitude
        "noise_amp": 0.18,  # add a bit more noise
        "decay": 10,        # slower decay for less abruptness
        "double": False
    },
    {
        "filename": "geiger_click8.wav",
        "duration": 0.006,  # mid freq, more noise, slow decay
        "frequency": 1800,
        "sine_amp": 0.2,
        "noise_amp": 0.4,
        "decay": 4,
        "double": False
    },
    {
        "filename": "geiger_click9.wav",
        "duration": 0.002,  # very short, pure sine
        "frequency": 2500,
        "sine_amp": 0.6,
        "noise_amp": 0.0,
        "decay": 20,
        "double": False
    },
    {
        "filename": "geiger_click10.wav",
        "duration": 0.004,  # double, high freq, more noise
        "frequency": 3500,
        "sine_amp": 0.2,
        "noise_amp": 0.4,
        "decay": 10,
        "double": True
    },
]

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sounds_dir = os.path.join(project_root, "data", "sounds")
os.makedirs(sounds_dir, exist_ok=True)

for params in click_variations:
    t = np.linspace(0, params["duration"], int(sample_rate * params["duration"]), False)
    if params["frequency"] > 0:
        sine_wave = params["sine_amp"] * np.sin(2 * np.pi * params["frequency"] * t)
    else:
        sine_wave = 0
    noise = params["noise_amp"] * np.random.normal(0, 0.2, t.size)
    click = sine_wave + noise
    envelope = np.exp(-params["decay"] * t / params["duration"])
    click = click * envelope
    click = click / np.max(np.abs(click)) * 0.9
    click = (click * 32767).astype(np.int16)

    if params["double"]:
        silence = np.zeros(int(0.001 * sample_rate), dtype=np.int16)  # 1ms gap
        click = np.concatenate([click, silence, click])

    wavfile.write(os.path.join(sounds_dir, params["filename"]), sample_rate, click)