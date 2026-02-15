// Enhanced Song Management JavaScript
// Implements full CRUD functionality with advanced validation and UX

let allSongs = [];
let currentSongId = null;
let youtubePlayer = null;
let currentPage = 1;
const songsPerPage = 9;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  loadSongs();
  setupEventListeners();

  // Initialize tooltips
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  tooltipTriggerList.forEach(function (tooltipTriggerEl) {
    new bootstrap.Tooltip(tooltipTriggerEl);
  });
});

// Load songs from API
async function loadSongs() {
  try {
    showLoading(true);
    const response = await fetch("/api/songs");

    if (!response.ok) {
      throw new Error("Failed to fetch songs");
    }

    allSongs = await response.json();

    // Sort songs alphabetically by title
    allSongs.sort((a, b) => a.title.localeCompare(b.title));

    // Update UI
    updateStatistics();
    displaySongs();
    generatePagination();
  } catch (error) {
    console.error("Error loading songs:", error);
    showAlert("Failed to load songs. Please refresh the page.", "danger");
  } finally {
    showLoading(false);
  }
}

// Display song cards with pagination
function displaySongs() {
  const songsList = document.getElementById("songsList");
  const emptyState = document.getElementById("emptySongs");

  // Filter songs based on current filters
  const filteredSongs = filterSongs();

  if (filteredSongs.length === 0) {
    songsList.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  // Calculate pagination
  const startIndex = (currentPage - 1) * songsPerPage;
  const endIndex = Math.min(startIndex + songsPerPage, filteredSongs.length);
  const songsToShow = filteredSongs.slice(startIndex, endIndex);

  // Generate HTML for song cards
  const songsHTML = songsToShow.map((song) => createSongCard(song)).join("");
  songsList.innerHTML = songsHTML;

  // Initialize feather icons in the newly created cards
  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }

  // Update pagination controls
  generatePagination(filteredSongs.length);
}

