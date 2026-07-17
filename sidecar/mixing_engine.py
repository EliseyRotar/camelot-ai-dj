import sounddevice as sd
import numpy as np
import os
import librosa
from library import get_track_features, get_db
from techniques import TransitionManager, TransitionTechnique, LongBlend, BassSwap, QuickCut, EchoOut
from analyzer import get_cached_audio

MASTER_SR = 22050
BLOCK_SIZE = 2048
TARGET_LUFS = -14.0

# Precomputed FFT bin indices for 3-band EQ (constants for BLOCK_SIZE @ MASTER_SR)
_FREQS = np.fft.rfftfreq(BLOCK_SIZE, d=1.0 / MASTER_SR)
_LOW_IDX = int(np.searchsorted(_FREQS, 250))
_MID_IDX = int(np.searchsorted(_FREQS, 2000))


class Deck:
    def __init__(self, name: str):
        self.name = name
        self.audio = np.zeros(0, dtype=np.float32)
        self.beat_grid = np.zeros(0, dtype=np.float32)
        self.playhead = 0
        self.is_playing = False

        self.gain = 1.0
        self.eq_low = 1.0
        self.eq_mid = 1.0
        self.eq_high = 1.0

        self.echo_active = False
        self.history_buffer = np.zeros(MASTER_SR * 2, dtype=np.float32)
        self.delay_samples = int(MASTER_SR * 0.5)

        self.original_bpm = 0.0
        self.duration = 0.0
        self.title = ""
        self.artist = ""
        self.last_rms = 0.0

    def load_track(self, filepath: str, track_id: int, original_bpm: float,
                   original_lufs: float, target_bpm: float,
                   title: str = "", artist: str = ""):
        print(f"[{self.name}] Loading '{title}' (id={track_id})...")
        # 1. Load audio — prefer the pre-decoded .npy cache (~33ms) over librosa.load (~8s cold)
        cache_path = get_cached_audio(track_id)
        if cache_path:
            y = np.load(cache_path)
            print(f"[{self.name}]   loaded from cache ({len(y)} samples)")
        else:
            print(f"[{self.name}]   cache miss — decoding via librosa (this is slow on first load)...")
            y, _ = librosa.load(filepath, sr=MASTER_SR, mono=True)

        # 2. LUFS normalize
        lufs_delta = TARGET_LUFS - original_lufs
        norm_gain = 10 ** (lufs_delta / 20.0)
        y = y * norm_gain
        print(f"[{self.name}]   LUFS norm (delta={lufs_delta:.2f}dB, gain={norm_gain:.2f})")

        # 3. Beat grid — use the DB-cached grid, never recompute (saves 6s)
        features = get_track_features(track_id)
        if features and features['beat_grid'] is not None and len(features['beat_grid']) > 0:
            self.beat_grid = features['beat_grid']
        else:
            # Only fall back to recomputing if the DB row is somehow missing
            _, beat_frames = librosa.beat.beat_track(y=y, sr=MASTER_SR)
            self.beat_grid = librosa.frames_to_time(beat_frames, sr=MASTER_SR)

        # 4. Time-stretch to target BPM (load-time, one-shot)
        self.original_bpm = original_bpm
        if original_bpm > 0 and target_bpm > 0:
            rate = target_bpm / original_bpm
            if abs(rate - 1.0) > 0.01:
                print(f"[{self.name}]   stretching {original_bpm:.1f}->{target_bpm:.1f} BPM (rate={rate:.3f})")
                y = librosa.effects.time_stretch(y, rate=rate)
                self.beat_grid = self.beat_grid / rate

        self.audio = y.astype(np.float32)
        self.duration = len(self.audio) / MASTER_SR
        self.playhead = 0
        self.is_playing = False
        self.echo_active = False
        self.history_buffer.fill(0)
        self.title = title
        self.artist = artist
        self.last_rms = 0.0
        print(f"[{self.name}] Loaded '{title}' — {len(self.audio)} samples ({self.duration:.1f}s).")

    def fire_on_beat(self, target_beat_time_sec: float = -1.0):
        if target_beat_time_sec is not None and target_beat_time_sec >= 0 and len(self.beat_grid) > 0:
            idx = int(np.searchsorted(self.beat_grid, target_beat_time_sec))
            idx = min(idx, len(self.beat_grid) - 1)
            self.playhead = int(self.beat_grid[idx] * MASTER_SR)
        elif len(self.beat_grid) > 0:
            self.playhead = int(self.beat_grid[0] * MASTER_SR)
        else:
            self.playhead = 0

        self.is_playing = True
        self.echo_active = False
        print(f"[{self.name}] Fired at playhead {self.playhead} ({self.playhead/MASTER_SR:.2f}s)")

    def cue(self):
        self.is_playing = False
        self.echo_active = False
        if len(self.beat_grid) > 0:
            self.playhead = int(self.beat_grid[0] * MASTER_SR)
        else:
            self.playhead = 0
        self.last_rms = 0.0
        print(f"[{self.name}] Cued (stopped, playhead reset).")

    def get_chunk(self, size: int) -> np.ndarray:
        if not self.is_playing or len(self.audio) == 0:
            if self.echo_active:
                start_idx = len(self.history_buffer) - self.delay_samples
                chunk = self.history_buffer[start_idx: start_idx + size].copy() * 0.6
                if len(chunk) < size:
                    chunk = np.pad(chunk, (0, size - len(chunk)))
                self.last_rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                return chunk.astype(np.float32)
            self.last_rms = 0.0
            return np.zeros(size, dtype=np.float32)

        if self.echo_active:
            start_idx = len(self.history_buffer) - self.delay_samples
            chunk = self.history_buffer[start_idx: start_idx + size].copy() * 0.6
            if len(chunk) < size:
                chunk = np.pad(chunk, (0, size - len(chunk)))
        else:
            end = self.playhead + size
            if end > len(self.audio):
                chunk = self.audio[self.playhead:]
                chunk = np.pad(chunk, (0, size - len(chunk)))
                self.is_playing = False
            else:
                chunk = self.audio[self.playhead:end].copy()
            self.playhead += size
            chunk = chunk * self.gain

        if self.eq_low != 1.0 or self.eq_mid != 1.0 or self.eq_high != 1.0:
            F = np.fft.rfft(chunk)
            F[:_LOW_IDX] *= self.eq_low
            F[_LOW_IDX:_MID_IDX] *= self.eq_mid
            F[_MID_IDX:] *= self.eq_high
            chunk = np.fft.irfft(F, n=size).astype(np.float32)

        if self.is_playing or self.echo_active:
            self.history_buffer[:-size] = self.history_buffer[size:]
            self.history_buffer[-size:] = chunk

        self.last_rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
        return chunk


