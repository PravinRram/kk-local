// Create Session Page JavaScript
let allSongs = [];

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

let currentUsername = getOrCreateUserId();
let displayName = localStorage.getItem("kk_displayName");

if (!displayName) {
  if (typeof DISPLAY_NAME !== "undefined" && DISPLAY_NAME) {
    displayName = DISPLAY_NAME;
  } else {
    displayName = "Guest " + Math.random().toString(36).substring(2, 6);
  }
  localStorage.setItem("kk_displayName", displayName);
} else if (typeof DISPLAY_NAME !== "undefined" && DISPLAY_NAME) {
  displayName = DISPLAY_NAME;
  localStorage.setItem("kk_displayName", displayName);
}

document.addEventListener("DOMContentLoaded", function () {
  loadSongs();
  loadLeaderboard();
  loadUserRanking();
  loadUserSessions();
  setupEventListeners();

  // Refresh data periodically
  setInterval(loadUserSessions, 30000); // Refresh sessions every 30 seconds
});

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

function displaySongs(songs) {
  const songsList = document.getElementById("songsList");

  if (songs.length === 0) {
    songsList.innerHTML =
      '<div class="text-center text-muted p-5">No songs found matching your criteria.</div>';
    return;
  }

  songsList.innerHTML = songs
    .map((song) => {
      const difficultyClass =
        song.difficulty === "easy"
          ? "bg-success"
          : song.difficulty === "medium"
          ? "bg-warning"
          : "bg-danger";

      return `
            <div class="song-card" data-song-id="${song.id}" onclick="selectSong(${song.id})">
                <div class="song-card-header">
                    <div>
                        <div class="song-card-title">${song.title}</div>
                        <div class="song-card-artist">${song.artist}</div>
                    </div>
                    <span class="badge ${difficultyClass} song-card-badge">${song.difficulty}</span>
                </div>
                <div class="song-card-footer">
                    <span>${song.genre}</span>
                    <span>${formatDuration(song.duration)}</span>
                </div>
            </div>
        `;
    })
    .join("");
}