// Create HTML for a single song card
function createSongCard(song) {
  // Get difficulty badge color
  let difficultyClass = "bg-easy";
  if (song.difficulty === "medium") difficultyClass = "bg-medium";
  if (song.difficulty === "hard") difficultyClass = "bg-hard";
  if (song.difficulty === "expert") difficultyClass = "bg-expert";

  // Format duration
  const duration = formatDuration(song.duration);

  // Extract YouTube thumbnail (if possible)
  let thumbnailUrl = getThumbnailUrl(song.youtube_url);

  return `
    <div class="col-md-6 col-lg-4">
        <div class="card song-card" data-id="${song.id}">
            <div class="badge ${difficultyClass} difficulty-badge">${song.difficulty}</div>
            <div class="card-img-top text-center">
                ${
    thumbnailUrl
      ? `<img src="${thumbnailUrl}" alt="${
        escapeHtml(song.title)
      }" class="img-fluid">`
      : `<i data-feather="music" style="width: 64px; height: 64px;"></i>`
  }
            </div>
            <div class="card-body">
                <h5 class="card-title" title="${escapeHtml(song.title)}">${
    escapeHtml(song.title)
  }</h5>
                <h6 class="card-subtitle mb-2 text-muted" title="${
    escapeHtml(song.artist)
  }">
                    ${escapeHtml(song.artist)}
                </h6>

                <div class="d-flex gap-2 mb-3">
                    <span class="badge bg-secondary">${
    escapeHtml(song.genre)
  }</span>
                    <span class="badge bg-light text-dark">
                        <i data-feather="clock" class="me-1"></i> ${duration}
                    </span>
                </div>

                <button class="btn btn-sm btn-primary w-100 mb-2"
                    onclick="previewSong(${song.id})">
                    <i data-feather="play"></i> Preview
                </button>

                <div class="song-actions">
                    <button class="btn btn-light edit-song"
                        onclick="editSong(${song.id})"
                        title="Edit Song">
                        <i data-feather="edit-2"></i>
                    </button>
                    <button class="btn btn-light text-danger delete-song"
                        onclick="confirmDelete(${song.id}, '${
    escapeHtml(song.title)
  }', '${escapeHtml(song.artist)}')"
                        title="Delete Song">
                        <i data-feather="trash-2"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
    `;
}

// Extract YouTube video ID and generate thumbnail URL
function getThumbnailUrl(youtubeUrl) {
  if (!youtubeUrl) return null;

  // Extract video ID
  let videoId = null;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = youtubeUrl.match(regExp);

  if (match && match[2].length === 11) {
    videoId = match[2];
    return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
  }

  return null;
}

// Format duration from seconds to MM:SS
function formatDuration(seconds) {
  if (!seconds) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// Generate pagination controls
function generatePagination(totalItems = allSongs.length) {
  const paginationElement = document.querySelector("#pagination ul.pagination");

  // Calculate total pages
  const totalPages = Math.ceil(totalItems / songsPerPage);

  if (totalPages <= 1) {
    paginationElement.innerHTML = "";
    return;
  }

  // Generate pagination HTML
  let paginationHtml = `
        <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="changePage(${
    currentPage - 1
  }); return false;" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;

  // Generate page numbers
  for (let i = 1; i <= totalPages; i++) {
    paginationHtml += `
            <li class="page-item ${currentPage === i ? "active" : ""}">
                <a class="page-link" href="#" onclick="changePage(${i}); return false;">${i}</a>
            </li>
        `;
  }

  paginationHtml += `
        <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="changePage(${
    currentPage + 1
  }); return false;" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;

  paginationElement.innerHTML = paginationHtml;
}

// Change page
function changePage(newPage) {
  const filteredSongs = filterSongs();
  const totalPages = Math.ceil(filteredSongs.length / songsPerPage);

  if (newPage < 1 || newPage > totalPages) {
    return;
  }

  currentPage = newPage;
  displaySongs();

  // Scroll to top of song list
  document.getElementById("songsList").scrollIntoView({ behavior: "smooth" });
}

// Update statistics
function updateStatistics() {
  if (!allSongs || allSongs.length === 0) {
    document.getElementById("totalSongs").textContent = "0";
    document.getElementById("totalGenres").textContent = "0";
    document.getElementById("popularSongs").textContent = "0";
    document.getElementById("avgDuration").textContent = "0:00";
    return;
  }

  // Count total songs
  document.getElementById("totalSongs").textContent = allSongs.length;

  // Count unique genres
  const uniqueGenres = new Set(allSongs.map((song) => song.genre));
  document.getElementById("totalGenres").textContent = uniqueGenres.size;

  // Calculate average duration
  const totalDuration = allSongs.reduce((sum, song) => sum + song.duration, 0);
  const avgDuration = Math.round(totalDuration / allSongs.length);
  document.getElementById("avgDuration").textContent = formatDuration(
    avgDuration,
  );

  // Popular songs (placeholder - in a real app, this would be based on play count)
  document.getElementById("popularSongs").textContent = Math.min(
    5,
    allSongs.length,
  );

  // Animate counters for visual appeal
  animateCounters();
}

// Animate counter numbers
function animateCounters() {
  document.querySelectorAll(".counter").forEach((counter) => {
    const target = parseInt(counter.textContent);
    let count = 0;
    const duration = 1000; // 1 second animation
    const frameDuration = 1000 / 60; // 60fps
    const totalFrames = Math.round(duration / frameDuration);
    const increment = target / totalFrames;

    // Skip animation for non-numeric content
    if (isNaN(target)) return;

    // Start from 0
    counter.textContent = "0";

    // Animate
    const timer = setInterval(() => {
      count += increment;
      if (count >= target) {
        clearInterval(timer);
        counter.textContent = target;
      } else {
        counter.textContent = Math.floor(count);
      }
    }, frameDuration);
  });
}

// Filter songs based on search and filter criteria
function filterSongs() {
  const searchTerm = document.getElementById("searchSongs").value.toLowerCase();
  const selectedGenre = document.getElementById("filterGenre").value;
  const selectedDifficulty = document.getElementById("filterDifficulty").value;

  return allSongs.filter((song) => {
    // Apply search filter
    const matchesSearch = !searchTerm ||
      song.title.toLowerCase().includes(searchTerm) ||
      song.artist.toLowerCase().includes(searchTerm);

    // Apply genre filter
    const matchesGenre = !selectedGenre || song.genre === selectedGenre;

    // Apply difficulty filter
    const matchesDifficulty = !selectedDifficulty ||
      song.difficulty === selectedDifficulty;

    // Return true if song matches all applied filters
    return matchesSearch && matchesGenre && matchesDifficulty;
  });
}

// Preview a song in the modal
function previewSong(songId) {
  const song = allSongs.find((s) => s.id === songId);
  if (!song) return;

  // Update modal content
  document.getElementById("previewTitle").textContent = song.title;
  document.getElementById("previewSongTitle").textContent = song.title;
  document.getElementById("previewArtist").textContent = song.artist;
  document.getElementById("previewGenre").textContent = song.genre;
  document.getElementById("previewDifficulty").textContent =
    song.difficulty.charAt(0).toUpperCase() + song.difficulty.slice(1);
  document.getElementById("previewDuration").textContent = formatDuration(
    song.duration,
  );

  // Set YouTube embed
  const videoId = extractYoutubeId(song.youtube_url);
  const previewContainer = document.getElementById("youtubePreview");

  if (videoId) {
    previewContainer.innerHTML = `<div id="youtubePlayer"></div>`;

    // Initialize YouTube player
    if (typeof YT !== "undefined" && YT.Player) {
      youtubePlayer = new YT.Player("youtubePlayer", {
        height: "100%",
        width: "100%",
        videoId: videoId,
        playerVars: {
          autoplay: 0,
          controls: 1,
          modestbranding: 1,
          rel: 0,
        },
      });
    } else {
      previewContainer.innerHTML = `
                <div class="alert alert-info">
                    YouTube player is not available. <a href="${song.youtube_url}" target="_blank">Open in YouTube</a>
                </div>
            `;
    }
  } else {
    previewContainer.innerHTML = `
            <div class="alert alert-warning">
                Could not extract YouTube video ID. <a href="${song.youtube_url}" target="_blank">Try opening directly</a>
            </div>
        `;
  }

  // Placeholder usage statistics (in a real app, these would come from the database)
  document.getElementById("previewUsageCount").textContent = Math.floor(
    Math.random() * 20,
  );
  document.getElementById("previewAvgScore").textContent = `${
    Math.floor(70 + Math.random() * 20)
  }/100`;

  // Set up edit button
  document.getElementById("editFromPreviewBtn").onclick = function () {
    // Close preview modal and open edit modal
    bootstrap.Modal.getInstance(document.getElementById("previewModal")).hide();
    editSong(songId);
  };

  // Show modal
  const previewModal = new bootstrap.Modal(
    document.getElementById("previewModal"),
  );
  previewModal.show();

  // Clean up when modal is hidden
  document.getElementById("previewModal").addEventListener(
    "hidden.bs.modal",
    function () {
      if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
      }
    },
    { once: true },
  );
}

// Extract YouTube video ID from URL
function extractYoutubeId(url) {
  if (!url) return null;

  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);

  return match && match[2].length === 11 ? match[2] : null;
}

// Edit song
function editSong(songId) {
  const song = allSongs.find((s) => s.id === songId);
  if (!song) return;

  // Set current song ID
  currentSongId = songId;

  // Update form title and button text
  document.getElementById("addSongModalLabel").innerHTML =
    '<i data-feather="edit-2"></i> Edit Song';
  document.getElementById("saveButtonText").textContent = "Update Song";

  // Populate form fields
  const form = document.getElementById("addSongForm");
  form.classList.remove("was-validated");

  document.getElementById("songId").value = song.id;
  document.getElementById("title").value = song.title;
  document.getElementById("artist").value = song.artist;
  document.getElementById("genre").value = song.genre;
  document.getElementById("difficulty").value = song.difficulty;
  document.getElementById("duration").value = song.duration;
  document.getElementById("youtubeUrl").value = song.youtube_url || "";
  document.getElementById("lyricsUrl").value = song.lyrics_url || "";

  // Show modal
  const modal = new bootstrap.Modal(document.getElementById("addSongModal"));
  modal.show();

  // Re-initialize icons
  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }
}

// Confirm song deletion
function confirmDelete(songId, title, artist) {
  currentSongId = songId;

  // Update confirmation modal
  document.getElementById("deleteItemTitle").textContent = title;
  document.getElementById("deleteItemArtist").textContent = artist;

  // Show confirmation modal
  const modal = new bootstrap.Modal(
    document.getElementById("deleteConfirmModal"),
  );
  modal.show();
}

// Set up event listeners
function setupEventListeners() {
  // Add song form submission
  document
    .getElementById("addSongForm")
    .addEventListener("submit", function (event) {
      event.preventDefault();
      saveSong();
    });

  // Delete confirmation
  document
    .getElementById("confirmDeleteBtn")
    .addEventListener("click", deleteSong);

  // Search and filter events
  document.getElementById("searchSongs").addEventListener("input", function () {
    currentPage = 1; // Reset to first page on search
    displaySongs();
  });

  document
    .getElementById("filterGenre")
    .addEventListener("change", function () {
      currentPage = 1;
      displaySongs();
    });

  document
    .getElementById("filterDifficulty")
    .addEventListener("change", function () {
      currentPage = 1;
      displaySongs();
    });

  // Reset filters
  document
    .getElementById("resetFilters")
    .addEventListener("click", function () {
      document.getElementById("searchSongs").value = "";
      document.getElementById("filterGenre").value = "";
      document.getElementById("filterDifficulty").value = "";
      currentPage = 1;
      displaySongs();
    });

  // Reset form when modal is closed
  document
    .getElementById("addSongModal")
    .addEventListener("hidden.bs.modal", function () {
      resetForm();
    });
}

// Save song (create or update)
async function saveSong() {
  const form = document.getElementById("addSongForm");

  // Client-side form validation
  if (!form.checkValidity()) {
    return;
  }

  // Get form data
  const songData = {
    title: document.getElementById("title").value.trim(),
    artist: document.getElementById("artist").value.trim(),
    genre: document.getElementById("genre").value,
    difficulty: document.getElementById("difficulty").value,
    duration: parseInt(document.getElementById("duration").value),
    youtube_url: document.getElementById("youtubeUrl").value.trim(),
    lyrics_url: document.getElementById("lyricsUrl").value.trim(),
  };

  try {
    // Determine if this is a create or update operation
    const isUpdate = !!currentSongId;
    const url = isUpdate ? `/api/songs/${currentSongId}` : "/api/songs";
    const method = isUpdate ? "PUT" : "POST";

    // Send request to API
    const response = await fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(songData),
    });

    // Handle API errors
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "An error occurred");
    }

    // Get updated song data
    const savedSong = await response.json();

    // Close modal
    bootstrap.Modal.getInstance(document.getElementById("addSongModal")).hide();

    // Show success notification
    const message = isUpdate
      ? "Song updated successfully!"
      : "Song added successfully!";
    showSuccessToast(message);

    // Reload songs
    await loadSongs();
  } catch (error) {
    console.error("Error saving song:", error);
    showAlert(error.message || "Failed to save song", "danger");
  }
}

// Delete song
async function deleteSong() {
  if (!currentSongId) return;

  try {
    const response = await fetch(`/api/songs/${currentSongId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "Failed to delete song");
    }

    // Close modal
    bootstrap.Modal.getInstance(
      document.getElementById("deleteConfirmModal"),
    ).hide();

    // Show success notification
    showSuccessToast("Song deleted successfully!");

    // Reload songs
    await loadSongs();
  } catch (error) {
    console.error("Error deleting song:", error);
    showAlert(error.message || "Failed to delete song", "danger");

    // Close modal
    bootstrap.Modal.getInstance(
      document.getElementById("deleteConfirmModal"),
    ).hide();
  }
}

