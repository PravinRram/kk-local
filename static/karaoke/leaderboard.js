document.addEventListener("DOMContentLoaded", function () {
  loadLeaderboard();
});

async function loadLeaderboard() {
  const container = document.getElementById("leaderboardContainer");
  try {
    const response = await fetch("/api/leaderboard?limit=25"); // Fetch top 25 scores
    if (!response.ok) {
      throw new Error("Failed to load leaderboard data.");
    }
    const scores = await response.json();
    displayLeaderboard(scores);
  } catch (error) {
    console.error("Error loading leaderboard:", error);
    if (container) {
      container.innerHTML =
        '<div class="alert alert-danger m-3">Could not load leaderboard. Please try again later.</div>';
    }
  }
}

function displayLeaderboard(leaderboardData) {
  const container = document.getElementById("leaderboardContainer");
  if (!container) return;

  if (leaderboardData.length === 0) {
    container.innerHTML =
      '<div class="alert alert-info text-center m-3">The leaderboard is empty. Be the first to start karaoking!</div>';
    return;
  }

  const html = `
        <div class="table-responsive">
            <table class="table table-hover leaderboard-table mb-0">
                <thead>
                    <tr>
                        <th scope="col" class="text-center">Rank</th>
                        <th scope="col">Player</th>
                        <th scope="col" class="d-none d-lg-table-cell">Sessions</th>
                        <th scope="col" class="text-end">Time Spent Karaoking</th>
                        <th scope="col" class="text-center d-none d-md-table-cell">Member Since</th>
                    </tr>
                </thead>
                <tbody>
                    ${
    leaderboardData.map((entry, index) => getLeaderboardRow(entry, index)).join("")
  }
                </tbody>
            </table>
        </div>
    `;

  container.innerHTML = html;
  // Replace feather icons in dynamically loaded content
  if (typeof replaceFeatherIcons !== 'undefined') {
    replaceFeatherIcons();
  }
}

function getLeaderboardRow(entry, index) {
  const rank = index + 1;
  let rankBadge;

  if (rank === 1) {
    rankBadge =
      `<span class="rank-badge rank-gold"><i data-feather="award"></i></span>`;
  } else if (rank === 2) {
    rankBadge =
      `<span class="rank-badge rank-silver"><i data-feather="award"></i></span>`;
  } else if (rank === 3) {
    rankBadge =
      `<span class="rank-badge rank-bronze"><i data-feather="award"></i></span>`;
  } else {
    rankBadge = `<span class="rank-badge">${rank}</span>`;
  }

  const memberDate = new Date(entry.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' });
  const timeFormatted = formatTime(entry.total_mic_time);

  return `
        <tr>
            <td class="text-center align-middle">${rankBadge}</td>
            <td class="align-middle">
                <div class="d-flex flex-column">
                    <strong>${entry.user.display_name || entry.user.username}</strong>
                    <small class="text-muted d-lg-none">${entry.session_count} sessions</small>
                </div>
            </td>
            <td class="align-middle d-none d-lg-table-cell">${entry.session_count}</td>
            <td class="align-middle text-end"><strong>${timeFormatted}</strong></td>
            <td class="align-middle text-center d-none d-md-table-cell">${memberDate}</td>
        </tr>
    `;
}

function formatTime(seconds) {
  if (!seconds || seconds === 0) return '0m';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}
