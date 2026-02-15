// Corrected static/karaoke/join.js

let ws = null;
let audioContext = null;
let mediaStream = null;
let audioWorkletNode = null;
let isConnected = false;
let isPeerConnected = false;
let player = null;
let ignoreStateChange = false; // Flag to prevent broadcast loops
let lyricsManager = null;
let isMicMuted = false;
let isDeafened = false;
let audioGainNode = null;
let currentUserId = null;
let currentDisplayName = null;
let scoreSubmitted = false;
let pendingExit = false;
let scoreModal = null;

// Mic time tracking
let micStartTime = null; // Timestamp when mic was last turned on
let totalMicTime = 0; // Total time in seconds with mic on
let micTimeInterval = null; // Interval for updating display

const micBtn = document.getElementById("micBtn");
const deafenBtn = document.getElementById("deafenBtn");
const leaveBtn = document.getElementById("leaveBtn");
const alertBtn = document.getElementById("alertBtn");
let errorModal = null;
let reportModal = null;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

function setCookie(name, value, maxAgeSeconds = 60 * 60 * 24 * 365) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSeconds}`;
}

function getOrCreateUserId() {
  if (typeof CURRENT_USERNAME !== "undefined" && CURRENT_USERNAME) {
    localStorage.setItem("kk_user_id", CURRENT_USERNAME);
    setCookie("kk_user_id", CURRENT_USERNAME);
    return CURRENT_USERNAME;
  }
  const cookieId = getCookie("kk_user_id");
  if (cookieId) return cookieId;

  let userId = localStorage.getItem("kk_user_id");
  if (!userId) {
    userId = "guest_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("kk_user_id", userId);
  }
  setCookie("kk_user_id", userId);
  return userId;
}

function getOrCreateDisplayName() {
  if (typeof DISPLAY_NAME !== "undefined" && DISPLAY_NAME) {
    localStorage.setItem("kk_displayName", DISPLAY_NAME);
    return DISPLAY_NAME;
  }
  let name = localStorage.getItem("kk_displayName");
  if (!name) {
    name = "Guest " + Math.random().toString(36).substring(2, 6);
    localStorage.setItem("kk_displayName", name);
  }
  return name;
}

function ensureUserIdentity() {
  currentUserId = getOrCreateUserId();
  currentDisplayName = getOrCreateDisplayName();
}
// --- YouTube Player Functions ---

function getYouTubeVideoId(url) {
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);
  return match && match[2].length === 11 ? match[2] : null;
}

function onYouTubeIframeAPIReady() {
  const videoId = getYouTubeVideoId(YOUTUBE_URL);
  if (!videoId) {
    console.error("Invalid YouTube URL");
    document.getElementById("player").innerHTML =
      '<div class="alert alert-danger">Invalid YouTube video URL provided.</div>';
    return;
  }
  player = new YT.Player("player", {
    height: "360",
    width: "640",
    videoId: videoId,
    playerVars: {
      autoplay: 0,
      controls: 1,
      rel: 0,
      showinfo: 0,
      modestbranding: 1,
      fs: 1,
      cc_load_policy: 0,
      iv_load_policy: 3,
      autohide: 1,
      origin: window.location.origin,
      enablejsapi: 1,
      playsinline: 1,
    },
    events: {
      onReady: onPlayerReady,
      onStateChange: onPlayerStateChange,
      onError: onPlayerError,
    },
  });
}

function onPlayerError(event) {
  console.error("YouTube Player Error:", event.data);
  let errorMessage = "An error occurred with the video player.";

  switch (event.data) {
    case 2:
      errorMessage = "Invalid video ID. Please check the YouTube URL.";
      break;
    case 5:
      errorMessage = "HTML5 player error. Please try refreshing the page.";
      break;
    case 100:
      errorMessage = "Video not found or has been removed.";
      break;
    case 101:
    case 150:
      errorMessage =
        "Video cannot be played in embedded players. Please choose a different video that allows embedding.";
      break;
  }

  // Show error in console and update connection status
  console.error(errorMessage);
  const connectionStatus = document.getElementById("connectionStatus");
  if (connectionStatus) {
    connectionStatus.textContent = "Video Error";
    connectionStatus.className = "badge bg-danger";
  }

  // Show alert to user
  if (typeof showErrorModal === "function") {
    showErrorModal("Video Playback Error", errorMessage);
  } else {
    alert(errorMessage);
  }
}

function onPlayerReady(event) {
  console.log("YouTube player ready");

  // Update song duration in sidebar
  const duration = player.getDuration();
  const durationElement = document.getElementById("songDuration");
  if (durationElement && duration) {
    const minutes = Math.floor(duration / 60);
    const seconds = Math.floor(duration % 60);
    durationElement.textContent = `${minutes}:${
      seconds.toString().padStart(2, "0")
    }`;
  }

  // Update connection status
  const connectionStatus = document.getElementById("connectionStatus");
  if (connectionStatus) {
    connectionStatus.textContent = "Ready";
    connectionStatus.className = "badge bg-success";
  }

  // Initialize lyrics
  const lyricsContainer = document.getElementById("lyricsDisplay");
  if (lyricsContainer) {
    lyricsManager = new LyricsManager(lyricsContainer, player);
    lyricsManager.loadLyrics(SESSION_SONG_ID);

    // Setup lyrics controls
    setupLyricsControls();
  }

  const playBtnBar = document.getElementById("playBtn");
  if (playBtnBar) {
    playBtnBar.addEventListener("click", togglePlayPause);
  }
}

function onPlayerStateChange(event) {
  if (ignoreStateChange) return;
  const time = player.getCurrentTime() || 0;
  if (event.data === YT.PlayerState.PLAYING) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "PLAY", time: time }));
    }
    updatePlayPauseIcon(true);
    if (lyricsManager) {
      lyricsManager.startSync();
      // Update karaoke progress indicator if it exists
      const progressBar = document.querySelector(".karaoke-progress-bar");
      if (progressBar) {
        updateKaraokeProgress();
      }
    }
  } else if (event.data === YT.PlayerState.PAUSED) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "PAUSE", time: time }));
    }
    updatePlayPauseIcon(false);
    if (lyricsManager) lyricsManager.stopSync();
  } else if (event.data === YT.PlayerState.ENDED) {
    if (lyricsManager) lyricsManager.stopSync();
    maybePromptScore(false);
  }
}

// Update karaoke progress indicator
function updateKaraokeProgress() {
  if (!player) return;

  const progressInterval = setInterval(() => {
    if (player.getPlayerState() === YT.PlayerState.PLAYING) {
      const duration = player.getDuration() || 1;
      const currentTime = player.getCurrentTime() || 0;
      const progressPercent = (currentTime / duration) * 100;

      const progressBar = document.querySelector(".karaoke-progress-bar");
      if (progressBar) {
        progressBar.style.width = `${progressPercent}%`;
      }
    } else if (
      player.getPlayerState() === YT.PlayerState.ENDED ||
      player.getPlayerState() === YT.PlayerState.PAUSED
    ) {
      clearInterval(progressInterval);
    }
  }, 1000);
}

function togglePlayPause() {
  if (!player) return;
  const state = player.getPlayerState();
  if (state === YT.PlayerState.PLAYING) {
    player.pauseVideo();
  } else {
    player.playVideo();
  }
}

function updatePlayPauseIcon(isPlaying) {
  const playBtn = document.getElementById("playBtn");
  if (playBtn) {
    const icon = playBtn.querySelector("i");
    icon.setAttribute("data-feather", isPlaying ? "pause" : "play");
    if (typeof feather !== 'undefined') {
      feather.replace();
    }
  }
}

// --- App Initialization and DOM ---

document.addEventListener("DOMContentLoaded", function () {
  errorModal = new bootstrap.Modal(document.getElementById("errorModal"));
  reportModal = new bootstrap.Modal(document.getElementById("reportModal"));
  scoreModal = new bootstrap.Modal(document.getElementById("scoreModal"));
  ensureUserIdentity();

  // Keep video player hidden - it plays audio only
  const videoPlayer = document.getElementById("videoPlayer");
  if (videoPlayer) {
    videoPlayer.style.display = "none";
    videoPlayer.style.visibility = "hidden";
  }

  document.getElementById("inviteBtn").addEventListener("click", function () {
    navigator.clipboard.writeText(window.location.href).then(() => {
      this.innerHTML = '<i data-feather="check"></i> Copied!';
      if (typeof feather !== 'undefined') {
        feather.replace();
      }
      setTimeout(() => {
        this.innerHTML = '<i data-feather="share-2"></i> Share';
        if (typeof feather !== 'undefined') {
          feather.replace();
        }
      }, 2000);
    });
  });

  document
    .getElementById("retryConnectionBtn")
    .addEventListener("click", () => {
      errorModal.hide();
      connectToSession();
    });

  // Alert button to open report modal
  if (alertBtn) {
    alertBtn.addEventListener("click", () => {
      reportModal.show();
      setTimeout(() => {
        if (typeof feather !== 'undefined') {
          feather.replace();
        }
      }, 100);
    });
  }

  // Confirm report button
  document.getElementById("confirmReportBtn").addEventListener("click", () => {
    reportModal.hide();
    disconnectFromSession();
  });

  // NOTE: connectToSession() is NOT called here automatically. User must click the mic button.
});

// Auto-leave session when user closes the tab or navigates away
window.addEventListener("beforeunload", function (e) {
  if (isConnected) {
    // Disconnect from the session - WebSocket close will trigger server-side cleanup
    disconnectFromSession();
  }
});

function showError(message) {
  document.getElementById("errorModalMessage").textContent = message;
  if (errorModal) {
    errorModal.show();
    setTimeout(() => {
      if (typeof feather !== 'undefined') {
        feather.replace();
      }
    }, 100);
  }
}

// --- WebSocket and Connection Logic ---

async function connectToSession() {
  if (isConnected) return;
  try {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl =
      `${protocol}//${window.location.host}/karaoke/ws/${SESSION_ID}`;
    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = async () => {
      console.log("WebSocket connected");
      isConnected = true;
      micBtn.classList.add("active");

      // Send user identification to backend
      ws.send(JSON.stringify({
        type: "USER_JOIN",
        user_id: currentUserId,
        display_name: currentDisplayName
      }));

      // Start tracking mic time
      startMicTimeTracking();

      await setupAudio();
      fetchSessionInfo();
    };

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        if (event.data.startsWith("{")) {
          try {
            const msg = JSON.parse(event.data);
            handleControlMessage(msg);
          } catch (e) {
            console.warn("Received non-JSON text message:", event.data);
          }
        } else {
          // Handle legacy string messages (for backward compatibility)
          if (event.data === "session-full") {
            showError("Session is full. Please try again later.");
            ws.close();
          } else if (event.data === "peer-connected") {
            isPeerConnected = true;
            updateSessionStatus("active");
            fetchSessionInfo();
          } else if (event.data === "peer-disconnected") {
            isPeerConnected = false;
            fetchSessionInfo();
          }
        }
      } else if (event.data instanceof ArrayBuffer) {
        await playAudio(event.data);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      showError("Connection error. Please check your internet and try again.");
    };
    ws.onclose = () => {
      console.log("WebSocket closed");
      isConnected = false;
      isPeerConnected = false;
      micBtn.classList.remove("active");
      stopMicTimeTracking();
      cleanupAudio();
      updateSessionStatus("disconnected");
      fetchSessionInfo();
    };
  } catch (error) {
    console.error("Error connecting to session:", error);
    showError(
      "Failed to connect. Please check browser permissions and try again.",
    );
  }
}

