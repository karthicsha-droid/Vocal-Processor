"""
Smooth Real-Time Audio Processor with Ring Buffer
Uses a ring buffer to prevent crackling and underruns
"""

import numpy as np
import sounddevice as sd
import threading
import queue
import msvcrt

class SmoothAudioProcessor:
    def __init__(self, sample_rate=44100, block_size=2048):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.is_running = False
        
        # Processing parameters
        self.center_attenuation = 0.6
        self.vocal_removal_mix = 1.0
        self.master_volume = 1.0
        
        # Thread-safe queue with larger buffer
        self.audio_queue = queue.Queue(maxsize=20)
        
        # Lock for thread-safe parameter updates
        self.param_lock = threading.Lock()
        
    def list_audio_devices(self):
        """List all available audio devices"""
        print("\n=== Available Audio Devices ===")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            marker = ""
            if device['max_input_channels'] > 0 and device['max_output_channels'] > 0:
                marker = " [IN/OUT]"
            elif device['max_input_channels'] > 0:
                marker = " [INPUT]"
            elif device['max_output_channels'] > 0:
                marker = " [OUTPUT]"
            print(f"{i}: {device['name']}{marker}")
        print("================================\n")
        
    def process_audio(self, audio_data):
        """Process stereo audio to create the mixed output"""
        if len(audio_data.shape) < 2 or audio_data.shape[1] < 2:
            # Mono audio - convert to stereo
            mono = audio_data[:, 0] if len(audio_data.shape) > 1 else audio_data
            return np.column_stack([mono, mono])
            
        # Extract left and right channels
        left = audio_data[:, 0]
        right = audio_data[:, 1]
        
        with self.param_lock:
            # Stream 1: Vocal Removal (L - R)
            vocal_removed = (left - right) * self.vocal_removal_mix
            
            # Stream 2: Center Extraction at configurable attenuation
            center = ((left + right) / 2.0) * self.center_attenuation
            
            # Mix both streams together
            mixed = vocal_removed + center
            
            # Apply master volume
            mixed = mixed * self.master_volume
        
        # Soft limiting to prevent clipping
        mixed = np.clip(mixed, -1.0, 1.0)
        
        # Create stereo output
        output = np.column_stack([mixed, mixed])
        
        return output
    
    def input_callback(self, indata, frames, time, status):
        """Input callback - captures and processes audio"""
        if status:
            print(f"Input status: {status}")
        
        try:
            # Process the audio
            processed = self.process_audio(indata.copy())
            
            # Put in queue (non-blocking, drop if queue full)
            try:
                self.audio_queue.put_nowait(processed)
            except queue.Full:
                pass  # Drop frame if queue is full
                
        except Exception as e:
            print(f"Processing error: {e}")
    
    def output_callback(self, outdata, frames, time, status):
        """Output callback - plays processed audio"""
        if status:
            print(f"Output status: {status}")
        
        try:
            # Get processed audio from queue
            data = self.audio_queue.get_nowait()
            outdata[:] = data
        except queue.Empty:
            # No data available - output silence
            outdata.fill(0)
    
    def display_controls(self):
        """Display current settings and controls"""
        print("\n" + "="*60)
        print("  SMOOTH VOCAL MIXER - OPTIMIZED FOR STABILITY")
        print("="*60)
        print("\nCurrent Settings:")
        print(f"  Center Attenuation:  {self.center_attenuation*100:.0f}%")
        print(f"  Vocal Removal Mix:   {self.vocal_removal_mix*100:.0f}%")
        print(f"  Master Volume:       {self.master_volume*100:.0f}%")
        print("\nControls:")
        print("  [1/2] - Decrease/Increase Center Attenuation (±5%)")
        print("  [3/4] - Decrease/Increase Vocal Removal Mix (±10%)")
        print("  [5/6] - Decrease/Increase Master Volume (±5%)")
        print("  [R]   - Reset to defaults")
        print("  [Q]   - Quit")
        print("="*60 + "\n")
    
    def keyboard_listener(self):
        """Listen for keyboard input to adjust parameters"""
        while self.is_running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                
                with self.param_lock:
                    if key == '1':
                        self.center_attenuation = max(0.0, self.center_attenuation - 0.05)
                        print(f"Center Attenuation: {self.center_attenuation*100:.0f}%")
                    elif key == '2':
                        self.center_attenuation = min(1.0, self.center_attenuation + 0.05)
                        print(f"Center Attenuation: {self.center_attenuation*100:.0f}%")
                    elif key == '3':
                        self.vocal_removal_mix = max(0.0, self.vocal_removal_mix - 0.1)
                        print(f"Vocal Removal Mix: {self.vocal_removal_mix*100:.0f}%")
                    elif key == '4':
                        self.vocal_removal_mix = min(1.0, self.vocal_removal_mix + 0.1)
                        print(f"Vocal Removal Mix: {self.vocal_removal_mix*100:.0f}%")
                    elif key == '5':
                        self.master_volume = max(0.0, self.master_volume - 0.05)
                        print(f"Master Volume: {self.master_volume*100:.0f}%")
                    elif key == '6':
                        self.master_volume = min(1.5, self.master_volume + 0.05)
                        print(f"Master Volume: {self.master_volume*100:.0f}%")
                    elif key == 'r':
                        self.center_attenuation = 0.6
                        self.vocal_removal_mix = 1.0
                        self.master_volume = 1.0
                        print("Settings reset to defaults")
                        self.display_controls()
                    elif key == 'q':
                        print("\nStopping...")
                        self.is_running = False
                        break
    
    def start_processing(self, input_device=None, output_device=None):
        """Start real-time audio processing with separate input/output streams"""
        self.display_controls()
        
        self.is_running = True
        
        # Start keyboard listener in separate thread
        keyboard_thread = threading.Thread(target=self.keyboard_listener, daemon=True)
        keyboard_thread.start()
        
        # Pre-fill queue with silence
        silence = np.zeros((self.block_size, 2), dtype=np.float32)
        for _ in range(10):
            self.audio_queue.put(silence)
        
        try:
            # Separate input and output streams for better stability
            with sd.InputStream(
                device=input_device,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=2,
                callback=self.input_callback,
                dtype=np.float32
            ), sd.OutputStream(
                device=output_device,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=2,
                callback=self.output_callback,
                dtype=np.float32,
                prime_output_buffers_using_stream_callback=False
            ):
                print("Processing... (Press Q to quit)\n")
                while self.is_running:
                    sd.sleep(100)
                    
        except KeyboardInterrupt:
            print("\nStopping audio processor...")
            self.is_running = False
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            self.is_running = False


