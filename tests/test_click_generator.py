import numpy as np
import pytest


class TestGenerateClickSound:
    def test_returns_numpy_array(self, click_params):
        from click_generator import generate_click_sound
        result = generate_click_sound(click_params)
        assert isinstance(result, np.ndarray)

    def test_returns_int16_dtype(self, click_params):
        from click_generator import generate_click_sound
        result = generate_click_sound(click_params)
        assert result.dtype == np.int16

    def test_correct_duration(self, click_params):
        from click_generator import generate_click_sound, SAMPLE_RATE
        click_params["duration"] = 0.01
        result = generate_click_sound(click_params)
        assert len(result) == int(SAMPLE_RATE * 0.01)

    def test_custom_sample_rate(self, click_params):
        from click_generator import generate_click_sound
        custom_rate = 22050
        click_params["duration"] = 0.01
        result = generate_click_sound(click_params, sample_rate=custom_rate)
        assert len(result) == int(custom_rate * 0.01)

    def test_amplitude_normalized(self, click_params):
        from click_generator import generate_click_sound
        result = generate_click_sound(click_params)
        max_amplitude = np.max(np.abs(result))
        expected_max = int(0.9 * 32767)
        assert max_amplitude <= expected_max + 1
        assert max_amplitude >= expected_max * 0.8

    def test_zero_frequency_pure_noise(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 0,
            "sine_amp": 0.3, "noise_amp": 0.5, "decay": 10, "double": False
        }
        np.random.seed(42)
        result = generate_click_sound(params)
        assert len(result) > 0
        assert np.any(result != 0)

    def test_zero_noise_pure_sine(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.5, "noise_amp": 0.0, "decay": 10, "double": False
        }
        np.random.seed(42)
        result = generate_click_sound(params)
        assert len(result) > 0
        assert np.any(result != 0)

    def test_double_click_doubles_length(self, click_params):
        from click_generator import generate_click_sound, SAMPLE_RATE
        click_params["double"] = False
        single = generate_click_sound(click_params)
        click_params["double"] = True
        double = generate_click_sound(click_params)
        expected_double_len = len(single) * 2 + int(0.001 * SAMPLE_RATE)
        assert len(double) == expected_double_len

    def test_double_click_has_silence_gap(self, click_params):
        from click_generator import generate_click_sound, SAMPLE_RATE
        click_params["double"] = True
        click_params["duration"] = 0.005
        np.random.seed(42)
        result = generate_click_sound(click_params)
        single_len = int(SAMPLE_RATE * click_params["duration"])
        silence_len = int(0.001 * SAMPLE_RATE)
        silence_portion = result[single_len:single_len + silence_len]
        assert np.all(silence_portion == 0)

    def test_decay_affects_envelope(self):
        from click_generator import generate_click_sound
        base_params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.5, "noise_amp": 0.0, "double": False
        }
        np.random.seed(42)
        result_low = generate_click_sound({**base_params, "decay": 5})
        result_high = generate_click_sound({**base_params, "decay": 20})
        mid = len(result_low) // 2
        energy_low = np.sum(np.abs(result_low[mid:]).astype(float))
        energy_high = np.sum(np.abs(result_high[mid:]).astype(float))
        assert energy_high < energy_low

    def test_very_short_duration(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.0001, "frequency": 1000,
            "sine_amp": 0.3, "noise_amp": 0.2, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) >= 1

    def test_very_long_duration(self):
        from click_generator import generate_click_sound, SAMPLE_RATE
        params = {
            "filename": "test.wav", "duration": 0.5, "frequency": 1000,
            "sine_amp": 0.3, "noise_amp": 0.2, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) == int(SAMPLE_RATE * 0.5)

    def test_high_frequency(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 20000,
            "sine_amp": 0.5, "noise_amp": 0.0, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) > 0
        assert np.any(result != 0)

    def test_low_frequency(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.05, "frequency": 50,
            "sine_amp": 0.5, "noise_amp": 0.0, "decay": 2, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) > 0
        assert np.any(result != 0)

    def test_extreme_amplitudes(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 10.0, "noise_amp": 10.0, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert np.max(np.abs(result)) <= 32767

    def test_zero_amplitudes(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.0, "noise_amp": 0.0, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert np.all(result == 0)

    def test_reproducibility_with_same_seed(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.3, "noise_amp": 0.3, "decay": 10, "double": False
        }
        np.random.seed(42)
        result1 = generate_click_sound(params)
        np.random.seed(42)
        result2 = generate_click_sound(params)
        np.testing.assert_array_equal(result1, result2)

    def test_different_seeds_different_output(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.0, "noise_amp": 0.5, "decay": 10, "double": False
        }
        np.random.seed(42)
        result1 = generate_click_sound(params)
        np.random.seed(123)
        result2 = generate_click_sound(params)
        assert not np.array_equal(result1, result2)


class TestClickVariations:
    def test_all_variations_valid(self):
        from click_generator import CLICK_VARIATIONS, generate_click_sound
        np.random.seed(42)
        for i, params in enumerate(CLICK_VARIATIONS):
            result = generate_click_sound(params)
            assert isinstance(result, np.ndarray), f"Variation {i} failed"
            assert result.dtype == np.int16, f"Variation {i} failed"
            assert len(result) > 0, f"Variation {i} failed"

    def test_all_variations_have_required_keys(self):
        from click_generator import CLICK_VARIATIONS
        required_keys = {"filename", "duration", "frequency", "sine_amp", "noise_amp", "decay", "double"}
        for i, params in enumerate(CLICK_VARIATIONS):
            assert set(params.keys()) == required_keys, f"Variation {i} missing keys"

    def test_variations_have_unique_filenames(self):
        from click_generator import CLICK_VARIATIONS
        filenames = [p["filename"] for p in CLICK_VARIATIONS]
        assert len(filenames) == len(set(filenames))

    def test_variations_have_positive_durations(self):
        from click_generator import CLICK_VARIATIONS
        for params in CLICK_VARIATIONS:
            assert params["duration"] > 0

    def test_variations_have_valid_frequencies(self):
        from click_generator import CLICK_VARIATIONS
        for params in CLICK_VARIATIONS:
            assert params["frequency"] >= 0

    def test_variations_have_valid_amplitudes(self):
        from click_generator import CLICK_VARIATIONS
        for params in CLICK_VARIATIONS:
            assert params["sine_amp"] >= 0
            assert params["noise_amp"] >= 0

    def test_variations_have_positive_decay(self):
        from click_generator import CLICK_VARIATIONS
        for params in CLICK_VARIATIONS:
            assert params["decay"] > 0


class TestConstants:
    def test_sample_rate_standard(self):
        from click_generator import SAMPLE_RATE
        standard_rates = [8000, 11025, 16000, 22050, 44100, 48000, 96000]
        assert SAMPLE_RATE in standard_rates

    def test_random_seed_defined(self):
        from click_generator import RANDOM_SEED
        assert isinstance(RANDOM_SEED, int)


class TestEdgeCases:
    def test_minimum_viable_params(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "x", "duration": 0.001, "frequency": 100,
            "sine_amp": 0.1, "noise_amp": 0.1, "decay": 1, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) > 0

    def test_extreme_decay_high(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.5, "noise_amp": 0.2, "decay": 1000, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) > 0
        mid = len(result) // 2
        assert np.max(np.abs(result[mid:])) < np.max(np.abs(result[:mid // 2]))

    def test_extreme_decay_low(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.5, "noise_amp": 0.0, "decay": 0.1, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) > 0

    def test_single_sample_duration(self):
        from click_generator import generate_click_sound, SAMPLE_RATE
        params = {
            "filename": "test.wav", "duration": 1 / SAMPLE_RATE, "frequency": 1000,
            "sine_amp": 0.5, "noise_amp": 0.2, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert len(result) == 1


class TestIntegration:
    def test_generate_all_variations_sequentially(self):
        from click_generator import CLICK_VARIATIONS, generate_click_sound
        np.random.seed(42)
        results = [generate_click_sound(params) for params in CLICK_VARIATIONS]
        assert len(results) == len(CLICK_VARIATIONS)
        assert all(len(r) > 0 for r in results)

    def test_output_suitable_for_wav(self):
        from click_generator import generate_click_sound
        params = {
            "filename": "test.wav", "duration": 0.01, "frequency": 1000,
            "sine_amp": 0.3, "noise_amp": 0.2, "decay": 10, "double": False
        }
        result = generate_click_sound(params)
        assert result.dtype == np.int16
        assert np.all(result >= -32768)
        assert np.all(result <= 32767)