function handleControlMessage(msg) {
  switch (msg.type) {
    case "PARTICIPANT_UPDATE":
      // Handle participant count updates
      const participantCount = msg.count;
      isPeerConnected = participantCount > 1;

      // Update session status based on participant count
      if (participantCount > 1) {
        updateSessionStatus("active");
      } else {
        updateSessionStatus("waiting");
      }

      // Refresh participant list
      fetchSessionInfo();

      console.log(`[Session] Participants updated: ${participantCount} total`);
      break;

    case "PLAY":
      if (!player) return;
      ignoreStateChange = true;
      player.seekTo(msg.time, true);
      player.playVideo();
      updatePlayPauseIcon(true);
      if (lyricsManager) lyricsManager.startSync();
      setTimeout(() => {
        ignoreStateChange = false;
      }, 150);
      break;

    case "PAUSE":
      if (!player) return;
      ignoreStateChange = true;
      player.pauseVideo();
      updatePlayPauseIcon(false);
      if (lyricsManager) lyricsManager.stopSync();
      setTimeout(() => {
        ignoreStateChange = false;
      }, 150);
      break;
  }
}

function disconnectFromSession() {
  stopMicTimeTracking();
  if (ws) {
    ws.close();
  }
  cleanupAudio();
}

// --- Audio Processing ---

