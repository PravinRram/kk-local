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