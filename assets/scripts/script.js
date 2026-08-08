const projectHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--project-title-height"));

// Convert a glob pattern ('*', '?') into a RegExp
function globToRegExp(pattern) {
    const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&');
    const regex = escaped.replace(/\*/g, '.*').replace(/\?/g, '.');
    return new RegExp(`^${regex}$`);
}

// Resolve a project's image paths against the manifest list.
// Glob patterns ('*', '?') are expanded to every matching file, and literal
// basenames without a folder are resolved to their full relative path.
function expandProjectImages(project, availableFiles) {
    const expanded = [];
    for (const image of project.images) {
        const pattern = image.image_path;
        const hasGlob = pattern.includes('*') || pattern.includes('?');
        if (hasGlob) {
            // match the full relative path, or the basename when the pattern has no folder
            const regex = globToRegExp(pattern);
            const matches = availableFiles.filter(file =>
                regex.test(file) || regex.test(file.split('/').pop())
            );
            matches.forEach(file => expanded.push({ image_path: file }));
            continue;
        }
        if (availableFiles.includes(pattern)) {
            expanded.push(image);
            continue;
        }
        // literal basename without a folder: use the matching file if unique
        const basename = pattern.split('/').pop();
        const matches = availableFiles.filter(file => file.split('/').pop() === basename);
        if (pattern === basename && matches.length === 1) {
            expanded.push({ image_path: matches[0] });
            continue;
        }
        expanded.push(image);
    }
    return expanded;
}