async function setupAudio() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showError("Your browser does not support microphone access.");
    return;
  }
  try {
    if (audioContext && audioContext.state === "suspended") {
      await audioContext.resume();
    }
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 48000,
      });
    }
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = audioContext.createMediaStreamSource(mediaStream);

    // Create gain node for audio output control (deafen)
    audioGainNode = audioContext.createGain();
    audioGainNode.gain.value = 1.0;

    try {
      await audioContext.audioWorklet.addModule(
        "/static/karaoke/audio-processor.js",
      );
      audioWorkletNode = new AudioWorkletNode(audioContext, "audio-processor");
      audioWorkletNode.port.onmessage = (event) => {
        if (
          ws && ws.readyState === WebSocket.OPEN && !isMicMuted && !isDeafened
        ) {
          // Extract just the audio buffer from the message
          if (event.data && event.data.audio) {
            ws.send(event.data.audio);
          }
        }
      };
      source.connect(audioWorkletNode);
      audioWorkletNode.connect(audioGainNode);
      audioGainNode.connect(audioContext.destination);
    } catch (workletError) {
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
          int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        if (
          ws && ws.readyState === WebSocket.OPEN && !isMicMuted && !isDeafened
        ) {
          ws.send(int16Data.buffer);
        }
      };
      source.connect(scriptProcessor);
      scriptProcessor.connect(audioGainNode);
      audioGainNode.connect(audioContext.destination);
    }
    console.log("Audio ready! Microphone is active.");
  } catch (error) {
    console.error("Error setting up audio:", error);
    showError(
      "Microphone access was denied or an error occurred. Please check your browser permissions and try again.",
    );
    if (ws) ws.close();
  }
}