def main():
    processor = SmoothAudioProcessor(sample_rate=44100, block_size=2048)
    
    devices = sd.query_devices()
    
    # Auto-detect CABLE Output for input
    input_device = None
    for i, dev in enumerate(devices):
        if 'CABLE Output' in dev['name'] and dev['max_input_channels'] >= 2:
            input_device = i
            print(f"\nAuto-detected INPUT: {dev['name']}")
            break
    
    if input_device is None:
        print("\n⚠ Warning: Couldn't find CABLE Output. Make sure VB-CABLE is installed.")
        print("Trying Stereo Mix as fallback...")
        for i, dev in enumerate(devices):
            if 'Stereo Mix' in dev['name'] and dev['max_input_channels'] >= 2:
                input_device = i
                print(f"Using INPUT: {dev['name']}")
                break
    
    # Show only output devices for user selection
    print("\n" + "="*60)
    print("  Available OUTPUT Devices:")
    print("="*60)
    output_devices = []
    for i, dev in enumerate(devices):
        if dev['max_output_channels'] >= 2:
            output_devices.append(i)
            print(f"  [{len(output_devices)-1}] {dev['name']}")
    print("="*60)
    
    print("\nSelect your OUTPUT device (speakers/headphones):")
    choice = input("Enter number: ").strip()
    
    if choice.isdigit() and int(choice) < len(output_devices):
        output_device = output_devices[int(choice)]
        device_info = sd.query_devices(output_device)
        processor.sample_rate = int(device_info['default_samplerate'])
        print(f"\nUsing OUTPUT: {device_info['name']}")
        print(f"Sample rate: {processor.sample_rate} Hz\n")
    else:
        output_device = None
        print("\nUsing default output device\n")
    
    # Start processing
    processor.start_processing(input_device, output_device)


if __name__ == "__main__":
    main()