// script.js
document.addEventListener('DOMContentLoaded', () => {

    const mainDisplay = document.getElementById('main-display');
    const imageContainer = document.getElementById('image-container');
    const galleryContainer = document.getElementById('gallery-container'); 
    const projectGallery = document.getElementById('project-gallery');   

    // Load photo data
    // also fetch the manifest of available images to expand '*' glob patterns
    Promise.all([
        fetch('galleries/main.json')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            }),
        fetch('assets/photos/manifest.json')
            .then(response => response.ok ? response.json() : [])
            .catch(() => [])
    ])
        .then(([projects, availableFiles]) => {
            if (!projects || !Array.isArray(projects)) {
                throw new Error('Invalid projects data');
            }
            // Expand any '*' glob patterns in image paths before rendering
            projects = projects.map(project => ({ ...project, images: expandProjectImages(project, availableFiles) }));
            initGallery(projects);
        })
        .catch(error => {
            console.error('Error loading projects:', error);
            displayError();
        });
    
    function initGallery(projects) {
	    console.log('Project height:', projectHeight);

        // index to track image indices for each project
        const imageIndices = {};


        // Add project titles to gallery
        projects.forEach((project, index) => {

            const projectContainer = document.createElement('div');
            projectContainer.classList.add('project-container');

            const projectTitle = document.createElement('div');
            projectTitle.classList.add('project-title');
            projectTitle.textContent = project['project-title'];
            
            if (index === 0) {
                projectTitle.classList.add('active');
            }

            const additionalInfos = document.createElement("div");
            additionalInfos.classList.add("additional-infos")

            // Add location if present
            if (project.location) {
                const locationElem = document.createElement('span');
                locationElem.classList.add('project-location');
                locationElem.textContent = project.location;
                additionalInfos.appendChild(locationElem);
            }
            // Add year if present
            if (project.year) {
                const yearElem = document.createElement('span');
                yearElem.classList.add('project-year');
                yearElem.textContent = project.year;
                additionalInfos.appendChild(yearElem);
            }

            imageIndices[index] = 0;

            // handle click event to select project
            projectTitle.addEventListener('click', projectTitleFunction);
            //projectTitle.addEventListener('touchend', projectTitleFunction);

            function projectTitleFunction(){
                projectTransition(index);
            }

            // Append projectTitle after year and location
            projectContainer.appendChild(projectTitle);
            projectContainer.appendChild(additionalInfos)

            projectGallery.appendChild(projectContainer);
        });
        
        // Set up scrolling
        let currentPosition = 0;
        let project_index = 0;
        //let scrollTimeout = null;
        const totalProjects = projects.length;

        function projectTransition(newIndex){
            currentPosition = newIndex * projectHeight;
            projectTransitionAnimation(currentPosition, newIndex);
        }

        function projectTransitionAnimation(position, newIndex){
            projectGallery.style.transition = 'transform 0.12s ease-out';
            projectGallery.style.transform = `translateY(${-position}px)`;
            if (newIndex !== project_index) {
                project_index = newIndex;
                //navigator.vibrate(50); // Optional: Add a vibration effect on project change
                updateProject();
            }
        }

        // Horizontal swipe on the featured image (touch)
        // Bound once, so it always targets the current project via imageNav hooks.
        // Declared before updateProject() so the hooks can be assigned there.
        let imageNavNext = null;
        let imageNavPrev = null;
        let touchStartX = 0;
        let touchStartY2 = 0;
        let isImageTouch = false;

        mainDisplay.addEventListener('touchstart', (e) => {
            if (e.touches.length > 0) {
                touchStartX = e.touches[0].clientX;
                touchStartY2 = e.touches[0].clientY;
                isImageTouch = true;
            }
        }, { passive: true });

        mainDisplay.addEventListener('touchend', (e) => {
            if (!isImageTouch) return;
            isImageTouch = false;
            const dx = e.changedTouches[0].clientX - touchStartX;
            const dy = e.changedTouches[0].clientY - touchStartY2;
            const threshold = 50; // px
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > threshold) {
                if (dx < 0) {
                    imageNavNext && imageNavNext(); // swipe left -> next
                } else {
                    imageNavPrev && imageNavPrev(); // swipe right -> prev
                }
            }
        });

        // Initialize the first project
        updateProject();

        const minSwipeDistance = 0; // Minimum distance to consider a swipe

        // or galleryWrapper
        // Add these variables to track touch state
        let touchStartY = 0;
        let isTouchActive = false;
        const scrollSpeed = 0.075; // Adjust this for scroll sensitivity
        const mobileScrollMultiplier = 1; // Adjust this for mobile scroll sensitivity

        // Wheel event (desktop)
        galleryContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            handleScroll(e.deltaY);
        });

        // Touch events (mobile)
        galleryContainer.addEventListener('touchstart', (e) => {
            if (e.touches.length > 0) {
                touchStartY = e.touches[0].clientY;
                isTouchActive = true;
            }
        });

        galleryContainer.addEventListener('touchmove', (e) => {
            if (!isTouchActive) return;
            e.preventDefault();
            
            const touchY = e.touches[0].clientY;
            const deltaY = touchStartY - touchY; // Inverted for natural scroll direction
            touchStartY = touchY;
            
            handleScroll(deltaY * mobileScrollMultiplier);
        }, { passive: false });

        galleryContainer.addEventListener('touchend', () => {
            isTouchActive = false;
        });

        galleryContainer.addEventListener('touchcancel', () => {
            isTouchActive = false;
        });

        // Unified scroll handler
        function handleScroll(deltaY) {

            const additionalSpace = projectHeight / 2; // Additional space to scroll past the last project

            const maxPosition = (totalProjects - 1) * projectHeight + additionalSpace;
            const minPosition = -additionalSpace;
            const direction = deltaY > 0 ? 1 : -1;
            
            // Update position with boundaries
            currentPosition = Math.min(
                maxPosition,
                Math.max(minPosition, currentPosition + direction * projectHeight * scrollSpeed)
            );
            
            // Calculate nearest project index
            const minIndex = 0;
            const maxIndex = totalProjects - 1;
            const newIndex = Math.min(
                Math.max(Math.round(currentPosition / projectHeight), minIndex), 
                maxIndex
            );
            
            // Apply transform
            projectTransitionAnimation(currentPosition, newIndex);
        }
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowUp') {
                if (project_index > 0) {
                    newIndex = project_index - 1;
                    projectTransition(newIndex);
                }
            } else if (e.key === 'ArrowDown') {
                if (project_index < totalProjects - 1) {
                    newIndex = project_index + 1;
                    projectTransition(newIndex);
                }
            }
        });

        // About button logic
        const backBtn = document.getElementById('back');
        const aboutBtn = document.getElementById('about');
        const aboutText = document.getElementById('about-text');
        const nameElem = document.getElementById('name');
        const cursorLine = document.getElementById('cursor-line');
        const navigation = document.querySelector('.navigation');
        const photoInfo = document.getElementById('photo-info');

        const normalModeElements = [projectGallery, mainDisplay, cursorLine, nameElem, aboutBtn, imageContainer, navigation, photoInfo];
        const aboutModeElements = [aboutText, backBtn];

        aboutBtn.addEventListener('click', aboutBtnFunction);
        //aboutBtn.addEventListener('touchend', aboutBtnFunction);

        function aboutBtnFunction() {
            // Expand gallery-container
            galleryContainer.classList.add('about-active');
            mainDisplay.classList.add('about-active');

            normalModeElements.forEach(elem => {
                if (elem) elem.classList.add('hidden');
            });
            aboutModeElements.forEach(elem => {
                if (elem) elem.classList.remove('hidden');
            });

        }

        backBtn.addEventListener('click', backBtnFunction);
        //backBtn.addEventListener('touchend', backBtnFunction);

        function backBtnFunction() {
            // Restore gallery-container
            galleryContainer.classList.remove('about-active');
            mainDisplay.classList.remove('about-active');
            
            normalModeElements.forEach(elem => {
                if (elem) elem.classList.remove('hidden');
            });
            aboutModeElements.forEach(elem => {
                if (elem) elem.classList.add('hidden');
            });
        }

        function updateProject() {

            let image_index = imageIndices[project_index] || 0; 
            const project = projects[project_index];
            const totalImages = project.images.length;
            const hasEndText = !!(project['end-text']);
            const totalSlides = totalImages + (hasEndText ? 1 : 0);
            const featuredImg = document.getElementById('featured-image');
            const endTextElem = document.getElementById('project-end-text');
            /*const photoTitle = document.getElementById('photo-title');*/
            const imageDesc = document.getElementById('photo-description');

            const imageCounter = document.getElementById('image-counter');
            const prevBtn = document.getElementById('prev-btn');
            const nextBtn = document.getElementById('next-btn');

            // Remove active class from all projects
            document.querySelectorAll('.project-title').forEach(title => {
                title.classList.remove('active');
            });
            
            // Add active class to selected project
            const projectTitle = projectGallery.children[project_index].querySelector(".project-title");
            if (projectTitle) {
                projectTitle.classList.add('active');
            }
            
            updateImage();

            // Event listeners for buttons
            prevBtn.addEventListener('click', showPrevImage);
            nextBtn.addEventListener('click', showNextImage);
            
            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowLeft') {
                    showPrevImage();
                } else if (e.key === 'ArrowRight') {
                    showNextImage();
                }
            });

            let wheelDelta = 0;
            mainDisplay.addEventListener('wheel', (e) => {
                wheelDelta += e.deltaY;
                const threshold = 100; // Increase this value for longer scroll to trigger

                if (wheelDelta <= -threshold) {
                    showPrevImage();
                    wheelDelta = 0;
                } else if (wheelDelta >= threshold) {
                    showNextImage();
                    wheelDelta = 0;
                }
            });

            // Show previous image
            function showPrevImage() {
                if (image_index > 0) {
                    image_index -= 1;
                    updateImage();
                }
            }
            
            // Show next image (or the end-text slide)
            function showNextImage() {
                const maxIndex = hasEndText ? totalImages : totalImages - 1;
                if (image_index < maxIndex) {
                    image_index += 1;
                    updateImage();
                }
            }
            // Keep the touch-swipe hooks pointing at this project's navigation
            imageNavNext = showNextImage;
            imageNavPrev = showPrevImage;

            function updateImage(){
                // Update the featured display
                const project = projects[project_index];
                // show the end-text slide instead of an image on the last slide
                const onEndText = hasEndText && image_index === totalImages;
                if (onEndText) {
                    featuredImg.style.display = 'none';
                    endTextElem.classList.remove('hidden');
                    endTextElem.textContent = project['end-text'];
                } else {
                    featuredImg.style.display = '';
                    endTextElem.classList.add('hidden');
                    const image = project.images[image_index];
                    if (project) {
                        console.log('Selected project:', project);
                        featuredImg.src = `assets/photos/${image.image_path}`;
                        /*featuredImg.alt = project['project-title'];*/
                        imageDesc.textContent = image.description || '';
                    }
                }
                updateCounter();
                updateButtonVisibility();

                function enterFullscreen() {
                    if (!document.fullscreenElement) {
                        featuredImg.requestFullscreen();
                    }
                }

                function exitFullscreen() {
                    if (document.fullscreenElement) {
                        document.exitFullscreen();
                    }
                }

                /*
                // Click center of image to fullscreen
                featuredImg.addEventListener('click', (e) => {
                    const rect = featuredImg.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    // Check if click is near center (within 20% of width/height)
                    if (
                        x > rect.width * 0.4 && x < rect.width * 0.6 &&
                        y > rect.height * 0.4 && y < rect.height * 0.6
                    ) {
                        enterFullscreen();
                    }
                });
                */

                mainDisplay.addEventListener('dblclick', (e) => {
                    if (e.target.closest('.nav-btn')) return; // double-clicking the arrows must not toggle fullscreen
                    if (!document.fullscreenElement) {
                        enterFullscreen();
                    } else {
                        exitFullscreen();
                    }
                });

                // Press 'f' to fullscreen
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'f' && !document.fullscreenElement) {
                        enterFullscreen();
                    }
                    if ((e.key === 'Escape') || (e.key === 'f') && document.fullscreenElement) {
                        exitFullscreen();
                    }
                });

                /*
                // Exit fullscreen on click outside image
                document.addEventListener('click', (e) => {
                    if (document.fullscreenElement && e.target !== featuredImg) {
                        exitFullscreen();
                    }
                });
                */
            }
            function updateCounter() {
                imageIndices[project_index] = image_index; // Update the index for the current project
                imageCounter.textContent = `${image_index + 1} / ${totalSlides}`;
            }
            // Update button visibility based on current index
            function updateButtonVisibility() {
                // Hide left button if at first image
                if(image_index === 0) {
                    prevBtn.classList.add('hidden_btn');
                } else {
                    prevBtn.classList.remove('hidden_btn');
                }
                // Hide right button if at last image (or on the end-text slide)
                const lastIndex = hasEndText ? totalImages : totalImages - 1;
                if(image_index === lastIndex) {
                    nextBtn.classList.add('hidden_btn');
                } else {
                    nextBtn.classList.remove('hidden_btn');
                }
            }
        }

        /* RESIZE
        const separator = document.getElementById('gallery-separator');
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;

        separator.addEventListener('mousedown', (e) => {
            isResizing = true;
            startY = e.clientY;
            startHeight = galleryContainer.offsetHeight;
            document.body.style.cursor = 'row-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const dy = e.clientY - startY;
            const newHeight = Math.max(100, startHeight + dy);
            galleryContainer.style.height = `${newHeight}px`;
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
        */
    }
});


function displayError() {
    const gallery = document.getElementById('project-gallery');
    gallery.innerHTML = '<p class="error">Error loading photos. Please try again later.</p>';
    
    const featuredImg = document.getElementById('featured-image');
    featuredImg.alt = 'Error loading image';
    
    document.getElementById('photo-description').textContent = 'Could not load photos. Please check your connection.';
}