async function playAudio(audioData) {
  if (!audioContext) return;
  try {
    const int16Array = new Int16Array(audioData);
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7fff);
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
  if (audioWorkletNode) {
    audioWorkletNode.port.onmessage = null;
    audioWorkletNode.disconnect();
    audioWorkletNode = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (audioContext) {
    audioContext.close().catch(console.error);
    audioContext = null;
  }
}

// --- Session Info ---

async function fetchSessionInfo() {
  try {
    const response = await fetch(`/api/sessions/${SESSION_ID}`);
    if (response.ok) {
      const sessionData = await response.json();
      displayParticipants(sessionData.participants);
    }
  } catch (error) {
    console.error("Error fetching session info:", error);
  }
}

function displayParticipants(participants) {
  const container = document.getElementById("participantsContainer");
  if (!container) return;
  if (!participants || participants.length === 0) {
    container.innerHTML =
      '<div class="small text-muted">Just you in here.</div>';
    return;
  }
  container.innerHTML = participants
    .map(
      (p) => {
        // Handle nested user object structure
        const user = p.user || p;
        const displayName = user.display_name || user.username || "Guest";
        return `
        <div class="d-flex align-items-center mb-2">
            <i data-feather="user" class="me-2 text-muted"></i>
            <span class="small">${displayName}</span>
        </div>
    `;
      },
    )
    .join("");
  if (typeof feather !== 'undefined') {
    feather.replace();
  }
}

function updateSessionStatus(status) {
  const statusBadge = document.getElementById("sessionStatus");
  if (statusBadge) {
    statusBadge.textContent = status;
    statusBadge.className = "badge " +
      (status === "active" ? "bg-success" : "bg-info");
  }
}

// --- Mic Time Tracking Functions ---

function startMicTimeTracking() {
  if (!isMicMuted && !micStartTime) {
    micStartTime = Date.now();
  }

  // Update display every second
  micTimeInterval = setInterval(() => {
    updateMicTimeDisplay();
  }, 1000);
}

function stopMicTimeTracking() {
  if (micStartTime) {
    const elapsed = Math.floor((Date.now() - micStartTime) / 1000);
    totalMicTime += elapsed;
    micStartTime = null;
  }

  if (micTimeInterval) {
    clearInterval(micTimeInterval);
    micTimeInterval = null;
  }

  console.log(`Total mic time: ${totalMicTime} seconds`);
}

function updateMicTimeDisplay() {
  let currentTotal = totalMicTime;

  // Add current session time if mic is active
  if (micStartTime && !isMicMuted) {
    const currentSession = Math.floor((Date.now() - micStartTime) / 1000);
    currentTotal += currentSession;
  }

  // Update the display
  const micTimeElement = document.getElementById("micTime");
  if (micTimeElement) {
    micTimeElement.textContent = formatMicTime(currentTotal);
  }
}

function formatMicTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

function getTotalMicTime() {
  let total = totalMicTime;

  // Add current session time if mic is active
  if (micStartTime && !isMicMuted) {
    const currentSession = Math.floor((Date.now() - micStartTime) / 1000);
    total += currentSession;
  }

  return total;
}

function maybePromptScore(exitAfter) {
  if (scoreSubmitted || !scoreModal) return false;
  const micTime = getTotalMicTime();
  if (!micTime || micTime <= 0) return false;
  pendingExit = exitAfter;
  const micTimeLabel = document.getElementById("scoreMicTime");
  if (micTimeLabel) {
    micTimeLabel.textContent = formatMicTime(micTime);
  }
  scoreModal.show();
  return true;
}

async function submitScore() {
  const scoreInput = document.getElementById("scoreInput");
  const accuracyInput = document.getElementById("accuracyInput");
  const timingInput = document.getElementById("timingInput");
  const notesInput = document.getElementById("notesInput");

  const score = parseInt(scoreInput?.value, 10);
  if (Number.isNaN(score)) {
    showError("Please enter a valid score.");
    return;
  }

  const accuracy = accuracyInput ? parseInt(accuracyInput.value, 10) : null;
  const timing = timingInput ? parseInt(timingInput.value, 10) : null;
  const notes = notesInput ? notesInput.value : null;

  const csrfToken = document
    .querySelector('meta[name="csrf-token"]')
    ?.getAttribute("content");

  try {
    const response = await fetch("/api/scores", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: JSON.stringify({
        session_id: SESSION_ID,
        username: currentUserId,
        display_name: currentDisplayName,
        score: score,
        mic_time: getTotalMicTime(),
        accuracy: Number.isNaN(accuracy) ? null : accuracy,
        timing: Number.isNaN(timing) ? null : timing,
        notes: notes,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "Failed to submit score.");
    }

    scoreSubmitted = true;
    scoreModal.hide();

    if (pendingExit) {
      pendingExit = false;
      disconnectFromSession();
      window.location.href = "/karaoke";
    }
  } catch (error) {
    console.error("Error submitting score:", error);
    showError(error.message || "Failed to submit score. Please try again.");
  }
}

// --- Final Event Listeners ---

// Microphone toggle
micBtn.addEventListener("click", () => {
  if (!isConnected) {
    connectToSession();
    return;
  }

  isMicMuted = !isMicMuted;
  const icon = micBtn.querySelector("i");

  if (isMicMuted) {
    // Mic was turned off - stop tracking
    if (micStartTime) {
      const elapsed = Math.floor((Date.now() - micStartTime) / 1000);
      totalMicTime += elapsed;
      micStartTime = null;
    }
    icon.setAttribute("data-feather", "mic-off");
    micBtn.classList.add("muted");
  } else {
    // Mic was turned on - start tracking
    micStartTime = Date.now();
    icon.setAttribute("data-feather", "mic");
    micBtn.classList.remove("muted");
  }
  if (typeof feather !== 'undefined') {
    feather.replace();
  }
});

// Deafen toggle (mute both mic and audio)
if (deafenBtn) {
  deafenBtn.addEventListener("click", () => {
    isDeafened = !isDeafened;
    const icon = deafenBtn.querySelector("i");

    if (isDeafened) {
      // Mute both microphone and audio output
      const wasMicActive = !isMicMuted;
      isMicMuted = true;

      // Stop tracking mic time if it was active
      if (wasMicActive && micStartTime) {
        const elapsed = Math.floor((Date.now() - micStartTime) / 1000);
        totalMicTime += elapsed;
        micStartTime = null;
      }

      if (audioGainNode) {
        audioGainNode.gain.value = 0;
      }
      icon.setAttribute("data-feather", "volume-x");
      deafenBtn.classList.add("muted");

      // Update mic button to show it's also muted
      const micIcon = micBtn.querySelector("i");
      micIcon.setAttribute("data-feather", "mic-off");
      micBtn.classList.add("muted");
    } else {
      // Unmute audio output (mic stays as it was)
      if (audioGainNode) {
        audioGainNode.gain.value = 1.0;
      }
      icon.setAttribute("data-feather", "volume-2");
      deafenBtn.classList.remove("muted");

      // Reset mic to unmuted state
      isMicMuted = false;
      micStartTime = Date.now(); // Start tracking again
      const micIcon = micBtn.querySelector("i");
      micIcon.setAttribute("data-feather", "mic");
      micBtn.classList.remove("muted");
    }
    if (typeof feather !== 'undefined') {
      feather.replace();
    }
  });
}

leaveBtn.addEventListener("click", () => {
  const leaveModal = new bootstrap.Modal(document.getElementById("leaveModal"));
  leaveModal.show();
});

document.getElementById("confirmLeaveBtn").addEventListener("click", () => {
  const leaveModalEl = document.getElementById("leaveModal");
  const leaveModal = bootstrap.Modal.getInstance(leaveModalEl);
  if (leaveModal) {
    leaveModal.hide();
  }
  const prompted = maybePromptScore(true);
  if (!prompted) {
    disconnectFromSession();
    window.location.href = "/karaoke";
  }
});

const skipScoreBtn = document.getElementById("skipScoreBtn");
if (skipScoreBtn) {
  skipScoreBtn.addEventListener("click", () => {
    if (scoreModal) {
      scoreModal.hide();
    }
    if (pendingExit) {
      pendingExit = false;
      disconnectFromSession();
      window.location.href = "/karaoke";
    }
  });
}

const submitScoreBtn = document.getElementById("submitScoreBtn");
if (submitScoreBtn) {
  submitScoreBtn.addEventListener("click", () => {
    submitScore();
  });
}

// Lyrics control functions
function setupLyricsControls() {
  const autoScrollBtn = document.getElementById("autoScrollBtn");
  const increaseFontBtn = document.getElementById("increaseFontBtn");
  const decreaseFontBtn = document.getElementById("decreaseFontBtn");

  let isAutoScrollEnabled = true;
  let currentFontSize = 1; // 1 = default, range from 0.7 to 1.5

  // Auto-scroll toggle
  if (autoScrollBtn) {
    autoScrollBtn.addEventListener("click", () => {
      isAutoScrollEnabled = !isAutoScrollEnabled;

      const toggleIndicator = autoScrollBtn.querySelector(".toggle-indicator");
      if (isAutoScrollEnabled) {
        if (toggleIndicator) {
          toggleIndicator.textContent = "ON";
          toggleIndicator.classList.add("active");
        }
        if (lyricsManager) {
          lyricsManager.enableAutoScroll();
        }
      } else {
        if (toggleIndicator) {
          toggleIndicator.textContent = "OFF";
          toggleIndicator.classList.remove("active");
          toggleIndicator.style.background = "#f8d7da";
          toggleIndicator.style.color = "#721c24";
        }
        if (lyricsManager) {
          lyricsManager.disableAutoScroll();
        }
      }
      if (typeof feather !== 'undefined') {
        feather.replace();
      }
    });
  }

  // Font size controls
  if (increaseFontBtn) {
    increaseFontBtn.addEventListener("click", () => {
      if (currentFontSize < 1.5) {
        currentFontSize += 0.1;
        updateLyricsFontSize();
      }
    });
  }

  if (decreaseFontBtn) {
    decreaseFontBtn.addEventListener("click", () => {
      if (currentFontSize > 0.7) {
        currentFontSize -= 0.1;
        updateLyricsFontSize();
      }
    });
  }

  function updateLyricsFontSize() {
    const lyricsScroll = document.querySelector(".lyrics-scroll");
    if (lyricsScroll) {
      lyricsScroll.style.fontSize = `${currentFontSize}rem`;
    }
  }
}
