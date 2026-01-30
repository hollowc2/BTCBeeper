"""Tests for click_generator.py sound synthesis module.

Covers:
- Sound generation with various parameters
- Boundary conditions (zero/extreme values)
- Output format validation
- Double-click functionality
- Normalization behavior
"""

import numpy as np
import pytest


class TestGenerateClickSound:
    """Test generate_click_sound function for audio synthesis."""

    def test_returns_numpy_array(self, click_params):
        """Verify function returns a numpy array."""
        from click_generator import generate_click_sound

        result = generate_click_sound(click_params)

        assert isinstance(result, np.ndarray)

    def test_returns_int16_dtype(self, click_params):
        """Verify output is int16 format for WAV compatibility."""
        from click_generator import generate_click_sound

        result = generate_click_sound(click_params)

        assert result.dtype == np.int16

    def test_correct_duration(self, click_params):
        """Verify output length matches specified duration."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        click_params["duration"] = 0.01  # 10ms
        result = generate_click_sound(click_params)

        expected_samples = int(SAMPLE_RATE * 0.01)
        assert len(result) == expected_samples

    def test_custom_sample_rate(self, click_params):
        """Verify custom sample rate affects output length."""
        from click_generator import generate_click_sound

        custom_rate = 22050
        click_params["duration"] = 0.01
        result = generate_click_sound(click_params, sample_rate=custom_rate)

        expected_samples = int(custom_rate * 0.01)
        assert len(result) == expected_samples

    def test_amplitude_normalized(self, click_params):
        """Verify output is normalized to 90% of max int16 range."""
        from click_generator import generate_click_sound

        result = generate_click_sound(click_params)
        max_amplitude = np.max(np.abs(result))

        # Should be normalized to 90% of 32767
        expected_max = int(0.9 * 32767)
        # Allow some tolerance for floating point
        assert max_amplitude <= expected_max + 1
        # Should be close to the target (not too quiet)
        assert max_amplitude >= expected_max * 0.8

    def test_zero_frequency_pure_noise(self):
        """Verify zero frequency produces pure noise signal."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 0,
            "sine_amp": 0.3,  # Should be ignored
            "noise_amp": 0.5,
            "decay": 10,
            "double": False
        }

        np.random.seed(42)  # For reproducibility
        result = generate_click_sound(params)

        # Should still produce output
        assert len(result) > 0
        # Check it's not all zeros
        assert np.any(result != 0)

    def test_zero_noise_pure_sine(self):
        """Verify zero noise produces pure sine wave."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.5,
            "noise_amp": 0.0,
            "decay": 10,
            "double": False
        }

        np.random.seed(42)
        result = generate_click_sound(params)

        assert len(result) > 0
        assert np.any(result != 0)

    def test_double_click_doubles_length(self, click_params):
        """Verify double=True approximately doubles the output length."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        click_params["double"] = False
        single = generate_click_sound(click_params)

        click_params["double"] = True
        double = generate_click_sound(click_params)

        # Double click = original + 1ms silence + original
        expected_double_len = len(single) * 2 + int(0.001 * SAMPLE_RATE)
        assert len(double) == expected_double_len

    def test_double_click_has_silence_gap(self, click_params):
        """Verify double click has silent gap in the middle."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        click_params["double"] = True
        click_params["duration"] = 0.005  # Longer for clearer separation

        np.random.seed(42)
        result = generate_click_sound(click_params)

        single_len = int(SAMPLE_RATE * click_params["duration"])
        silence_len = int(0.001 * SAMPLE_RATE)

        # Check the silence portion is all zeros
        silence_start = single_len
        silence_end = single_len + silence_len
        silence_portion = result[silence_start:silence_end]

        assert np.all(silence_portion == 0)

    def test_decay_affects_envelope(self):
        """Verify higher decay creates faster amplitude drop."""
        from click_generator import generate_click_sound

        base_params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.5,
            "noise_amp": 0.0,  # Pure sine for cleaner comparison
            "double": False
        }

        np.random.seed(42)
        low_decay = {**base_params, "decay": 5}
        high_decay = {**base_params, "decay": 20}

        result_low = generate_click_sound(low_decay)
        result_high = generate_click_sound(high_decay)

        # Compare energy in second half (after decay)
        mid = len(result_low) // 2
        energy_low = np.sum(np.abs(result_low[mid:]).astype(float))
        energy_high = np.sum(np.abs(result_high[mid:]).astype(float))

        # Higher decay should have less energy in second half
        assert energy_high < energy_low

    def test_very_short_duration(self):
        """Verify handling of very short duration."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.0001,  # 0.1ms - very short
            "frequency": 1000,
            "sine_amp": 0.3,
            "noise_amp": 0.2,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        # Should still produce some samples
        assert len(result) >= 1

    def test_very_long_duration(self):
        """Verify handling of longer duration."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        params = {
            "filename": "test.wav",
            "duration": 0.5,  # 500ms - relatively long
            "frequency": 1000,
            "sine_amp": 0.3,
            "noise_amp": 0.2,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        expected_len = int(SAMPLE_RATE * 0.5)
        assert len(result) == expected_len

    def test_high_frequency(self):
        """Verify handling of high frequency tones."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 20000,  # Near audible limit
            "sine_amp": 0.5,
            "noise_amp": 0.0,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        assert len(result) > 0
        assert np.any(result != 0)

    def test_low_frequency(self):
        """Verify handling of low frequency tones."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.05,  # Longer to capture full cycle
            "frequency": 50,  # Low frequency
            "sine_amp": 0.5,
            "noise_amp": 0.0,
            "decay": 2,  # Slow decay to see the wave
            "double": False
        }

        result = generate_click_sound(params)

        assert len(result) > 0
        assert np.any(result != 0)

    def test_extreme_amplitudes(self):
        """Verify handling of extreme amplitude values."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 10.0,  # Very high
            "noise_amp": 10.0,  # Very high
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        # Should be normalized
        assert np.max(np.abs(result)) <= 32767

    def test_zero_amplitudes(self):
        """Verify handling of zero amplitudes produces silence."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.0,
            "noise_amp": 0.0,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        # All zeros expected (silent)
        assert np.all(result == 0)

    def test_reproducibility_with_same_seed(self):
        """Verify same random seed produces identical output."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.3,
            "noise_amp": 0.3,  # Has random component
            "decay": 10,
            "double": False
        }

        np.random.seed(42)
        result1 = generate_click_sound(params)

        np.random.seed(42)
        result2 = generate_click_sound(params)

        np.testing.assert_array_equal(result1, result2)

    def test_different_seeds_different_output(self):
        """Verify different seeds produce different output (for noise component)."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.0,  # No sine to focus on noise
            "noise_amp": 0.5,
            "decay": 10,
            "double": False
        }

        np.random.seed(42)
        result1 = generate_click_sound(params)

        np.random.seed(123)
        result2 = generate_click_sound(params)

        # Should not be identical
        assert not np.array_equal(result1, result2)


class TestClickVariations:
    """Test the predefined CLICK_VARIATIONS configurations."""

    def test_all_variations_valid(self):
        """Verify all predefined variations produce valid output."""
        from click_generator import CLICK_VARIATIONS, generate_click_sound

        np.random.seed(42)
        for i, params in enumerate(CLICK_VARIATIONS):
            result = generate_click_sound(params)

            assert isinstance(result, np.ndarray), f"Variation {i} failed: not numpy array"
            assert result.dtype == np.int16, f"Variation {i} failed: wrong dtype"
            assert len(result) > 0, f"Variation {i} failed: empty output"

    def test_all_variations_have_required_keys(self):
        """Verify all variations have all required parameters."""
        from click_generator import CLICK_VARIATIONS

        required_keys = {"filename", "duration", "frequency", "sine_amp", "noise_amp", "decay", "double"}

        for i, params in enumerate(CLICK_VARIATIONS):
            assert set(params.keys()) == required_keys, f"Variation {i} missing keys"

    def test_variations_have_unique_filenames(self):
        """Verify all variations have unique filenames."""
        from click_generator import CLICK_VARIATIONS

        filenames = [p["filename"] for p in CLICK_VARIATIONS]
        assert len(filenames) == len(set(filenames))

    def test_variations_have_positive_durations(self):
        """Verify all durations are positive."""
        from click_generator import CLICK_VARIATIONS

        for params in CLICK_VARIATIONS:
            assert params["duration"] > 0

    def test_variations_have_valid_frequencies(self):
        """Verify all frequencies are non-negative."""
        from click_generator import CLICK_VARIATIONS

        for params in CLICK_VARIATIONS:
            assert params["frequency"] >= 0

    def test_variations_have_valid_amplitudes(self):
        """Verify all amplitudes are non-negative."""
        from click_generator import CLICK_VARIATIONS

        for params in CLICK_VARIATIONS:
            assert params["sine_amp"] >= 0
            assert params["noise_amp"] >= 0

    def test_variations_have_positive_decay(self):
        """Verify all decay values are positive."""
        from click_generator import CLICK_VARIATIONS

        for params in CLICK_VARIATIONS:
            assert params["decay"] > 0


class TestClickParamsTypedDict:
    """Test ClickParams TypedDict structure."""

    def test_typed_dict_keys(self):
        """Verify ClickParams has expected keys."""
        from click_generator import ClickParams

        # TypedDict defines __annotations__
        expected_keys = {"filename", "duration", "frequency", "sine_amp", "noise_amp", "decay", "double"}
        assert set(ClickParams.__annotations__.keys()) == expected_keys

    def test_typed_dict_types(self):
        """Verify ClickParams has correct type annotations."""
        from click_generator import ClickParams

        annotations = ClickParams.__annotations__
        assert annotations["filename"] == str
        assert annotations["duration"] == float
        assert annotations["frequency"] == float
        assert annotations["sine_amp"] == float
        assert annotations["noise_amp"] == float
        assert annotations["decay"] == float
        assert annotations["double"] == bool


class TestConstants:
    """Test module-level constants."""

    def test_sample_rate_standard(self):
        """Verify SAMPLE_RATE is a standard audio rate."""
        from click_generator import SAMPLE_RATE

        standard_rates = [8000, 11025, 16000, 22050, 44100, 48000, 96000]
        assert SAMPLE_RATE in standard_rates

    def test_random_seed_defined(self):
        """Verify RANDOM_SEED is defined for reproducibility."""
        from click_generator import RANDOM_SEED

        assert isinstance(RANDOM_SEED, int)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimum_viable_params(self):
        """Verify minimal valid parameters work."""
        from click_generator import generate_click_sound

        params = {
            "filename": "x",
            "duration": 0.001,
            "frequency": 100,
            "sine_amp": 0.1,
            "noise_amp": 0.1,
            "decay": 1,
            "double": False
        }

        result = generate_click_sound(params)
        assert len(result) > 0

    def test_extreme_decay_high(self):
        """Verify extreme high decay value works."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.5,
            "noise_amp": 0.2,
            "decay": 1000,  # Very high decay
            "double": False
        }

        result = generate_click_sound(params)
        assert len(result) > 0
        # Should be almost entirely decayed
        mid = len(result) // 2
        assert np.max(np.abs(result[mid:])) < np.max(np.abs(result[:mid // 2]))

    def test_extreme_decay_low(self):
        """Verify extreme low decay value works."""
        from click_generator import generate_click_sound

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.5,
            "noise_amp": 0.0,
            "decay": 0.1,  # Very low decay
            "double": False
        }

        result = generate_click_sound(params)
        assert len(result) > 0

    def test_single_sample_duration(self):
        """Verify minimum possible duration (single sample)."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        params = {
            "filename": "test.wav",
            "duration": 1 / SAMPLE_RATE,  # One sample
            "frequency": 1000,
            "sine_amp": 0.5,
            "noise_amp": 0.2,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)
        assert len(result) == 1


class TestIntegration:
    """Integration tests for the sound generation pipeline."""

    def test_generate_all_variations_sequentially(self):
        """Verify all variations can be generated in sequence."""
        from click_generator import CLICK_VARIATIONS, generate_click_sound

        np.random.seed(42)
        results = []

        for params in CLICK_VARIATIONS:
            result = generate_click_sound(params)
            results.append(result)

        assert len(results) == len(CLICK_VARIATIONS)
        assert all(len(r) > 0 for r in results)

    def test_output_suitable_for_wav(self):
        """Verify output format is suitable for WAV file writing."""
        from click_generator import generate_click_sound, SAMPLE_RATE

        params = {
            "filename": "test.wav",
            "duration": 0.01,
            "frequency": 1000,
            "sine_amp": 0.3,
            "noise_amp": 0.2,
            "decay": 10,
            "double": False
        }

        result = generate_click_sound(params)

        # WAV requirements:
        # - int16 dtype
        # - Values in range [-32768, 32767]
        assert result.dtype == np.int16
        assert np.all(result >= -32768)
        assert np.all(result <= 32767)
