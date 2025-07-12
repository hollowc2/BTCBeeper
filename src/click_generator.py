import numpy as np
from scipy.io import wavfile
import os

# Parameters for the Geiger counter click
sample_rate = 44100  # Hz (standard audio sample rate)
duration = 0.004  # seconds (very short for a sharp click)
frequency = 1200  # Hz (tone for the click's character)

# Generate time array
t = np.linspace(0, duration, int(sample_rate * duration), False)

# Create a click: combine a sine wave with noise for texture
sine_wave = 0.4 * np.sin(2 * np.pi * frequency * t)  # Subtle tonal component
noise = 0.6 * np.random.normal(0, 0.2, t.size)  # Noise for realism
click = sine_wave + noise

# Apply an exponential decay envelope for sharpness
envelope = np.exp(-12 * t / duration)
click = click * envelope

# Normalize to avoid clipping
click = click / np.max(np.abs(click)) * 0.9

# Convert to 16-bit PCM format
click = (click * 32767).astype(np.int16)

# Save to WAV file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sounds_dir = os.path.join(project_root, "data", "sounds")
os.makedirs(sounds_dir, exist_ok=True)
wavfile.write(os.path.join(sounds_dir, "geiger_click.wav"), sample_rate, click)