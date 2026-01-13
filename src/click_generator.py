"""
Click sound generator for BTCBeeper.

Generates Geiger counter-style click sounds with various characteristics
(frequency, duration, noise level, decay rate) for audio feedback.
"""

import numpy as np
from scipy.io import wavfile
import os
from typing import TypedDict

# Parameters for the Geiger counter click
SAMPLE_RATE = 44100  # Hz (standard audio sample rate)
RANDOM_SEED = 42  # For reproducible sound generation


class ClickParams(TypedDict):
    """Parameters for generating a click sound."""
    filename: str
    duration: float
    frequency: float
    sine_amp: float
    noise_amp: float
    decay: float
    double: bool

# List of click variations
click_variations: list[ClickParams] = [
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

def generate_click_sound(params: ClickParams, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a single click sound based on parameters.
    
    Args:
        params: Click sound parameters (frequency, duration, etc.)
        sample_rate: Audio sample rate in Hz
        
    Returns:
        NumPy array of int16 audio samples
    """
    # Generate time array
    t = np.linspace(0, params["duration"], int(sample_rate * params["duration"]), False)
    
    # Generate sine wave if frequency > 0
    if params["frequency"] > 0:
        sine_wave = params["sine_amp"] * np.sin(2 * np.pi * params["frequency"] * t)
    else:
        sine_wave = np.zeros_like(t)
    
    # Add noise
    noise = params["noise_amp"] * np.random.normal(0, 0.2, t.size)
    click = sine_wave + noise
    
    # Apply exponential decay envelope
    envelope = np.exp(-params["decay"] * t / params["duration"])
    click = click * envelope
    
    # Normalize to 90% of max amplitude
    max_amplitude = np.max(np.abs(click))
    if max_amplitude > 0:
        click = click / max_amplitude * 0.9
    
    # Convert to int16 (16-bit audio)
    click = (click * 32767).astype(np.int16)
    
    # Create double click if requested
    if params["double"]:
        silence_duration = 0.001  # 1ms gap
        silence = np.zeros(int(silence_duration * sample_rate), dtype=np.int16)
        click = np.concatenate([click, silence, click])
    
    return click


def main() -> None:
    """Generate all click sound variations and save to disk."""
    # Set random seed for reproducible sound generation
    np.random.seed(RANDOM_SEED)
    
    # Determine output directory
    project_root = Path(__file__).parent.parent
    sounds_dir = project_root / "data" / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate all click variations
    for params in click_variations:
        click = generate_click_sound(params)
        output_path = sounds_dir / params["filename"]
        wavfile.write(str(output_path), SAMPLE_RATE, click)
        print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()