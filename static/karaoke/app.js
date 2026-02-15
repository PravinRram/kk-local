// Karaoke App JavaScript
let currentSession = null;
let allSongs = [];

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

// This is the persistent user ID. It should be set by the server in a cookie.
let currentUsername = getCookie("kk_user_id");
if (!currentUsername) {
  // This is a fallback for safety, but the cookie should be set by the server.
  currentUsername = "guest_" + Math.random().toString(36).substring(7);
  console.warn("Could not find user ID cookie, generated temporary one.");
}

// This is a friendly name for display, stored locally.
let displayName = localStorage.getItem("kk_displayName");
if (!displayName) {
  displayName = "Guest " + Math.random().toString(36).substring(2, 6);
  localStorage.setItem("kk_displayName", displayName);
}

let ws = null;
let audioContext = null;
let mediaStream = null;
let audioWorkletNode = null;
let isConnected = false;

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", function () {
  loadSongs();
  setupEventListeners();
});

// Load songs from API
async function loadSongs() {
  try {
    const response = await fetch("/api/songs");
    allSongs = await response.json();
    displaySongs(allSongs);
  } catch (error) {
    console.error("Error loading songs:", error);
    document.getElementById("songsList").innerHTML =
      '<div class="alert alert-danger">Failed to load songs. Please try again.</div>';
  }
}

// Display songs in the modal
function displaySongs(songs) {
  const songsList = document.getElementById("songsList");

  if (songs.length === 0) {
    songsList.innerHTML = '<div class="alert alert-info">No songs found.</div>';
    return;
  }

  songsList.innerHTML = songs.map((song) => `
        <a href="#" class="list-group-item list-group-item-action song-item" data-song-id="${song.id}">
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${song.title}</h6>
                <small>
                    <span class="badge bg-secondary">${song.difficulty}</span>
                </small>
            </div>
            <p class="mb-1">${song.artist}</p>
            <small class="text-muted">${song.genre} • ${
    formatDuration(song.duration)
  }</small>
        </a>
    `).join("");

  // Add click handlers to song items
  document.querySelectorAll(".song-item").forEach((item) => {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      const songId = parseInt(this.dataset.songId);
      selectSong(songId);
    });
  });
}

// Format duration from seconds to mm:ss
function formatDuration(seconds) {
  if (!seconds) return "Unknown";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// Select a song and create a session
async function selectSong(songId, replaceExisting = false) {
  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        song_id: songId,
        username: currentUsername, // The persistent user ID from cookie
        display_name: displayName, // The friendly name from localStorage
        replace_existing: replaceExisting,
      }),
    });

    const data = await response.json();
    const modal = bootstrap.Modal.getInstance(
      document.getElementById("songModal"),
    );

    if (!response.ok) {
      if (response.status === 409) {
        // Handle case where user already has a song in the queue
        const isActive = data.status === "active";
        const confirmMessage = isActive
          ? `You are currently in an active session with "${data.song.title}". Do you want to leave this session and start a new one?`
          : `You already have "${data.song.title}" in your queue. Do you want to replace it with a new song?`;

        if (confirm(confirmMessage)) {
          // User confirmed, retry with replace_existing flag
          return selectSong(songId, true);
        }
      } else {
        throw new Error(data.error || "Failed to create session");
      }
      if (modal) modal.hide();
      return;
    }

    currentSession = data;

    // Close modal
    if (modal) modal.hide();

    // Redirect to join page
    window.location.href = `/karaoke/join/${data.session_id}`;
  } catch (error) {
    console.error("Error creating session:", error);
    updateStatus("Failed to create session. Please try again.", "danger");
  }
}

// Display session information
function displaySessionInfo(session) {
  document.getElementById("songTitle").textContent = session.song.title;
  document.getElementById("songArtist").textContent = session.song.artist;
  document.getElementById("songGenre").textContent = session.song.genre;
  document.getElementById("songDifficulty").textContent =
    session.song.difficulty;
  document.getElementById("sessionId").textContent = session.session_id;
  document.getElementById("sessionInfo").style.display = "block";

  const joinUrl = window.location.origin + "/karaoke/join/" +
    session.session_id;
  document.getElementById("joinUrl").textContent = joinUrl;
  document.getElementById("joinUrl").href = joinUrl;
  document.getElementById("joinUrlInput").value = joinUrl;
  document.getElementById("shareLink").style.display = "block";

  window.karaokeApp.currentSession = session;
}

