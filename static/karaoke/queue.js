async function loadQueue() {
  try {
    // If we're on a join page, show the current session
    if (typeof SESSION_ID !== 'undefined' && SESSION_ID) {
      const response = await fetch(`/api/sessions/${SESSION_ID}`);
      if (response.ok) {
        const sessionData = await response.json();
        // Display the current session as a queue item
        const queue = [{
          session_id: sessionData.session_id,
          song_id: sessionData.song.id,
          title: sessionData.song.title,
          artist: sessionData.song.artist,
          genre: sessionData.song.genre,
          difficulty: sessionData.song.difficulty,
          duration: sessionData.song.duration,
          queued_at: sessionData.created_at,
          current: true // Mark as current session
        }];
        displayQueue(queue);
        return;
      }
    }

    // Otherwise, try to load user's queue
    const response = await fetch("/api/queue");
    const queue = await response.json();
    displayQueue(queue);
  } catch (error) {
    console.error("Error loading queue:", error);
    const container = document.getElementById("queueContainer");
    if (container) {
      container.innerHTML =
        '<p class="text-danger small">Could not load queue.</p>';
    }
  }
}

function displayQueue(queue) {
  const container = document.getElementById("queueContainer");
  if (!container) return;

  if (queue.length === 0) {
    container.innerHTML =
      '<p class="text-muted small">Your queue is empty.</p>';
    return;
  }

  container.innerHTML = queue.map((song) => {
    const difficultyBadge = getDifficultyBadge(song.difficulty);
    const isCurrent = song.current;
    const statusBadge = isCurrent ? '<span class="badge bg-success mb-1">Now Playing</span>' : '';

    return `
            <div class="queue-item mb-2 p-2 border rounded ${isCurrent ? 'border-success' : ''}">
                <div class="d-flex align-items-center gap-2">
                    <div class="flex-fill">
                        ${statusBadge}
                        <div class="d-flex justify-content-between align-items-start">
                            <strong class="small">${song.title}</strong>
                            ${!isCurrent ? `<button class="btn btn-sm btn-outline-danger p-0 delete-queue-item" data-session-id="${song.session_id}" style="width: 20px; height: 20px; line-height: 0;">
                                <i data-feather="x" style="width: 14px; height: 14px;"></i>
                            </button>` : ''}
                        </div>
                        <div class="small text-muted">${song.artist}</div>
                        <div class="small text-muted">${song.genre} • ${difficultyBadge} • ${
      formatDuration(song.duration)
    }</div>
                    </div>
                </div>
            </div>
        `;
  }).join("");

  // Replace feather icons in dynamically loaded content
  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }
}

async function deleteQueueItem(sessionId) {
  try {
    const response = await fetch(`/api/queue/${sessionId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "Failed to delete song from queue.");
    }
    // Refresh the queue to show the item has been removed
    await loadQueue();
  } catch (error) {
    console.error("Error deleting queue item:", error);
    alert(error.message);
  }
}

function getDifficultyBadge(difficulty) {
  const badges = {
    "easy": '<span class="badge bg-success">Easy</span>',
    "medium": '<span class="badge bg-warning">Medium</span>',
    "hard": '<span class="badge bg-danger">Hard</span>',
  };
  return badges[difficulty.toLowerCase()] ||
    `<span class="badge bg-secondary">${difficulty}</span>`;
}

function formatDuration(seconds) {
  if (!seconds) return "Unknown";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

document.addEventListener("DOMContentLoaded", function () {
  const queueContainer = document.getElementById("queueContainer");
  if (queueContainer) {
    // Event delegation for delete buttons
    queueContainer.addEventListener("click", function (event) {
      const deleteButton = event.target.closest(".delete-queue-item");
      if (deleteButton) {
        const sessionId = deleteButton.dataset.sessionId;
        if (
          sessionId &&
          confirm("Are you sure you want to remove this song from your queue?")
        ) {
          deleteQueueItem(sessionId);
        }
      }
    });
  }

  loadQueue();
  // Refresh queue every 30 seconds (less frequent since we're showing the current session)
  setInterval(loadQueue, 30000);
});
