// Lyrics Manager for Karaoke App
// Handles fetching, parsing, and syncing LRC format lyrics with YouTube player

class LyricsManager {
  constructor(containerElement, youtubePlayer) {
    this.container = containerElement;
    this.player = youtubePlayer;
    this.lyrics = [];
    this.currentLineIndex = -1;
    this.syncInterval = null;
    this.autoScrollEnabled = true;
    this.fontSizeScale = 1.0;
    this.highlightColor = "#f06b42";
  }

  async loadLyrics(songId) {
    try {
      const response = await fetch(`/api/songs/${songId}/lyrics`);
      if (!response.ok) {
        if (response.status === 404) {
          this.showError("Lyrics unavailable for this song");
        } else {
          this.showError("Failed to load lyrics");
        }
        return;
      }
      const data = await response.json();
      this.parseLRC(data.lyrics);
      this.renderLyrics();
    } catch (error) {
      console.error("Error loading lyrics:", error);
      this.showError("Failed to load lyrics");
    }
  }

  parseLRC(lrcContent) {
    // Parse LRC format: [mm:ss.xx]Line text
    const lines = lrcContent.split("\n");
    this.lyrics = [];

    // Extract metadata and lyrics
    const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)/;
    const metaRegex = /\[(ti|ar|al|by|length):([^\]]*)\]/i;

    // Store metadata
    this.metadata = {};

    for (const line of lines) {
      // Check if it's metadata
      const metaMatch = line.match(metaRegex);
      if (metaMatch) {
        const key = metaMatch[1].toLowerCase();
        const value = metaMatch[2].trim();
        this.metadata[key] = value;
        continue;
      }

      // Check if it's a timed lyric line
      const match = line.match(timeRegex);
      if (match) {
        const minutes = parseInt(match[1]);
        const seconds = parseInt(match[2]);
        const centiseconds = parseInt(match[3].padEnd(3, "0").substring(0, 3));
        const text = match[4].trim();

        const timeInSeconds = minutes * 60 + seconds + centiseconds / 1000;

        if (text) {
          // Only add lines with text
          this.lyrics.push({
            time: timeInSeconds,
            text: text,
            words: this.splitIntoWords(text), // Split text into words for potential word-by-word highlighting
          });
        }
      }
    }

    // Sort by time
    this.lyrics.sort((a, b) => a.time - b.time);

    // Add an end marker based on the next line's timestamp or estimated duration
    if (this.lyrics.length > 0) {
      for (let i = 0; i < this.lyrics.length - 1; i++) {
        this.lyrics[i].endTime = this.lyrics[i + 1].time;
      }

      // For the last line, use the song duration from metadata or estimate
      const lastLine = this.lyrics[this.lyrics.length - 1];
      if (this.metadata && this.metadata.length) {
        // Parse length metadata (e.g. [length:04:30])
        const lengthParts = this.metadata.length.split(":");
        if (lengthParts.length === 2) {
          const durationInSeconds = parseInt(lengthParts[0]) * 60 +
            parseInt(lengthParts[1]);
          lastLine.endTime = durationInSeconds;
        } else {
          // Estimate end time for last line (add 5 seconds)
          lastLine.endTime = lastLine.time + 5;
        }
      } else {
        // Estimate end time for last line (add 5 seconds)
        lastLine.endTime = lastLine.time + 5;
      }
    }
  }

  // Split text into words for potential word-by-word highlighting
  splitIntoWords(text) {
    return text.split(/\s+/).map((word) => ({
      text: word,
      highlighted: false,
    }));
  }

  renderLyrics() {
    if (this.lyrics.length === 0) {
      this.showError("No lyrics available for this song");
      return;
    }

    // Create progress bar
    const progressBarHTML = `
      <div class="karaoke-progress">
        <div class="karaoke-progress-bar" style="width: 0%"></div>
      </div>
    `;

    // Create lyrics HTML with enhanced formatting
    const lyricsHTML = this.lyrics
      .map(
        (line, index) =>
          `<div class="lyric-line" data-index="${index}" data-time="${line.time}" data-end-time="${
            line.endTime || 0
          }">
                ${this.escapeHtml(line.text)}
            </div>`,
      )
      .join("");

    // Preserve existing scroll container if present or create a new one
    const scrollContainer = this.container.querySelector(".lyrics-scroll");

    if (scrollContainer) {
      scrollContainer.innerHTML = lyricsHTML;

      // Add progress bar if it doesn't exist
      const progressBarContainer = this.container.querySelector(
        ".karaoke-progress",
      );
      if (!progressBarContainer) {
        const lyricsContainer = this.container.querySelector(
          ".lyrics-container",
        );
        lyricsContainer.insertAdjacentHTML("afterbegin", progressBarHTML);
      }
    } else {
      // First time rendering - create full structure
      this.container.querySelector(".lyrics-loading")?.remove();
      this.container.innerHTML = `
              <div class="lyrics-container">
                  ${progressBarHTML}
                  <div class="lyrics-overlay"></div>
                  <div class="lyrics-scroll">
                      ${lyricsHTML}
                  </div>
                  <div class="lyrics-overlay-bottom"></div>
              </div>
          `;
    }
  }

  startSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval); // Clear any existing interval
    }

    this.syncInterval = setInterval(() => {
      if (this.player && this.player.getCurrentTime) {
        const currentTime = this.player.getCurrentTime();
        this.updateHighlight(currentTime);
        this.updateProgressBar(currentTime);
      }
    }, 100); // Update every 100ms
  }

  // Update progress bar based on current time and song duration
  updateProgressBar(currentTime) {
    if (!this.player || !currentTime) return;

    const duration = this.player.getDuration() || 1;
    const progressPercent = (currentTime / duration) * 100;

    const progressBar = this.container.querySelector(".karaoke-progress-bar");
    if (progressBar) {
      progressBar.style.width = `${progressPercent}%`;
    }
  }

  updateHighlight(currentTime) {
    // Find the current line based on time
    let lineIndex = -1;
    for (let i = this.lyrics.length - 1; i >= 0; i--) {
      if (currentTime >= this.lyrics[i].time) {
        lineIndex = i;
        break;
      }
    }

    // Only update UI if the current line has changed
    if (lineIndex !== this.currentLineIndex) {
      this.currentLineIndex = lineIndex;

      // Remove previous highlights
      const lines = this.container.querySelectorAll(".lyric-line");
      lines.forEach((line) => {
        line.classList.remove("active", "past", "upcoming", "next");
      });

      // Highlight current line and classify others
      if (lineIndex >= 0) {
        const currentLine = lines[lineIndex];
        if (currentLine) {
          currentLine.classList.add("active");

          // Mark past lines
          for (let i = 0; i < lineIndex; i++) {
            lines[i].classList.add("past");
          }

          // Mark next few lines as upcoming
          for (
            let i = lineIndex + 1;
            i < Math.min(lineIndex + 4, lines.length);
            i++
          ) {
            if (i === lineIndex + 1) {
              lines[i].classList.add("next"); // The immediate next line
            } else {
              lines[i].classList.add("upcoming"); // Lines after the next
            }
          }

          // Scroll to current line if auto-scroll is enabled
          if (this.autoScrollEnabled) {
            this.scrollToLine(currentLine);
          }
        }
      }
    } else if (lineIndex >= 0) {
      // We're still on the same line, update the word highlighting if implemented
      this.updateWordHighlighting(currentTime, lineIndex);
    }
  }

  // Optional word-by-word highlighting within a line
  updateWordHighlighting(currentTime, lineIndex) {
    // This is a simplified implementation - in a real app, you'd need per-word timestamps
    const currentLine = this.lyrics[lineIndex];
    const endTime = currentLine.endTime || currentLine.time + 5;
    const duration = endTime - currentLine.time;

    // Calculate how far through the line we are (0-1)
    const progress = Math.min(1, (currentTime - currentLine.time) / duration);

    // Highlight words based on progress
    if (currentLine.words && currentLine.words.length > 0) {
      const wordCount = currentLine.words.length;
      const wordsToHighlight = Math.ceil(progress * wordCount);

      // Real implementation would use actual word timings
      // This is just a visual approximation
      const lineElement = this.container.querySelector(
        `.lyric-line[data-index="${lineIndex}"]`,
      );
      if (lineElement) {
        // This would be implemented with spans for each word in a real app
      }
    }
  }

  scrollToLine(lineElement) {
    const container = this.container.querySelector(".lyrics-scroll");
    if (container && lineElement) {
      const containerHeight = container.clientHeight;
      const lineTop = lineElement.offsetTop;
      const lineHeight = lineElement.clientHeight;

      // Center the current line
      const scrollTarget = lineTop - containerHeight / 2 + lineHeight / 2;
      container.scrollTo({
        top: scrollTarget,
        behavior: "smooth",
      });
    }
  }

  // Enable auto scrolling
  enableAutoScroll() {
    this.autoScrollEnabled = true;
    // If we already have a current line, scroll to it
    if (this.currentLineIndex >= 0) {
      const currentLine = this.container.querySelector(
        `.lyric-line[data-index="${this.currentLineIndex}"]`,
      );
      if (currentLine) {
        this.scrollToLine(currentLine);
      }
    }
  }

  // Disable auto scrolling
  disableAutoScroll() {
    this.autoScrollEnabled = false;
  }

  // Adjust font size
  setFontSize(scale) {
    this.fontSizeScale = scale;
    const scrollContainer = this.container.querySelector(".lyrics-scroll");
    if (scrollContainer) {
      scrollContainer.style.fontSize = `${scale}rem`;
    }
  }

  stopSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }

    // Reset the highlight
    this.currentLineIndex = -1;
    const lines = this.container.querySelectorAll(".lyric-line");
    lines.forEach((line) => {
      line.classList.remove("active", "past", "upcoming", "next");
    });
  }

  showError(message) {
    this.container.innerHTML = `
            <div class="lyrics-container">
                <div class="lyrics-scroll">
                    <div class="alert alert-info text-center">
                        <i data-feather="info" class="me-2"></i>
                        ${this.escapeHtml(message)}
                    </div>
                </div>
            </div>
        `;
    // Initialize feather icons if available
    if (typeof feather !== "undefined") {
      if (typeof replaceFeatherIcons !== 'undefined') {
        replaceFeatherIcons();
      }
    }
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  destroy() {
    this.stopSync();
    this.lyrics = [];
    this.metadata = {};
    this.currentLineIndex = -1;
    if (this.container) {
      this.container.innerHTML = "";
    }
  }

  // Get song metadata if available
  getMetadata() {
    return this.metadata || {};
  }

  // Export lyrics for saving/sharing
  exportLyrics() {
    if (!this.lyrics || this.lyrics.length === 0) {
      return null;
    }

    // Create LRC format output
    let output = "";

    // Add metadata
    if (this.metadata) {
      for (const [key, value] of Object.entries(this.metadata)) {
        output += `[${key}:${value}]\n`;
      }
      output += "\n";
    }

    // Add lyrics
    this.lyrics.forEach((line) => {
      // Convert time to LRC format [mm:ss.xx]
      const minutes = Math.floor(line.time / 60)
        .toString()
        .padStart(2, "0");
      const seconds = Math.floor(line.time % 60)
        .toString()
        .padStart(2, "0");
      const centiseconds = Math.floor((line.time % 1) * 100)
        .toString()
        .padStart(2, "0");

      output += `[${minutes}:${seconds}.${centiseconds}]${line.text}\n`;
    });

    return output;
  }
}