// Update status message
function updateStatus(message, type = "info") {
  const statusEl = document.getElementById("statusMessage");
  statusEl.className = `alert alert-${type}`;
  statusEl.textContent = message;
}

// Setup event listeners
function setupEventListeners() {
  // Search songs
  document.getElementById("searchSongs").addEventListener(
    "input",
    function (e) {
      filterSongs();
    },
  );

  // Filter by genre
  document.getElementById("filterGenre").addEventListener(
    "change",
    function (e) {
      filterSongs();
    },
  );

  // Filter by difficulty
  document.getElementById("filterDifficulty").addEventListener(
    "change",
    function (e) {
      filterSongs();
    },
  );

  // Mic button to connect/disconnect
  const micBtn = document.getElementById("micBtn");
  if (micBtn) {
    micBtn.addEventListener("click", function () {
      if (currentSession && currentSession.session_id) {
        if (isConnected) {
          disconnectFromSession();
        } else {
          connectToSession(currentSession.session_id);
        }
      } else {
        updateStatus("Please select a song first!", "warning");
      }
    });
  }

  // Submit score button
  document.getElementById("submitScoreBtn").addEventListener(
    "click",
    function () {
      submitScore();
    },
  );

  // Copy link button
  const copyBtn = document.getElementById("copyLinkBtn");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      const input = document.getElementById("joinUrlInput");
      input.select();
      input.setSelectionRange(0, 99999);
      navigator.clipboard.writeText(input.value).then(() => {
        const icon = this.querySelector("i");
        icon.setAttribute("data-feather", "check");
        if (typeof replaceFeatherIcons !== 'undefined') {
          replaceFeatherIcons();
        }
        setTimeout(() => {
          icon.setAttribute("data-feather", "copy");
          if (typeof feather !== 'undefined') {
            feather.replace();
          }
        }, 2000);
      });
    });
  }

  // Log out button
  document.querySelector(".bar-button-right").addEventListener(
    "click",
    function () {
      if (confirm("Are you sure you want to end this session?")) {
        if (currentSession) {
          const scoreModal = new bootstrap.Modal(
            document.getElementById("scoreModal"),
          );
          scoreModal.show();
        } else {
          location.reload();
        }
      }
    },
  );
}

// Filter songs based on search and filters
function filterSongs() {
  const search = document.getElementById("searchSongs").value.toLowerCase();
  const genre = document.getElementById("filterGenre").value;
  const difficulty = document.getElementById("filterDifficulty").value;

  const filtered = allSongs.filter((song) => {
    const matchesSearch = !search ||
      song.title.toLowerCase().includes(search) ||
      song.artist.toLowerCase().includes(search);
    const matchesGenre = !genre || song.genre === genre;
    const matchesDifficulty = !difficulty || song.difficulty === difficulty;

    return matchesSearch && matchesGenre && matchesDifficulty;
  });

  displaySongs(filtered);
}

// Submit score for the current session
async function submitScore() {
  if (!currentSession) {
    updateStatus("No active session to score.", "warning");
    return;
  }

  const score = parseInt(document.getElementById("scoreInput").value);
  const accuracy = parseFloat(document.getElementById("accuracyInput").value);
  const timing = parseFloat(document.getElementById("timingInput").value);
  const notes = document.getElementById("notesInput").value;

  try {
    const response = await fetch("/api/scores", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: currentSession.session_id,
        username: currentUsername,
        display_name: displayName, // Pass the display name
        score: score,
        accuracy: accuracy,
        timing: timing,
        completeness: 100,
        notes: notes,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to submit score");
    }

    // Close modal
    const modal = bootstrap.Modal.getInstance(
      document.getElementById("scoreModal"),
    );
    modal.hide();

    // Show success message
    updateStatus(`Score submitted! Your score: ${score}/100`, "success");

    // Reset session after a delay
    setTimeout(() => {
      location.reload();
    }, 2000);
  } catch (error) {
    console.error("Error submitting score:", error);
    updateStatus("Failed to submit score. Please try again.", "danger");
  }
}

