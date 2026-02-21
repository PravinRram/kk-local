// Initialize FilePond plugins once
FilePondComponents.initPlugins();

// Use FilePond component for post image
if (!document.querySelector('.filepond-post').classList.contains('filepond--hopper')) {
    window.imagePostPond = FilePondComponents.createPostImage('.filepond-post', 'postImageUrl');
}

// Socket.IO for real-time updates
const socket = io();
    socket.on('connect', function() {
        socket.emit('join_feed', {});
    });

    socket.on('post_update', function(data) {
        const newPostsBtn = document.getElementById('newPostsBtn');
        if (newPostsBtn) {
            newPostsBtn.style.display = 'block';
        }
    });

// Join personal room for notifications
const currentUserId = document.body.dataset.userId;
if (currentUserId) {
    socket.emit('join_user_room', { user_id: currentUserId });
}

// Show notification badge update on new notification
socket.on('new_notification', function(data) {
    const badge = document.querySelector('.notification-badge, .nav-badge');
    if (badge) {
        const current = parseInt(badge.textContent) || 0;
        badge.textContent = current + 1;
        badge.style.display = 'inline';
    }
});