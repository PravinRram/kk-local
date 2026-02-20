// Real-time search
let searchTimeout;
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');

if (searchInput) {
    const searchResultsBox = document.getElementById('searchResultsBox');
    const clearBtn = document.getElementById('clearSearchBtn');
    
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        
        // Show/hide clear button
        if (this.value.length > 0) {
            clearBtn.classList.add('visible');
        } else {
            clearBtn.classList.remove('visible');
        }
        
        if (query.length < 1) {
            searchResults.innerHTML = '';
            searchResultsBox.classList.remove('active');
            return;
        }

        searchTimeout = setTimeout(() => {
            fetch(`/api/search?q=${encodeURIComponent(query)}&type=all`)
                .then(response => response.json())
                .then(data => {
                    displaySearchResults(data);
                });
        }, 300);
    });
    
    // Hide results box when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.sidebar')) {
            searchResultsBox.classList.remove('active');
        }
    });
    
    // Keep results box visible when clicking inside sidebar
    searchInput.addEventListener('focus', function() {
        if (this.value.trim().length > 0) {
            searchResultsBox.classList.add('active');
        }
    });
}

function displaySearchResults(results) {
    const searchResultsBox = document.getElementById('searchResultsBox');
    const searchResults = document.getElementById('searchResults');
    
    if (results.length === 0) {
        searchResults.innerHTML = '<p class="text-muted small px-3 py-2">No results found</p>';
        searchResultsBox.classList.add('active');
        return;
    }

    // Separate users and forums
    const users = results.filter(r => r.type === 'user');
    const forums = results.filter(r => r.type === 'forum');
    const hashtags = results.filter(r => r.type === 'hashtag');

    let html = '';
    
    // Users section
    if (users.length > 0) {
        html += '<div class="search-section-header">Users</div>';
        users.forEach(user => {
            html += `
                <div class="search-result-item" onclick="window.location.href='/profile/${user.id}'">
                    <div class="d-flex align-items-center">
                        <img src="${user.profile_picture}" class="user-avatar-small me-2">
                        <div>
                            <strong>${user.username}</strong>
                            <span class="age-badge ms-1">${user.age} years</span>
                        </div>
                    </div>
                </div>
            `;
        });
    }
    
    // Divider between sections
    if (users.length > 0 && forums.length > 0) {
        html += '<div class="search-section-divider"></div>';
    }
    
    // Forums section
    if (forums.length > 0) {
        html += '<div class="search-section-header">Forums</div>';
        forums.forEach(forum => {
            html += `
                <div class="search-result-item" onclick="window.location.href='/forum/${forum.id}'">
                    <div class="d-flex align-items-center gap-2">
                        ${forum.banner
                            ? `<img src="${forum.banner}" class="rounded forum-banner-small">`
                            : `<div class="rounded d-flex align-items-center justify-content-center flex-shrink-0" style="width: 48px; height: 28px; background: var(--kk-gradient);"><span class="material-symbols-outlined" style="font-size: 16px; color: white;">forum</span></div>`
                        }
                        <div>
                            <strong>${forum.name}</strong>
                            <p class="mb-0 small text-muted">${forum.member_count} members</p>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    // Hashtags section
    if (hashtags.length > 0) {
        if (users.length > 0 || forums.length > 0) {
            html += '<div class="search-section-divider"></div>';
        }
        html += '<div class="search-section-header">Hashtags</div>';
        hashtags.forEach(hashtag => {
            html += `
                <div class="search-result-item" onclick="window.location.href='/hashtag/${encodeURIComponent(hashtag.hashtag.substring(1))}'">
                    <div class="d-flex align-items-center">
                        <span class="material-symbols-outlined me-2" style="color: var(--primary-color);">tag</span>
                        <strong>${hashtag.display}</strong>
                    </div>
                </div>
            `;
        });
    }

    searchResults.innerHTML = html;
    searchResultsBox.classList.add('active');
}

function clearSearch(event) {
    event.stopPropagation();
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    const searchResultsBox = document.getElementById('searchResultsBox');
    const clearBtn = document.getElementById('clearSearchBtn');
    
    searchInput.value = '';
    searchResults.innerHTML = '';
    searchResultsBox.classList.remove('active');
    clearBtn.classList.remove('visible');
    searchInput.focus();
}