// static/karaoke/audio-processor.js

/**
 * Enhanced AudioWorkletProcessor for Kampong Konek Karaoke
 *
 * Features:
 * - Audio capture and forwarding
 * - Real-time pitch detection
 * - Audio visualization data generation
 * - Performance monitoring
 */
class KaraokeAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // Configuration
    this.bufferSize = 2048;
    this.sampleRate = 44100;

    // Buffers for processing
    this.audioBuffer = new Float32Array(this.bufferSize);
    this.bufferFillIndex = 0;

    // Frequency analysis
    this.minFrequency = 50; // Hz, lowest detectable frequency
    this.maxFrequency = 1500; // Hz, highest detectable frequency

    // Variables for pitch detection
    this.lastPitch = 0;
    this.pitchConfidence = 0;

    // Smoothing factor for pitch tracking (0-1)
    this.pitchSmoothingFactor = 0.8;

    // Performance monitoring
    this.processingStartTime = 0;

    // Communication with main thread
    this.port.onmessage = this.handleMessage.bind(this);
  }

  /**
   * Handle messages from the main thread
   */
  handleMessage(event) {
    const { type, data } = event.data;

    if (type === "setTargetPitch") {
      // Set the target pitch for comparison
      this.targetPitch = data.pitch;
    } else if (type === "setConfiguration") {
      // Update processor configuration
      if (data.pitchSmoothingFactor !== undefined) {
        this.pitchSmoothingFactor = data.pitchSmoothingFactor;
      }
      if (data.minFrequency !== undefined) {
        this.minFrequency = data.minFrequency;
      }
      if (data.maxFrequency !== undefined) {
        this.maxFrequency = data.maxFrequency;
      }
    }
  }

  /**
   * Calculate the autocorrelation of a signal
   * Used for pitch detection
   */
  autocorrelate(buffer, sampleRate) {
    // ACF (autocorrelation function) implementation
    let SIZE = buffer.length;
    let sumOfSquares = 0;

    // Calculate the sum of squares
    for (let i = 0; i < SIZE; i++) {
      const val = buffer[i];
      sumOfSquares += val * val;
    }

    // If there's no signal, return 0
    if (sumOfSquares < 0.01) return 0;

    let rms = Math.sqrt(sumOfSquares / SIZE);
    if (rms < 0.01) return 0;

    // Find the autocorrelation
    let result = 0;
    let bestOffset = -1;
    let bestCorrelation = 0;

    // Calculate the correlation for each possible offset
    for (let offset = 0; offset < SIZE / 2; offset++) {
      let correlation = 0;

      for (let i = 0; i < SIZE / 2; i++) {
        correlation += buffer[i] * buffer[i + offset];
      }

      correlation = correlation / (SIZE / 2);

      // Find the highest correlation
      if (correlation > bestCorrelation) {
        bestCorrelation = correlation;
        bestOffset = offset;
      }
    }

    // Check if we have a good correlation
    if (bestCorrelation > 0.01) {
      // Parabolic interpolation for better accuracy
      let s0, s1, s2;
      let adjustment;

      if (bestOffset > 0 && bestOffset < SIZE - 1) {
        const shift = bestOffset - 1;
        s0 = buffer[shift] * buffer[shift];
        s1 = buffer[shift + 1] * buffer[shift + 1];
        s2 = buffer[shift + 2] * buffer[shift + 2];
        adjustment = (0.5 * (s0 - s2)) / (s0 - 2 * s1 + s2);
        result = sampleRate / (bestOffset + adjustment);
      } else {
        result = sampleRate / bestOffset;
      }

      // Additional check for valid frequency range
      if (result < this.minFrequency || result > this.maxFrequency) {
        result = 0;
        bestCorrelation = 0;
      }
    } else {
      result = 0;
      bestCorrelation = 0;
    }

    return {
      frequency: result,
      confidence: bestCorrelation,
    };
  }

  /**
   * Calculate frequency to musical note
   */
  frequencyToNote(frequency) {
    if (frequency === 0) return null;

    // A4 = 440Hz
    const noteNames = [
      "C",
      "C#",
      "D",
      "D#",
      "E",
      "F",
      "F#",
      "G",
      "G#",
      "A",
      "A#",
      "B",
    ];
    const a4Index = 69; // MIDI note number for A4

    // Calculate MIDI note number
    const noteNumber = 12 * Math.log2(frequency / 440) + a4Index;
    const roundedNoteNumber = Math.round(noteNumber);

    // Calculate cents (deviation from equal temperament)
    const cents = Math.round((noteNumber - roundedNoteNumber) * 100);

    // Get note name and octave
    const octave = Math.floor(roundedNoteNumber / 12) - 1;
    const noteName = noteNames[roundedNoteNumber % 12];

    return {
      note: noteName + octave,
      cents: cents,
      midiNote: roundedNoteNumber,
    };
  }

  /**
   * Calculate the RMS (Root Mean Square) value of a buffer
   * Used to determine volume level
   */
  calculateRMS(buffer) {
    let sum = 0;

    for (let i = 0; i < buffer.length; i++) {
      sum += buffer[i] * buffer[i];
    }

    return Math.sqrt(sum / buffer.length);
  }

  /**
   * Generate frequency spectrum data for visualization
   */
  generateSpectrumData(buffer, numBands = 64) {
    // Simple spectrum analyzer using average amplitude in frequency ranges
    const bands = new Float32Array(numBands);
    const bucketSize = Math.floor(buffer.length / numBands);

    for (let i = 0; i < numBands; i++) {
      let sum = 0;
      const startIndex = i * bucketSize;
      const endIndex = startIndex + bucketSize;

      for (let j = startIndex; j < endIndex; j++) {
        sum += Math.abs(buffer[j]);
      }

      // Exponential scale for better visualization
      bands[i] = Math.pow(sum / bucketSize, 1.5);
    }

    return bands;
  }

  /**
   * Calculate pitch accuracy compared to target
   */
  calculatePitchAccuracy(detectedPitch, targetPitch) {
    if (!detectedPitch || !targetPitch) return null;

    // Calculate cents difference
    const ratio = detectedPitch / targetPitch;
    const cents = 1200 * Math.log2(ratio);
    const absCents = Math.abs(cents);

    // Score based on cents difference
    // Perfect: within 10 cents
    // Good: within 25 cents
    // Off: more than 25 cents
    if (absCents <= 10) {
      return { status: "perfect", cents: cents };
    } else if (absCents <= 25) {
      return { status: "good", cents: cents };
    } else {
      return { status: "off", cents: cents };
    }
  }

  /**
   * Process audio data
   */
  process(inputs, outputs, parameters) {
    this.processingStartTime = currentTime;

    // Get input data
    const input = inputs[0];
    const channel = input[0];

    if (!channel || channel.length === 0) {
      return true;
    }

    // Copy input to buffer for processing
    for (let i = 0; i < channel.length; i++) {
      if (this.bufferFillIndex >= this.bufferSize) {
        break;
      }
      this.audioBuffer[this.bufferFillIndex++] = channel[i];
    }

    // Process the buffer when it's full
    if (this.bufferFillIndex >= this.bufferSize) {
      // 1. Prepare audio data for sending
      const int16Data = new Int16Array(this.audioBuffer.length);
      for (let i = 0; i < this.audioBuffer.length; i++) {
        // Clamp values to [-1, 1]
        const s = Math.max(-1, Math.min(1, this.audioBuffer[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // 2. Calculate audio volume (RMS)
      const volume = this.calculateRMS(this.audioBuffer);

      // Skip further processing if volume is too low (silence)
      let pitchData = { frequency: 0, confidence: 0, note: null };
      let spectrumData = new Float32Array(64);
      let accuracy = null;

      if (volume > 0.01) {
        // Only process if there's audible sound
        // 3. Detect pitch
        const pitch = this.autocorrelate(this.audioBuffer, this.sampleRate);

        // Apply smoothing to pitch
        if (this.lastPitch && pitch.frequency) {
          pitch.frequency = this.lastPitch * this.pitchSmoothingFactor +
            pitch.frequency * (1 - this.pitchSmoothingFactor);
        }

        if (pitch.frequency > 0) {
          this.lastPitch = pitch.frequency;
          this.pitchConfidence = pitch.confidence;

          // Convert frequency to musical note
          const note = this.frequencyToNote(pitch.frequency);

          pitchData = {
            frequency: pitch.frequency,
            confidence: pitch.confidence,
            note: note,
          };

          // Calculate accuracy if target pitch is available
          if (this.targetPitch) {
            accuracy = this.calculatePitchAccuracy(
              pitch.frequency,
              this.targetPitch,
            );
          }
        }

        // 4. Generate visualization data
        spectrumData = this.generateSpectrumData(this.audioBuffer);
      }

      // 5. Send processed data to main thread
      const processingTime = currentTime - this.processingStartTime;

      this.port.postMessage(
        {
          audio: int16Data.buffer,
          volume: volume,
          pitch: pitchData,
          spectrum: spectrumData,
          accuracy: accuracy,
          processingTime: processingTime,
        },
        [int16Data.buffer],
      );

      // Reset buffer for next batch
      this.audioBuffer = new Float32Array(this.bufferSize);
      this.bufferFillIndex = 0;
    }

    // Return true to keep processor alive
    return true;
  }
}

registerProcessor("audio-processor", KaraokeAudioProcessor);