// WebSocket connection functions
async function connectToSession(sessionId) {
  if (isConnected) {
    disconnectFromSession();
    return;
  }

  try {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl =
      `${protocol}//${window.location.host}/karaoke/ws/${sessionId}`;

    updateStatus("Connecting to session...", "info");

    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = async () => {
      console.log("WebSocket connected");
      isConnected = true;
      document.getElementById("micBtn").classList.add("active");
      updateStatus("Connected! Setting up audio...", "success");
      await setupAudio();
    };

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        console.log("Received message:", event.data);

        if (event.data === "session-full") {
          updateStatus("Session is full.", "danger");
          ws.close();
          return;
        }

        if (event.data.startsWith("connected:")) {
          updateStatus("Connected! Waiting for partner...", "success");
        }

        if (event.data === "peer-connected") {
          updateStatus(
            "Partner joined! You can now hear each other.",
            "success",
          );
        }

        if (event.data === "peer-disconnected") {
          updateStatus("Partner disconnected.", "warning");
        }
      } else if (event.data instanceof ArrayBuffer) {
        await playAudio(event.data);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      updateStatus("Connection error.", "danger");
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
      isConnected = false;
      document.getElementById("micBtn").classList.remove("active");
      cleanupAudio();
    };
  } catch (error) {
    console.error("Error connecting:", error);
    updateStatus("Failed to connect.", "danger");
  }
}

async function setupAudio() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    updateStatus("Your browser does not support microphone access.", "danger");
    return;
  }

  try {
    // On many browsers, the AudioContext must be created or resumed after a user gesture.
    if (audioContext && audioContext.state === "suspended") {
      await audioContext.resume();
    }

    // Create the AudioContext if it doesn't exist.
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = audioContext.createMediaStreamSource(mediaStream);

    try {
      // Use the modern AudioWorklet API for audio processing.
      await audioContext.audioWorklet.addModule(
        "/static/karaoke/audio-processor.js",
      );
      audioWorkletNode = new AudioWorkletNode(audioContext, "audio-processor");

      // Listen for messages (processed audio buffers) from the worklet.
      audioWorkletNode.port.onmessage = (event) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(event.data); // event.data is an ArrayBuffer
        }
      };

      source.connect(audioWorkletNode);
      audioWorkletNode.connect(audioContext.destination);
    } catch (workletError) {
      // Fallback to the deprecated ScriptProcessorNode for older browsers.
      console.warn(
        "AudioWorklet failed, falling back to ScriptProcessor.",
        workletError,
      );
      const scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);

      scriptProcessor.onaudioprocess = (event) => {
        const inputData = event.inputBuffer.getChannelData(0);
        const int16Data = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(int16Data.buffer);
        }
      };

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioContext.destination);
    }

    updateStatus("Audio ready! Speak into your microphone.", "success");
  } catch (error) {
    console.error("Error setting up audio:", error);
    updateStatus(
      "Microphone access was denied or an error occurred. Please check your browser permissions and try again.",
      "danger",
    );
    if (ws) ws.close();
  }
}

async function playAudio(audioData) {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }

  try {
    const int16Array = new Int16Array(audioData);
    const float32Array = new Float32Array(int16Array.length);

    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7FFF);
    }

    const audioBuffer = audioContext.createBuffer(
      1,
      float32Array.length,
      audioContext.sampleRate,
    );
    audioBuffer.getChannelData(0).set(float32Array);

    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    source.start();
  } catch (error) {
    console.error("Error playing audio:", error);
  }
}

function cleanupAudio() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }

  if (audioWorkletNode) {
    audioWorkletNode.port.onmessage = null;
    audioWorkletNode.disconnect();
    audioWorkletNode = null;
  }

  if (audioContext) {
    audioContext.close().catch(console.error);
    audioContext = null;
  }
}

function disconnectFromSession() {
  if (ws) {
    ws.close();
  }
  cleanupAudio();
  updateStatus("Disconnected from session.", "info");
}

// Make functions available globally
window.karaokeApp = {
  currentSession,
  currentUsername,
  connectToSession,
  disconnectFromSession,
};