// Reset form to initial state
function resetForm() {
  const form = document.getElementById("addSongForm");
  form.reset();
  form.classList.remove("was-validated");

  // Clear all validation classes
  form.querySelectorAll(".is-valid, .is-invalid").forEach((element) => {
    element.classList.remove("is-valid", "is-invalid");
  });

  // Reset modal title and button text
  document.getElementById("addSongModalLabel").innerHTML =
    '<i data-feather="plus-circle"></i> Add New Song';
  document.getElementById("saveButtonText").textContent = "Add Song";

  // Clear hidden ID field
  document.getElementById("songId").value = "";
  currentSongId = null;

  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }
}

// Display loading spinner
function showLoading(isLoading) {
  const spinner = document.querySelector("#songsList .spinner-border");
  if (spinner) {
    spinner.parentElement.style.display = isLoading ? "block" : "none";
  }
}

// Show alert message
function showAlert(message, type = "info") {
  const alertElement = document.createElement("div");
  alertElement.className = `alert alert-${type} alert-dismissible fade show`;
  alertElement.role = "alert";

  alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

  // Insert at top of songs list
  const container = document.querySelector(".container");
  container.insertBefore(alertElement, container.firstChild);

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    const bsAlert = new bootstrap.Alert(alertElement);
    bsAlert.close();
  }, 5000);
}

