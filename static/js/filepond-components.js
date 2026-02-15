const FilePondComponents = {
    // Initialize FilePond plugins
    initPlugins: function() {
        if (typeof FilePond === 'undefined') {
            console.error('FilePond library not loaded');
            return false;
        }

        FilePond.registerPlugin(
            FilePondPluginFileValidateType,
            FilePondPluginFileValidateSize,
            FilePondPluginImagePreview,
            FilePondPluginImageValidateSize,
            FilePondPluginImageCrop,
            FilePondPluginImageResize,
            FilePondPluginImageTransform,
            FilePondPluginImageEdit
        );
        return true;
    },

    // Profile Picture Upload (Square, 500x500)
    createProfilePicture: function(inputSelector, hiddenInputId) {
        const input = document.querySelector(inputSelector);
        if (!input) return null;

        return FilePond.create(input, {
            acceptedFileTypes: ['image/png', 'image/jpeg', 'image/webp'],
            maxFileSize: '5MB',
            imageCropAspectRatio: '1:1',
            imageResizeTargetWidth: 500,
            imageResizeTargetHeight: 500,
            imageTransformOutputQuality: 90,
            labelIdle: 'Drag & Drop your profile picture or <span class="filepond--label-action">Browse</span>',
            server: {
                process: {
                    url: '/upload/profile-picture',
                    method: 'POST',
                    onload: (response) => {
                        if (hiddenInputId) {
                            document.getElementById(hiddenInputId).value = response;
                        }
                        return response;
                    }
                }
            },
            credits: false
        });
    },

    // Post Image Upload (No crop, max 5MB)
    createPostImage: function(inputSelector, hiddenInputId) {
        const input = document.querySelector(inputSelector);
        if (!input) return null;

        return FilePond.create(input, {
            acceptedFileTypes: ['image/png', 'image/jpeg', 'image/webp'],
            maxFileSize: '5MB',
            labelIdle: 'Drag & Drop your image or <span class="filepond--label-action">Browse</span>',
            server: {
                process: {
                    url: '/upload/post-image',
                    method: 'POST',
                    onload: (response) => {
                        if (hiddenInputId) {
                            document.getElementById(hiddenInputId).value = response;
                        }
                        return response;
                    }
                }
            },
            credits: false
        });
    },

    // Forum Banner Upload (Wide aspect ratio, 1200x300 recommended)
    createForumBanner: function(inputSelector, hiddenInputId) {
        const input = document.querySelector(inputSelector);
        if (!input) return null;

        return FilePond.create(input, {
            acceptedFileTypes: ['image/png', 'image/jpeg', 'image/webp'],
            maxFileSize: '5MB',
            imageCropAspectRatio: '4:1',
            imageResizeTargetWidth: 1200,
            imageResizeTargetHeight: 300,
            imageTransformOutputQuality: 85,
            labelIdle: 'Drag & Drop banner image (1200x300 recommended) or <span class="filepond--label-action">Browse</span>',
            server: {
                process: {
                    url: '/upload/forum-banner',
                    method: 'POST',
                    onload: (response) => {
                        if (hiddenInputId) {
                            document.getElementById(hiddenInputId).value = response;
                        }
                        return response;
                    }
                }
            },
            credits: false
        });
    },

    // Destroy a FilePond instance
    destroy: function(pondInstance) {
        if (pondInstance) {
            pondInstance.destroy();
        }
    }
};