async function selectSong(songId, replaceExisting = false) {
  try {
    updateStatusBanner("Creating session...", "info");
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");

    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: JSON.stringify({
        song_id: songId,
        username: currentUsername,
        display_name: displayName,
        replace_existing: replaceExisting,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      if (response.status === 409) {
        const isActive = data.status === "active";
        const confirmMessage = isActive
          ? `You are currently in an active session with "${data.song.title}". Do you want to leave this session and start a new one?`
          : `You already have "${data.song.title}" in your queue. Do you want to replace it with a new song?`;

        if (confirm(confirmMessage)) {
          return selectSong(songId, true);
        }
        updateStatusBanner("Session creation cancelled", "warning");
      } else {
        throw new Error(data.error || "Failed to create session");
      }
      return;
    }

    updateStatusBanner(
      `Session created! Redirecting to "${data.song.title}"...`,
      "success"
    );

    // Redirect to join page after a short delay
    setTimeout(() => {
      window.location.href = `/karaoke/join/${data.session_id}`;
    }, 1000);
  } catch (error) {
    console.error("Error creating session:", error);
    updateStatusBanner(
      "Failed to create session. Please try again.",
      "error"
    );
  }
}

async function loadLeaderboard() {
  try {
    const response = await fetch("/api/leaderboard?limit=5");
    const leaderboard = await response.json();
    displayLeaderboard(leaderboard);
  } catch (error) {
    console.error("Error loading leaderboard:", error);
    document.getElementById("leaderboardList").innerHTML =
      '<p class="text-danger small">Could not load leaderboard.</p>';
  }
}

function displayLeaderboard(leaderboard) {
  const container = document.getElementById("leaderboardList");

  if (leaderboard.length === 0) {
    container.innerHTML =
      '<p class="text-muted small">No scores yet. Be the first!</p>';
    return;
  }

  container.innerHTML = leaderboard
    .map((entry, index) => {
      const rank = index + 1;
      const rankClass =
        rank === 1
          ? "rank-1"
          : rank === 2
          ? "rank-2"
          : rank === 3
          ? "rank-3"
          : "";
      const micTimeFormatted = formatTime(entry.total_mic_time);

      return `
            <div class="leaderboard-item">
                <div class="leaderboard-rank ${rankClass}">${rank}</div>
                <div class="leaderboard-info">
                    <div class="leaderboard-name">${entry.user.display_name}</div>
                    <div class="leaderboard-score">${entry.session_count} sessions</div>
                </div>
                <div class="leaderboard-badge">${micTimeFormatted}</div>
            </div>
        `;
    })
    .join("");

  // Replace feather icons
  if (typeof feather !== "undefined") {
    feather.replace();
  }
}

async function loadUserRanking() {
  try {
    const response = await fetch("/api/user/ranking");
    const data = await response.json();
    displayUserRanking(data);
  } catch (error) {
    console.error("Error loading user ranking:", error);
    document.getElementById("userRankingCard").innerHTML =
      '<div class="text-center small text-muted">Could not load your ranking.</div>';
  }
}

function displayUserRanking(data) {
  const container = document.getElementById("userRankingCard");
  const name = (typeof DISPLAY_NAME !== "undefined" && DISPLAY_NAME)
    ? DISPLAY_NAME
    : "You";

  if (!data || data.total_sessions === 0) {
    container.innerHTML = `
            <div class="user-ranking-content">
                <div class="text-center">
                    <i data-feather="mic" style="width: 48px; height: 48px; color: var(--primary-color); margin-bottom: 0.5rem;"></i>
                    <div class="user-ranking-label">${name}</div>
                    <div class="small text-muted">No sessions yet!</div>
                    <div class="small text-muted">Select a song to get started</div>
                </div>
            </div>
        `;
  } else {
    const micTimeFormatted = formatTime(data.total_mic_time || 0);
    const avgScore = data.avg_score ? data.avg_score.toFixed(1) : "0.0";

    container.innerHTML = `
            <div class="user-ranking-content">
                <div class="user-ranking-position">#${data.ranking || "N/A"}</div>
                <div class="user-ranking-label">${name}</div>
                <div class="small text-muted">Your Global Rank</div>
                <div class="user-ranking-stats">
                    <div class="user-stat">
                        <div class="user-stat-value">${data.total_sessions}</div>
                        <div class="user-stat-label">Sessions</div>
                    </div>
                    <div class="user-stat">
                        <div class="user-stat-value">${avgScore}</div>
                        <div class="user-stat-label">Avg Score</div>
                    </div>
                    <div class="user-stat">
                        <div class="user-stat-value">${micTimeFormatted}</div>
                        <div class="user-stat-label">Total Time</div>
                    </div>
                    <div class="user-stat">
                        <div class="user-stat-value">${data.highest_score || 0}</div>
                        <div class="user-stat-label">Best Score</div>
                    </div>
                </div>
            </div>
        `;
  }

  // Replace feather icons
  if (typeof feather !== "undefined") {
    feather.replace();
  }
}

async function loadUserSessions() {
  try {
    const response = await fetch("/api/user/sessions");
    const sessions = await response.json();
    displayUserSessions(sessions);
  } catch (error) {
    console.error("Error loading user sessions:", error);
    document.getElementById("sessionsContainer").innerHTML =
      '<div class="small text-muted">No active sessions</div>';
  }
}

function displayUserSessions(sessions) {
  const container = document.getElementById("sessionsContainer");

  if (sessions.length === 0) {
    container.innerHTML = '<div class="small text-muted">No active sessions</div>';
    return;
  }

  container.innerHTML = sessions
    .map((session) => {
      const statusClass = session.status === "active" ? "active" : "waiting";
      const statusText = session.status === "active" ? "Active" : "Waiting";

      return `
            <div class="session-item" onclick="window.location.href='/karaoke/join/${session.session_id}'">
                <div class="session-item-title">${session.song.title}</div>
                <div class="session-item-artist">${session.song.artist}</div>
                <span class="session-item-status ${statusClass}">${statusText}</span>
            </div>
        `;
    })
    .join("");
}

function setupEventListeners() {
  // Search songs
  document.getElementById("searchSongs")?.addEventListener("input", filterSongs);

  // Filter by genre
  document.getElementById("filterGenre")?.addEventListener("change", filterSongs);

  // Filter by difficulty
  document.getElementById("filterDifficulty")?.addEventListener("change", filterSongs);
}

function filterSongs() {
  const search = document.getElementById("searchSongs").value.toLowerCase();
  const genre = document.getElementById("filterGenre").value;
  const difficulty = document.getElementById("filterDifficulty").value;

  const filtered = allSongs.filter((song) => {
    const matchesSearch =
      !search ||
      song.title.toLowerCase().includes(search) ||
      song.artist.toLowerCase().includes(search);
    const matchesGenre = !genre || song.genre === genre;
    const matchesDifficulty = !difficulty || song.difficulty === difficulty;

    return matchesSearch && matchesGenre && matchesDifficulty;
  });

  displaySongs(filtered);
}

function formatDuration(seconds) {
  if (!seconds) return "Unknown";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatTime(seconds) {
  if (!seconds || seconds === 0) return "0m";
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

function updateStatusBanner(message, type = "info") {
  const banner = document.getElementById("statusMessage");
  if (!banner) return;

  // Remove all status classes
  banner.classList.remove("success", "warning", "error");

  // Add the new status class
  if (type !== "info") {
    banner.classList.add(type);
  }

  // Update the message
  const messageSpan = banner.querySelector("span");
  if (messageSpan) {
    messageSpan.textContent = message;
  }
}

// Make selectSong available globally
window.selectSong = selectSong;