// Show success toast
function showSuccessToast(message) {
  document.getElementById("toastMessage").textContent = message;
  const toast = new bootstrap.Toast(document.getElementById("successToast"));
  toast.show();
}

// Utility function to escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ==================== EXTERNAL SONG SEARCH ====================

// Setup search event listeners
function setupSearchListeners() {
  const searchInput = document.getElementById("externalSearchInput");
  const searchBtn = document.getElementById("externalSearchBtn");

  // Search on button click
  searchBtn.addEventListener("click", performExternalSearch);

  // Search on Enter key
  searchInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      performExternalSearch();
    }
  });
}

// Perform external song search
async function performExternalSearch() {
  const searchInput = document.getElementById("externalSearchInput");
  const query = searchInput.value.trim();

  if (query.length < 2) {
    showAlert("Please enter at least 2 characters to search", "warning");
    return;
  }

  const loadingState = document.getElementById("searchLoadingState");
  const noResults = document.getElementById("searchNoResults");
  const resultsContainer = document.getElementById("searchResults");

  try {
    // Show loading state
    loadingState.style.display = "block";
    noResults.style.display = "none";
    resultsContainer.innerHTML = "";

    // Fetch results from API
    const response = await fetch(
      `/api/songs/search?q=${encodeURIComponent(query)}`,
    );

    if (!response.ok) {
      throw new Error("Search failed");
    }

    const data = await response.json();
    const results = data.results || [];

    // Hide loading state
    loadingState.style.display = "none";

    if (results.length === 0) {
      noResults.style.display = "block";
      return;
    }

    // Display search results
    displaySearchResults(results);
  } catch (error) {
    console.error("Error searching songs:", error);
    loadingState.style.display = "none";
    showAlert("Failed to search songs. Please try again.", "danger");
  }
}