class MixingEngine:
    def __init__(self):
        self.deck_a = Deck("Deck A")
        self.deck_b = Deck("Deck B")
        self.master_bpm = 120.0
        self.stream = None
        self.transition_manager = TransitionManager()
        self.active_deck = 'A'
        self.armed_technique = "LongBlend"
        self.autopilot_enabled = False
        self._stream_started = False

    def start_stream(self):
        if self._stream_started:
            return
        self.stream = sd.OutputStream(
            samplerate=MASTER_SR,
            channels=1,
            blocksize=BLOCK_SIZE,
            callback=self.audio_callback,
            dtype=np.float32
        )
        self.stream.start()
        self._stream_started = True
        print("Audio stream started.")

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self._stream_started = False
            print("Audio stream stopped.")

    def bars_to_samples(self, bars: float, bpm: float = None) -> int:
        bpm = bpm or self.master_bpm
        if bpm <= 0:
            bpm = 120.0
        beats_per_sec = bpm / 60.0
        samples_per_beat = MASTER_SR / beats_per_sec
        return int(bars * 4 * samples_per_beat)

    def get_armed_technique(self, duration_bars: float = None) -> TransitionTechnique:
        name = self.armed_technique
        if duration_bars is None:
            durations = {"LongBlend": 32.0, "BassSwap": 16.0, "QuickCut": 1.0, "EchoOut": 4.0}
            duration_bars = durations.get(name, 16.0)
        dur = self.bars_to_samples(duration_bars)
        if name == "BassSwap":
            return BassSwap(duration_samples=dur)
        elif name == "QuickCut":
            return QuickCut(duration_samples=dur)
        elif name == "EchoOut":
            return EchoOut(duration_samples=dur)
        else:
            return LongBlend(duration_samples=dur)

    def trigger_transition(self, technique=None):
        if technique is None:
            technique = self.get_armed_technique()
        print(f"Triggering transition: {technique.__class__.__name__} ({technique.duration_samples} samples)")
        if not self.deck_a.is_playing and not self.deck_b.is_playing:
            print("  (no deck playing — transition will still arm but may be silent)")
        self.transition_manager.trigger(technique)

    def audio_callback(self, outdata, frames, time_info, status):
        was_active = self.transition_manager.active_technique is not None
        trans_state = self.transition_manager.tick(frames)
        is_active = self.transition_manager.active_technique is not None

        if self.active_deck == 'A':
            deck_out, deck_in = self.deck_a, self.deck_b
        else:
            deck_out, deck_in = self.deck_b, self.deck_a

        if was_active or is_active:
            out_state = trans_state['deck_out']
            in_state = trans_state['deck_in']
            deck_out.gain = out_state['gain']
            deck_out.eq_low = out_state['eq_low']
            deck_out.eq_mid = out_state['eq_mid']
            deck_out.eq_high = out_state['eq_high']
            deck_out.echo_active = out_state['echo']
            deck_in.gain = in_state['gain']
            deck_in.eq_low = in_state['eq_low']
            deck_in.eq_mid = in_state['eq_mid']
            deck_in.eq_high = in_state['eq_high']
            deck_in.echo_active = in_state['echo']

        if was_active and not is_active:
            self.active_deck = 'B' if self.active_deck == 'A' else 'A'
            deck_out.gain = 0.0
            deck_out.is_playing = False
            deck_out.echo_active = False
            deck_in.gain = 1.0
            print(f"[callback] Transition complete. Active deck now: {self.active_deck}")

        chunk_a = self.deck_a.get_chunk(frames)
        chunk_b = self.deck_b.get_chunk(frames)
        mixed = np.clip(chunk_a + chunk_b, -1.0, 1.0)
        outdata[:, 0] = mixed


engine = MixingEngine()