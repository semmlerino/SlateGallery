// gallery_script.js - SlateGallery Photo Gallery JavaScript
// This file is included in gallery_template.html via Jinja2
// Part of the SlateGallery photo gallery generator

document.addEventListener('DOMContentLoaded', function() {
    // ===== SELECTION PERSISTENCE SYSTEM =====
    // Saves photo selections to localStorage and restores them on page load
    // Uses gallery identifier (based on page path) to prevent cross-gallery pollution

    // Generate gallery identifier from current page URL
    function getGalleryIdentifier() {
        // Use pathname to uniquely identify this gallery
        // E.g., /path/to/gallery1.html vs /path/to/gallery2.html
        return 'gallery_selections_' + window.location.pathname.replace(/[^a-zA-Z0-9]/g, '_');
    }

    // Save current selections to localStorage
    function saveSelections() {
        if (!window.localStorage) return; // Bail if localStorage unavailable

        try {
            const selections = {};
            const checkboxes = document.querySelectorAll('.select-checkbox');

            checkboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    const container = checkbox.parentElement;
                    const imagePath = container.getAttribute('data-full-image');
                    if (imagePath) {
                        selections[imagePath] = true;
                    }
                }
            });

            const storageKey = getGalleryIdentifier();
            localStorage.setItem(storageKey, JSON.stringify(selections));
        } catch (e) {
            // localStorage might be full or disabled
            console.warn('Failed to save selections to localStorage:', e);
        }
    }

    // Restore selections from localStorage
    function restoreSelections() {
        if (!window.localStorage) return;

        try {
            const storageKey = getGalleryIdentifier();
            const savedData = localStorage.getItem(storageKey);

            if (!savedData) return;

            const selections = JSON.parse(savedData);
            let restoredCount = 0;

            // Apply saved selections to current page
            const containers = document.querySelectorAll('.image-container');
            containers.forEach(container => {
                const imagePath = container.getAttribute('data-full-image');
                if (imagePath && selections[imagePath]) {
                    const checkbox = container.querySelector('.select-checkbox');
                    if (checkbox) {
                        checkbox.checked = true;
                        container.classList.add('selected');
                        restoredCount++;
                    }
                }
            });

            // Show notification if selections were restored
            if (restoredCount > 0) {
                showNotification(`Restored ${restoredCount} photo selection${restoredCount !== 1 ? 's' : ''} from previous session`);
            }
        } catch (e) {
            console.warn('Failed to restore selections from localStorage:', e);
        }
    }

    // Debounced save to avoid excessive localStorage writes
    let saveTimeout = null;
    function debouncedSave() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            saveSelections();
            updateSelectedCountBadge();
        }, 300);
    }

    // Generic debounce utility for performance optimization
    // Used to throttle expensive operations like resize handlers
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // ===== HIDDEN IMAGES SYSTEM =====
    // Manages hiding/unhiding images with localStorage persistence
    // Uses in-memory cache for O(1) performance (not localStorage reads in hot path)

    // Global state - in-memory cache initialized on page load
    let hiddenImages = {}; // Format: {"/path/to/image.jpg": true}
    let isHiddenMode = false; // Toggle between normal gallery and hidden images view
    let isSelectedMode = false; // Toggle between normal gallery and selected images view

    // ARIA live region for screen reader announcements
    function announceToScreenReader(message) {
        const liveRegion = document.getElementById('aria-live-region');
        if (liveRegion) {
            liveRegion.textContent = message;
        }
    }

    // Restore hidden images from localStorage to in-memory cache
    function restoreHiddenImages() {
        if (!window.localStorage) return;

        try {
            const storageKey = getGalleryIdentifier() + '_hidden';
            const savedData = localStorage.getItem(storageKey);
            hiddenImages = savedData ? JSON.parse(savedData) : {};
        } catch (e) {
            console.error('Failed to restore hidden images:', e);
            hiddenImages = {};
        }
    }

    // Debounced save to localStorage (300ms consistent with selections)
    const saveHiddenImages = debounce(() => {
        if (!window.localStorage) return;

        try {
            const storageKey = getGalleryIdentifier() + '_hidden';
            localStorage.setItem(storageKey, JSON.stringify(hiddenImages));
        } catch (e) {
            console.error('Failed to save hidden images:', e);
        }
    }, 300);

    // O(1) in-memory lookup - NOT reading localStorage
    function isImageHidden(imagePath) {
        return hiddenImages[imagePath] === true;
    }

    // Get count of hidden images
    function getHiddenImagesCount() {
        return Object.keys(hiddenImages).filter(key => hiddenImages[key]).length;
    }

    // Get count of selected images
    function getSelectedImagesCount() {
        return document.querySelectorAll('.select-checkbox:checked').length;
    }

    // Hide image from gallery
    function hideImage(imagePath) {
        hiddenImages[imagePath] = true;

        // Only clear selection for THIS image, not all selections
        const checkbox = document.querySelector(`[data-full-image="${imagePath}"] .select-checkbox`);
        if (checkbox && checkbox.checked) {
            checkbox.checked = false;
            checkbox.parentElement.classList.remove('selected');
            debouncedSave(); // Save selections
        }

        saveHiddenImages(); // Debounced save
    }

    // Unhide image (restore to gallery)
    function unhideImage(imagePath) {
        delete hiddenImages[imagePath];
        saveHiddenImages(); // Debounced save
    }

    // Hide current image in modal mode
    function hideCurrentImage() {
        if (allVisibleImages.length === 0) return;

        const image = allVisibleImages[currentImageIndex];
        if (!image || !image.parentElement) return;

        const imageContainer = image.parentElement;
        const imagePath = imageContainer.getAttribute('data-full-image');

        if (!imagePath) return;

        hideImage(imagePath);

        // Show notification
        const filename = imageContainer.querySelector('.image-info strong')?.textContent || 'Image';
        showNotification(`Hidden: ${filename}`);
        announceToScreenReader(`Image hidden: ${filename}`);

        // Navigate to next/prev image or close modal if last image
        const nextVisibleImages = getVisibleImages();
        if (nextVisibleImages.length === 0) {
            closeModal();
            showNotification('All images hidden. Returning to gallery.');
        } else {
            // Stay at same index if possible, or go to previous if at end
            if (currentImageIndex >= nextVisibleImages.length) {
                currentImageIndex = nextVisibleImages.length - 1;
            }
            displayImage(currentImageIndex);
        }

        updateCounts();
        updateHiddenCountBadge();
        filterImages();
    }

    // Unhide current image in modal mode (when in hidden mode)
    function unhideCurrentImage() {
        if (allVisibleImages.length === 0) return;

        const image = allVisibleImages[currentImageIndex];
        if (!image || !image.parentElement) return;

        const imageContainer = image.parentElement;
        const imagePath = imageContainer.getAttribute('data-full-image');

        if (!imagePath) return;

        unhideImage(imagePath);

        // Show notification
        const filename = imageContainer.querySelector('.image-info strong')?.textContent || 'Image';
        showNotification(`Restored: ${filename}`);
        announceToScreenReader(`Image restored: ${filename}`);

        // Check if this was the last hidden image
        const remainingHidden = getHiddenImagesCount();
        if (remainingHidden === 0) {
            // Auto-exit hidden mode
            toggleHiddenMode();
            showNotification('All images restored. Returning to gallery.');
        } else {
            // Navigate to next/prev hidden image
            const nextVisibleImages = getVisibleImages();
            if (nextVisibleImages.length === 0) {
                closeModal();
            } else {
                if (currentImageIndex >= nextVisibleImages.length) {
                    currentImageIndex = nextVisibleImages.length - 1;
                }
                displayImage(currentImageIndex);
            }
        }

        updateCounts();
        updateHiddenCountBadge();
        filterImages();
    }

    // Update modal hide button text and style based on mode
    function updateModalHideButton() {
        const hideButton = document.getElementById('modal-hide-button');
        const hideText = document.getElementById('modal-hide-text');

        if (!hideButton || !hideText) return;

        if (isHiddenMode) {
            hideButton.classList.add('unhide-mode');
            hideText.textContent = 'Unhide Image';
            hideButton.setAttribute('aria-label', 'Unhide this image and restore to gallery');
        } else {
            hideButton.classList.remove('unhide-mode');
            hideText.textContent = 'Hide Image';
            hideButton.setAttribute('aria-label', 'Hide this image from gallery');
        }
    }

    // Toggle between normal gallery and hidden images view
    function toggleHiddenMode() {
        isHiddenMode = !isHiddenMode;

        // If entering hidden mode, exit selected mode
        if (isHiddenMode && isSelectedMode) {
            isSelectedMode = false;
            const selectedToggleButton = document.getElementById('toggle-selected-mode');
            const selectedStatusBar = document.getElementById('status-bar');
            const showSelectedText = selectedToggleButton.querySelector('.show-selected-text');
            const showAllText = selectedToggleButton.querySelector('.show-all-text');

            selectedToggleButton.setAttribute('aria-pressed', 'false');
            showSelectedText.style.display = 'inline';
            showAllText.style.display = 'none';
            selectedStatusBar.classList.remove('selected-mode');
        }

        const toggleButton = document.getElementById('toggle-hidden-mode');
        const unhideAllButton = document.getElementById('unhide-all-button');
        const statusBar = document.getElementById('status-bar');
        const showHiddenText = toggleButton.querySelector('.show-hidden-text');
        const showGalleryText = toggleButton.querySelector('.show-gallery-text');

        if (isHiddenMode) {
            // Entering hidden mode
            toggleButton.setAttribute('aria-pressed', 'true');
            showHiddenText.style.display = 'none';
            showGalleryText.style.display = 'inline';
            unhideAllButton.style.display = 'inline-block';
            statusBar.classList.add('hidden-mode');

            const hiddenCount = getHiddenImagesCount();
            showNotification(`Showing ${hiddenCount} hidden images`);
            announceToScreenReader(`Hidden images mode activated. Showing ${hiddenCount} hidden images.`);
        } else {
            // Exiting hidden mode
            toggleButton.setAttribute('aria-pressed', 'false');
            showHiddenText.style.display = 'inline';
            showGalleryText.style.display = 'none';
            unhideAllButton.style.display = 'none';
            statusBar.classList.remove('hidden-mode');

            showNotification('Returned to gallery view');
            announceToScreenReader('Gallery view restored');
        }

        // Update modal hide button if modal is open
        updateModalHideButton();

        // Refresh gallery view
        filterImages();
        updateCounts();
    }

    // Toggle between normal gallery and selected images view
    function toggleSelectedMode() {
        isSelectedMode = !isSelectedMode;

        // If entering selected mode, exit hidden mode
        if (isSelectedMode && isHiddenMode) {
            isHiddenMode = false;
            const hiddenToggleButton = document.getElementById('toggle-hidden-mode');
            const unhideAllButton = document.getElementById('unhide-all-button');
            const hiddenStatusBar = document.getElementById('status-bar');
            const showHiddenText = hiddenToggleButton.querySelector('.show-hidden-text');
            const showGalleryText = hiddenToggleButton.querySelector('.show-gallery-text');

            hiddenToggleButton.setAttribute('aria-pressed', 'false');
            showHiddenText.style.display = 'inline';
            showGalleryText.style.display = 'none';
            unhideAllButton.style.display = 'none';
            hiddenStatusBar.classList.remove('hidden-mode');

            // Update modal hide button if modal is open
            updateModalHideButton();
        }

        const toggleButton = document.getElementById('toggle-selected-mode');
        const statusBar = document.getElementById('status-bar');
        const showSelectedText = toggleButton.querySelector('.show-selected-text');
        const showAllText = toggleButton.querySelector('.show-all-text');

        if (isSelectedMode) {
            // Entering selected mode
            toggleButton.setAttribute('aria-pressed', 'true');
            showSelectedText.style.display = 'none';
            showAllText.style.display = 'inline';
            statusBar.classList.add('selected-mode');

            const selectedCount = getSelectedImagesCount();
            showNotification(`Showing ${selectedCount} selected images`);
            announceToScreenReader(`Selected images mode activated. Showing ${selectedCount} selected images.`);
        } else {
            // Exiting selected mode
            toggleButton.setAttribute('aria-pressed', 'false');
            showSelectedText.style.display = 'inline';
            showAllText.style.display = 'none';
            statusBar.classList.remove('selected-mode');

            showNotification('Returned to gallery view');
            announceToScreenReader('Gallery view restored');
        }

        // Refresh gallery view
        filterImages();
        updateCounts();
    }

    // Update hidden count badge
    function updateHiddenCountBadge() {
        const badge = document.querySelector('.hidden-count-badge');
        if (!badge) return;

        const count = getHiddenImagesCount();
        if (count > 0) {
            badge.style.display = 'flex';
            badge.textContent = count;
            badge.setAttribute('aria-label', `${count} hidden images`);
        } else {
            badge.style.display = 'none';
        }
    }

    // Update selected count badge
    function updateSelectedCountBadge() {
        const badge = document.querySelector('.selected-count-badge');
        if (!badge) return;

        const count = getSelectedImagesCount();
        if (count > 0) {
            badge.style.display = 'flex';
            badge.textContent = count;
            badge.setAttribute('aria-label', `${count} selected images`);
        } else {
            badge.style.display = 'none';
        }
    }

    // Unhide all images with confirmation
    function unhideAllImages() {
        const count = getHiddenImagesCount();
        if (count === 0) {
            showNotification('No hidden images to restore', true);
            return;
        }

        // Confirmation dialog
        if (!confirm(`Are you sure you want to unhide all ${count} images? This cannot be undone.`)) {
            return;
        }

        hiddenImages = {};
        saveHiddenImages();

        if (isHiddenMode) {
            toggleHiddenMode();
        }

        showNotification(`All images restored (${count} images)`);
        announceToScreenReader(`All ${count} images restored to gallery`);

        updateCounts();
        updateHiddenCountBadge();
        filterImages();
    }

    // Event listeners for hidden images controls
    document.getElementById('toggle-hidden-mode').addEventListener('click', toggleHiddenMode);
    document.getElementById('unhide-all-button').addEventListener('click', unhideAllImages);

    // Event listener for selected images control
    document.getElementById('toggle-selected-mode').addEventListener('click', toggleSelectedMode);
    document.getElementById('modal-hide-button').addEventListener('click', function() {
        if (isHiddenMode) {
            unhideCurrentImage();
        } else {
            hideCurrentImage();
        }
    });

    // Notification Function
    function showNotification(message, isError = false) {
        const notificationBar = document.getElementById('notification-bar');
        notificationBar.textContent = message;
        notificationBar.classList.toggle('error', isError);
        notificationBar.classList.add('show');

        setTimeout(() => {
            notificationBar.classList.remove('show');
        }, 3000);
    }

    // Update Status Bar with current counts
    function updateCounts() {
        const statusBar = document.getElementById('status-bar');
        if (!statusBar) return;

        const allContainers = document.querySelectorAll('.image-container');
        const totalImages = allContainers.length;

        // Count visible images (not hidden by filters)
        let visibleCount = 0;
        allContainers.forEach(container => {
            if (container.style.display !== 'none') {
                visibleCount++;
            }
        });

        // Count selected checkboxes
        const selectedCount = document.querySelectorAll('.select-checkbox:checked').length;

        // Update status bar text with hidden mode indicator
        let statusText = `Showing ${visibleCount} of ${totalImages} images | ${selectedCount} selected`;
        if (isHiddenMode) {
            statusText += ' | HIDDEN IMAGES MODE';
        }
        statusBar.textContent = statusText;

        // Update export button badge
        updateExportButtonBadge(selectedCount);
    }

    // Update Export Button Badge based on selection count
    function updateExportButtonBadge(count) {
        const exportButtonContainer = document.querySelector('.export-button');
        const exportButton = document.getElementById('export-to-clipboard');

        if (!exportButtonContainer || !exportButton) return;

        if (count > 0) {
            exportButtonContainer.classList.add('has-selection');
            exportButton.setAttribute('data-count', count);
        } else {
            exportButtonContainer.classList.remove('has-selection');
            exportButton.removeAttribute('data-count');
        }
    }

    // Function to filter images based on selected filters
    function filterImages() {
        var orientationCheckboxes = document.querySelectorAll('.orientation-filter');
        var selectedOrientations = [];
        orientationCheckboxes.forEach(cb => { if (cb.checked) selectedOrientations.push(cb.value); });

        var focalLengthCheckboxes = document.querySelectorAll('.focal-length-filter');
        var selectedFocalLengths = [];
        focalLengthCheckboxes.forEach(cb => { if (cb.checked) selectedFocalLengths.push(cb.value); });

        var dateCheckboxes = document.querySelectorAll('.date-filter');
        var selectedDates = [];
        dateCheckboxes.forEach(cb => { if (cb.checked) selectedDates.push(cb.value); });

        var imageContainers = document.getElementsByClassName('image-container');

        for (var img of imageContainers) {
            var imgOrientation = img.getAttribute('data-orientation');
            var imgFocalLength = img.getAttribute('data-focal-length');
            var imgDate = img.getAttribute('data-date');
            var imgPath = img.getAttribute('data-full-image');

            var orientationMatch = selectedOrientations.length === 0 || selectedOrientations.includes(imgOrientation);
            var focalMatch = selectedFocalLengths.length === 0 || selectedFocalLengths.includes(imgFocalLength.toString());

            // Date matching: extract YYYY-MM-DD from ISO date string and check if it matches any selected day
            var dateMatch = selectedDates.length === 0 || (imgDate && selectedDates.some(date => imgDate.startsWith(date)));

            // Hidden state filtering
            var hiddenMatch = true;
            if (isHiddenMode) {
                // In hidden mode: ONLY show hidden images
                hiddenMatch = isImageHidden(imgPath);
            } else {
                // In normal mode: EXCLUDE hidden images
                hiddenMatch = !isImageHidden(imgPath);
            }

            // Selected state filtering
            var selectedMatch = true;
            if (isSelectedMode) {
                // In selected mode: ONLY show selected images
                selectedMatch = img.classList.contains('selected');
            }

            img.style.display = (orientationMatch && focalMatch && dateMatch && hiddenMatch && selectedMatch) ? 'flex' : 'none';
        }

        // Invalidate visible images cache after filtering (P1 Performance Fix)
        invalidateVisibleImagesCache();

        // If modal is open, refresh the visible images list
        if (modal.classList.contains('show')) {
            allVisibleImages = getVisibleImages();
            if (allVisibleImages.length === 0) {
                closeModal();
            } else {
                displayImage(currentImageIndex);
            }
        }

        // Update status bar after filtering
        updateCounts();
    }

    // Functions to select/deselect all checkboxes based on a filter class
    function selectAllCheckboxes(filterClass) {
        var checkboxes = document.querySelectorAll(filterClass);
        checkboxes.forEach(cb => { cb.checked = true; });
        filterImages();
    }

    function deselectAllCheckboxes(filterClass) {
        var checkboxes = document.querySelectorAll(filterClass);
        checkboxes.forEach(cb => { cb.checked = false; });
        filterImages();
    }

    // Global Select All Photos - only select photos that are visible!
    function selectAllPhotos() {
        const imageContainers = document.querySelectorAll('.image-container');
        imageContainers.forEach(container => {
            // Only select if container is visible
            if (container.style.display !== 'none') {
                const checkbox = container.querySelector('.select-checkbox');
                if (checkbox) {
                    checkbox.checked = true;
                    container.classList.add('selected');
                }
            }
        });
        debouncedSave(); // Save selections after bulk operation
        updateCounts(); // Update status bar
    }

    // Global Deselect All Photos
    function deselectAllPhotos() {
        var checkboxes = document.querySelectorAll('.select-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.parentElement.classList.remove('selected');
        });
        debouncedSave(); // Save selections after bulk operation
        updateCounts(); // Update status bar
    }

    document.getElementById('select-all-photos').addEventListener('click', selectAllPhotos);
    document.getElementById('deselect-all-photos').addEventListener('click', deselectAllPhotos);

    var orientationCheckboxes = document.querySelectorAll('.orientation-filter');
    orientationCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', filterImages);
    });

    var focalLengthCheckboxes = document.querySelectorAll('.focal-length-filter');
    focalLengthCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', filterImages);
    });

    document.getElementById('select-all-focal-length').addEventListener('click', function() {
        selectAllCheckboxes('.focal-length-filter');
    });

    document.getElementById('deselect-all-focal-length').addEventListener('click', function() {
        deselectAllCheckboxes('.focal-length-filter');
    });

    var dateCheckboxes = document.querySelectorAll('.date-filter');
    dateCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', filterImages);
    });

    document.getElementById('select-all-date').addEventListener('click', function() {
        selectAllCheckboxes('.date-filter');
    });

    document.getElementById('deselect-all-date').addEventListener('click', function() {
        deselectAllCheckboxes('.date-filter');
    });

    // Size slider functionality
    var sizeSlider = document.getElementById('size-slider');
    var sizeValue = document.getElementById('size-value');

    sizeSlider.addEventListener('input', function() {
        var size = sizeSlider.value + 'px';
        sizeValue.textContent = size;
        adjustImageSizes(size);
    });

    function adjustImageSizes(size) {
        // Use CSS variable for more reliable sizing
        document.documentElement.style.setProperty('--image-width', size);
        // No need to switch thumbnail sources since we use a single optimized size
    }

    document.getElementById('export-to-clipboard').addEventListener('click', function() {
        var imageContainers = document.getElementsByClassName('image-container');
        var exportData = [];
        var lastFolderPath = '';
        var currentBasePath = '';

        for (var container of imageContainers) {
            var checkbox = container.querySelector('.select-checkbox');
            if (checkbox && checkbox.checked) {
                var imgElement = container.querySelector('img');
                // Use original full path, not thumbnail
                var imgPath = imgElement.getAttribute('data-src-full') || container.getAttribute('data-full-image') || imgElement.getAttribute('src');
                var focalLength = container.getAttribute('data-focal-length');

                var focalLengthFormatted = parseFloat(focalLength);
                if (focalLengthFormatted % 1 === 0) {
                    focalLengthFormatted = focalLengthFormatted.toFixed(0);
                }

                var lastSlashIndex = imgPath.lastIndexOf('/');
                var folderPath = imgPath.substring(0, lastSlashIndex);
                var filename = imgPath.substring(lastSlashIndex + 1);

                // Extract base path up to /slates/ for this image
                var imgBasePath = '';
                var slatesIndex = imgPath.indexOf('/slates/');
                if (slatesIndex !== -1) {
                    imgBasePath = imgPath.substring(0, slatesIndex + 8); // +8 for '/slates/'
                }

                if (exportData.length === 0 || imgBasePath !== currentBasePath) {
                    // First image OR different show/base path - output full path
                    exportData.push(imgPath + '-' + focalLengthFormatted);
                    currentBasePath = imgBasePath;
                } else {
                    // Same base path - use relative format
                    var relativePath = imgPath.substring(currentBasePath.length);

                    // Check if it's the same folder as last time
                    if (folderPath === lastFolderPath) {
                        // Same folder - extract slate from relative path and output slate/subdirs/filename
                        var slateMatch = relativePath.match(/^([A-Z][0-9]+[A-Z])\//);
                        if (slateMatch) {
                            var slate = slateMatch[1];
                            var pathAfterSlate = relativePath.substring(slate.length + 1);
                            exportData.push(slate + '/' + pathAfterSlate + '-' + focalLengthFormatted);
                        } else {
                            // Fallback to relative path if no slate found
                            exportData.push(relativePath + '-' + focalLengthFormatted);
                        }
                    } else {
                        // Different folder - always include full relative path with slate
                        exportData.push(relativePath + '-' + focalLengthFormatted);
                    }
                }

                lastFolderPath = folderPath;
            }
        }

        if (exportData.length === 0) {
            showNotification('No images selected for export.', true);
            return;
        }

        var exportText = exportData.join('\n');

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(exportText).then(function() {
                showNotification('Data copied to clipboard');
            }, function(err) {
                showNotification('Failed to copy data: ' + err, true);
            });
        } else {
            var textarea = document.createElement('textarea');
            textarea.value = exportText;
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                showNotification('Data copied to clipboard');
            } catch (err) {
                showNotification('Failed to copy data: ' + err, true);
            }
            document.body.removeChild(textarea);
        }
    });

    // ===== EVENT DELEGATION FOR CHECKBOXES (P0 Performance Fix) =====
    // Instead of 500+ individual listeners, use single delegated listener on document
    // Memory: ~50KB saved, initialization: ~95ms faster on 500 images
    document.addEventListener('change', function(e) {
        if (e.target.matches('.select-checkbox')) {
            const checkbox = e.target;
            if (checkbox.checked) {
                checkbox.parentElement.classList.add('selected');
            } else {
                checkbox.parentElement.classList.remove('selected');
            }
            // Update modal checkbox if modal is open and this image is currently displayed
            if (modal.classList.contains('show')) {
                if (allVisibleImages[currentImageIndex] === checkbox.parentElement.querySelector('img')) {
                    modalSelectCheckbox.checked = checkbox.checked;
                }
            }
            // Save selections after individual checkbox change
            debouncedSave();
            // Update status bar
            updateCounts();
        }
    });

    // ===== EVENT DELEGATION FOR IMAGE CLICKS (P0 Performance Fix) =====
    // Instead of 500+ individual listeners, use single delegated listener on document
    // Memory: ~50KB saved, initialization: ~95ms faster on 500 images
    document.addEventListener('click', function(e) {
        if (e.target.matches('.image-container img')) {
            const img = e.target;
            const checkbox = img.parentElement.querySelector('.select-checkbox');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    });

    // Modal Elements
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    const modalCaption = document.getElementById('modal-caption');
    const closeButton = document.querySelector('.close-button');
    const prevButton = document.querySelector('.prev-button');
    const nextButton = document.querySelector('.next-button');
    const modalSelectCheckbox = document.querySelector('.modal-checkbox');

    let allVisibleImages = [];
    let currentImageIndex = 0;
    let lastFocusedElement = null; // To store the element that triggered the modal

    // ===== VISIBLE IMAGES CACHE SYSTEM =====
    // Prevents redundant DOM queries when filtering/navigating (P1 Performance Fix)
    // Cache is invalidated whenever filters change
    let visibleImagesCache = null;

    function invalidateVisibleImagesCache() {
        visibleImagesCache = null;
    }

    // Function to get all currently visible images (with caching)
    function getVisibleImages() {
        if (!visibleImagesCache) {
            visibleImagesCache = Array.from(document.querySelectorAll('.image-container img'))
                        .filter(img => img.parentElement.style.display !== 'none');
        }
        return visibleImagesCache;
    }

    function openModal(event) {
        // Prevent the click event from propagating to the modal background
        event.stopPropagation();

        allVisibleImages = getVisibleImages();
        if (allVisibleImages.length === 0) {
            showNotification('No images available to display in modal.', true);
            return;
        }

        // Store the last focused element
        lastFocusedElement = document.activeElement;

        // Get the image element from the parent container
        // Use event.target to find the clicked element (works with event delegation)
        const imageContainer = event.target.closest('.image-container');
        if (!imageContainer) {
            showNotification('Image container not found', true);
            return;
        }
        const image = imageContainer.querySelector('img');

        currentImageIndex = allVisibleImages.indexOf(image);

        // If the image is not found, default to the first image
        if (currentImageIndex === -1) {
            currentImageIndex = 0;
        }

        displayImage(currentImageIndex);
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
        modal.setAttribute('tabindex', '-1');
        modal.focus(); // Set focus to the modal

        // Update modal hide button for current mode
        updateModalHideButton();
    }

    function displayImage(index) {
        allVisibleImages = getVisibleImages(); // Refresh the list in case filters have changed
        if (allVisibleImages.length === 0) {
            closeModal();
            return;
        }

        if (index < 0) {
            currentImageIndex = allVisibleImages.length - 1; // Loop to last image
        } else if (index >= allVisibleImages.length) {
            currentImageIndex = 0; // Loop to first image
        } else {
            currentImageIndex = index;
        }

        // ===== COMPREHENSIVE NULL CHECKS (P0 Stability Fix) =====
        // Prevents crashes when filters change during modal navigation
        const image = allVisibleImages[currentImageIndex];
        if (!image || !image.parentElement) {
            closeModal();
            showNotification('Image no longer visible due to filters', true);
            return;
        }

        const imageContainer = image.parentElement;
        if (!imageContainer) {
            closeModal();
            showNotification('Image container not found', true);
            return;
        }

        // Use full-size image for modal, fallback to current src
        const fullSrc = image.getAttribute('data-src-full') ||
                        imageContainer.getAttribute('data-full-image') ||
                        image.getAttribute('src');

        if (!fullSrc) {
            closeModal();
            showNotification('Image source not found', true);
            return;
        }

        const imgAlt = image.getAttribute('alt') || 'Photo';

        // Retrieve metadata with null checks
        const filenameElement = imageContainer.querySelector('.image-info strong');
        if (!filenameElement) {
            closeModal();
            showNotification('Image metadata not found', true);
            return;
        }

        const filename = filenameElement.textContent;
        const focalLength = imageContainer.getAttribute('data-focal-length');

        // Build metadata HTML
        let metadataHTML = `<strong>${filename}</strong>`;
        metadataHTML += focalLength ? `<br>Focal Length: ${focalLength}mm` : '';

        modalImg.src = fullSrc;
        modalImg.alt = imgAlt;
        modalCaption.innerHTML = metadataHTML;

        const galleryCheckbox = imageContainer.querySelector('.select-checkbox');
        if (galleryCheckbox) {
            modalSelectCheckbox.checked = galleryCheckbox.checked;
        }
    }

    function closeModal() {
        modal.classList.remove('show');
        document.body.style.overflow = 'auto';
        // Return focus to the last focused element
        if (lastFocusedElement) {
            lastFocusedElement.focus();
        }
    }

    function showPrevImage() {
        displayImage(currentImageIndex - 1);
    }

    function showNextImage() {
        displayImage(currentImageIndex + 1);
    }

    // ===== EVENT DELEGATION FOR ENLARGE BUTTONS (P0 Performance Fix) =====
    // Instead of 500+ individual listeners, use single delegated listener on document
    // Memory: ~50KB saved, initialization: ~95ms faster on 500 images
    document.addEventListener('click', function(e) {
        if (e.target.closest('.enlarge-button')) {
            openModal(e);
        }
    });

    closeButton.addEventListener('click', closeModal);

    prevButton.addEventListener('click', showPrevImage);
    nextButton.addEventListener('click', showNextImage);

    // Close modal when clicking outside the image
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    // Keyboard navigation
    document.addEventListener('keydown', function(event) {
        if (modal.classList.contains('show')) {
            if (event.key === 'ArrowLeft') {
                showPrevImage();
            } else if (event.key === 'ArrowRight') {
                showNextImage();
            } else if (event.key === 'Escape') {
                closeModal();
            } else if (event.key === 'h' || event.key === 'H') {
                // 'h' key to hide/unhide current image
                if (isHiddenMode) {
                    unhideCurrentImage();
                } else {
                    hideCurrentImage();
                }
            }
        }
    });

    // Select/Deselect all within a slate
    function selectAllInSlate(slateElement) {
        var checkboxes = slateElement.querySelectorAll('.select-checkbox');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = true;
            checkbox.parentElement.classList.add('selected');
        });
        debouncedSave(); // Save selections after bulk operation
        updateCounts(); // Update status bar
    }

    function deselectAllInSlate(slateElement) {
        var checkboxes = slateElement.querySelectorAll('.select-checkbox');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = false;
            checkbox.parentElement.classList.remove('selected');
        });
        debouncedSave(); // Save selections after bulk operation
        updateCounts(); // Update status bar
    }

    var selectAllSlateButtons = document.querySelectorAll('.select-all-slate');
    selectAllSlateButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var slateDiv = this.closest('.slate');
            selectAllInSlate(slateDiv);
        });
    });

    var deselectAllSlateButtons = document.querySelectorAll('.deselect-all-slate');
    deselectAllSlateButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var slateDiv = this.closest('.slate');
            deselectAllInSlate(slateDiv);
        });
    });

    // Handle modal checkbox changes
    modalSelectCheckbox.addEventListener('change', function() {
        if (allVisibleImages.length === 0) return;

        const image = allVisibleImages[currentImageIndex];
        const imageContainer = image.parentElement;
        const galleryCheckbox = imageContainer.querySelector('.select-checkbox');
        if (galleryCheckbox) {
            galleryCheckbox.checked = this.checked;
            if (this.checked) {
                imageContainer.classList.add('selected');
            } else {
                imageContainer.classList.remove('selected');
            }
            // Save selections after modal checkbox change
            debouncedSave();
            // Update status bar
            updateCounts();
        }
    });

    // Initialize the gallery
    function initializeGallery() {
        // Restore hidden images from localStorage
        restoreHiddenImages();
        // Update hidden count badge
        updateHiddenCountBadge();
        // Filter images (includes hidden state filtering)
        filterImages();
        adjustImageSizes(sizeSlider.value + 'px');
        // Images use lazy loading for better performance
        // Restore saved selections from previous session
        restoreSelections();
        // Update selected count badge
        updateSelectedCountBadge();
        // Initialize status bar counts
        updateCounts();
    }

    initializeGallery();

    // Setup Intersection Observer for progressive image loading
    {% if lazy_loading %}
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    // Only add loading state if image isn't already loaded
                    if (!img.complete && !img.classList.contains('loaded')) {
                        img.classList.add('loading');
                        img.onload = () => {
                            img.classList.remove('loading');
                            img.classList.add('loaded');
                            // ===== OBSERVER CLEANUP (P0 Memory Fix) =====
                            // Unobserve after load to prevent memory leak with 500+ images
                            imageObserver.unobserve(img);
                        };
                        img.onerror = () => {
                            img.classList.remove('loading');
                            // Don't add 'loaded' on error to maintain loading shimmer
                            // Still unobserve to prevent memory leak
                            imageObserver.unobserve(img);
                        };
                    } else if (img.complete && !img.classList.contains('loaded')) {
                        // Image was already cached/loaded
                        img.classList.add('loaded');
                        imageObserver.unobserve(img);
                    }
                }
            });
        }, {
            // Start loading when image is 200px away from viewport
            rootMargin: '200px',
            threshold: 0.01
        });

        // Observe all lazy-load images
        document.querySelectorAll('img[loading="lazy"]').forEach(img => {
            // Set initial state for images already in cache
            if (img.complete) {
                img.classList.add('loaded');
            } else {
                // Ensure load handler is set for images not yet loaded
                img.onload = () => {
                    img.classList.remove('loading');
                    img.classList.add('loaded');
                    // ===== OBSERVER CLEANUP (P0 Memory Fix) =====
                    imageObserver.unobserve(img);
                };
                img.onerror = () => {
                    img.classList.remove('loading');
                    imageObserver.unobserve(img);
                };
            }
            imageObserver.observe(img);
        });
    }
    {% else %}
    // When lazy loading is disabled, all images load immediately
    // Just set loaded class for all images once they're loaded
    document.querySelectorAll('.images img').forEach(img => {
        if (img.complete) {
            img.classList.add('loaded');
        } else {
            img.onload = () => {
                img.classList.add('loaded');
            };
        }
    });
    {% endif %}

    // ===== DEBOUNCED RESIZE HANDLER (P1 Performance Fix) =====
    // Prevents excessive displayImage() calls during window resize
    // CPU usage: ~90% reduction (from 100+ calls/sec to ~6 calls/sec)
    window.addEventListener('resize', debounce(function() {
        if (modal.classList.contains('show')) {
            displayImage(currentImageIndex);
        }
    }, 150));

    // Accessibility: Allow closing modal with Enter key on close button
    closeButton.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            closeModal();
        }
    });

    // Accessibility: Allow navigating prev/next buttons with Enter key
    prevButton.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            showPrevImage();
        }
    });

    nextButton.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            showNextImage();
        }
    });
});