// Display search results
function displaySearchResults(results) {
  const resultsContainer = document.getElementById("searchResults");

  const resultsHTML = results
    .map(
      (song) => `
    <div class="col-md-6">
      <div class="card h-100">
        <div class="row g-0">
          <div class="col-4">
            ${
        song.artwork_url
          ? `<img src="${song.artwork_url}" class="img-fluid rounded-start h-100" style="object-fit: cover;" alt="${
            escapeHtml(song.title)
          }">`
          : `<div class="bg-light d-flex align-items-center justify-content-center h-100 rounded-start">
                     <i data-feather="music" style="width: 48px; height: 48px; color: #ddd;"></i>
                   </div>`
      }
          </div>
          <div class="col-8">
            <div class="card-body p-3">
              <h6 class="card-title mb-1">${escapeHtml(song.title)}</h6>
              <p class="card-text small text-muted mb-2">${
        escapeHtml(song.artist)
      }</p>
              <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-secondary">${
        escapeHtml(song.genre)
      }</span>
                <span class="badge bg-info">${
        formatDuration(song.duration)
      }</span>
              </div>
              <button
                class="btn btn-sm btn-primary w-100"
                onclick="addSearchedSong(${song.itunes_id}, '${
        escapeHtml(song.title).replace(/'/g, "\\'")
      }', '${escapeHtml(song.artist).replace(/'/g, "\\'")}', '${
        escapeHtml(song.genre)
      }', ${song.duration})"
              >
                <i data-feather="plus"></i> Add to Library
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
    )
    .join("");

  resultsContainer.innerHTML = resultsHTML;
  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }
}

// Add searched song to library
async function addSearchedSong(itunesId, title, artist, genre, duration) {
  // Pre-fill the add song modal with search result data
  document.getElementById("title").value = title;
  document.getElementById("artist").value = artist;
  document.getElementById("genre").value = genre;
  document.getElementById("duration").value = duration;

  // Estimate difficulty based on duration
  const difficulty = duration < 150
    ? "easy"
    : duration < 270
    ? "medium"
    : "hard";
  document.getElementById("difficulty").value = difficulty;

  // Close search modal
  bootstrap.Modal.getInstance(document.getElementById("searchSongModal"))
    .hide();

  // Open add song modal
  const addModal = new bootstrap.Modal(document.getElementById("addSongModal"));
  addModal.show();

  // Show info about adding YouTube URL
  showAlert(
    `Please add a YouTube URL for "${title}" to complete the song entry. Search YouTube for a karaoke version!`,
    "info",
  );
}

// Initialize search when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  setupSearchListeners();
});

// Export functions for global access
window.changePage = changePage;
window.previewSong = previewSong;
window.editSong = editSong;
window.confirmDelete = confirmDelete;
window.addSearchedSong = addSearchedSong;
