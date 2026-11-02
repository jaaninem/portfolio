// Read the project title row height (the scroll step). It derives from the title
// font size, which is scaled down on mobile, so re-read it on viewport changes.
// We read the used height of a rendered .project-title (which resolves the calc),
// because getComputedStyle returns raw var()/calc() text for custom properties.
function readProjectHeight() {
    const title = document.querySelector('.project-title');
    if (title) {
        return parseFloat(getComputedStyle(title).height);
    }
    return projectHeight; // titles not rendered yet: keep the current value
}
let projectHeight = 60; // placeholder; set precisely once the titles are rendered

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
    const galleryList = (typeof GALLERIES !== 'undefined' && Array.isArray(GALLERIES)) ? GALLERIES : [];
    const firstGalleryFile = galleryList.length > 0 ? galleryList[0].file : 'galleries/main.json';

    Promise.all([
        fetch(firstGalleryFile)
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
            initGallery(projects, availableFiles, galleryList);
        })
        .catch(error => {
            console.error('Error loading projects:', error);
            displayError();
        });
    
    function initGallery(projects, availableFiles, galleryList) {
	    console.log('Project height:', projectHeight);

        const galleryNav = document.getElementById('gallery-nav');

        // index to track image indices for each project
        let imageIndices = {};
        // the projects currently displayed (swapped when switching galleries)
        let currentProjects = projects;

        // Add project titles to gallery
        function renderProjects() {
            projectGallery.innerHTML = '';
            imageIndices = {};

            currentProjects.forEach((project, index) => {

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

            totalProjects = currentProjects.length;
        }

        // Set up scrolling
        let currentPosition = 0;
        let project_index = 0;
        //let scrollTimeout = null;
        let totalProjects = 0;

        renderProjects();
        buildGalleryButtons();

        // The titles now exist, so we can resolve the actual row height (calc)
        projectHeight = readProjectHeight();

        // Keep the scroll step in sync when crossing the mobile/desktop breakpoint
        function onViewportResize() {
            projectHeight = readProjectHeight();
            currentPosition = project_index * projectHeight;
            projectGallery.style.transition = 'none';
            projectGallery.style.transform = `translateY(${-currentPosition}px)`;
        }
        window.addEventListener('resize', onViewportResize);
        window.addEventListener('orientationchange', onViewportResize);

        function projectTransition(newIndex){
            currentPosition = newIndex * projectHeight;
            projectTransitionAnimation(currentPosition, newIndex);
        }

        function projectTransitionAnimation(position, newIndex){
            projectGallery.style.transition = 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)';
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

        // AbortControllers to dedupe listeners added per project render / image update
        let projectEventController = null;
        let imageEventController = null;

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

        // --- Neighbour photo peeks ----------------------------------------
        // The panel shows one faint thumbnail of the previous slide and one of
        // the next slide, sitting just outside the featured photo. They replace
        // the old arrow buttons while wheel/swipe/keyboard navigation remains.
        const featuredImg = document.getElementById('featured-image');
        const endTextElem = document.getElementById('project-end-text');
        const prevPeek = document.getElementById('prev-peek');
        const nextPeek = document.getElementById('next-peek');

        function peekImage(peek) {
            return peek.querySelector('.peek-img');
        }

        // Point a peek at a project image, preferring its generated thumbnail.
        function showPeekImage(peek, imagePath, label) {
            const image = peekImage(peek);
            peek.classList.remove('is-text', 'is-hidden');
            peek.setAttribute('aria-label', label);
            peek.tabIndex = 0;
            if (image.dataset.path !== imagePath) {
                image.dataset.path = imagePath;
                image.dataset.fallback = '';
                image.alt = '';
                image.src = `assets/thumbs/${imagePath}`;
            }
        }

        // Represent the end-of-series text slide as a tiny "Fin" card.
        function showPeekText(peek, label) {
            const image = peekImage(peek);
            peek.classList.add('is-text');
            peek.classList.remove('is-hidden');
            peek.setAttribute('aria-label', label);
            peek.tabIndex = 0;
            image.removeAttribute('src');
            image.dataset.path = '';
        }

        function hidePeek(peek) {
            peek.classList.add('is-hidden');
            peek.tabIndex = -1;
        }

        // Which slides sit on each side of the current one.
        // `nextIsText` marks the end-of-series slide, which has no photo.
        function neighbourPaths(project, index, hasEndText, totalImages) {
            const lastSlide = hasEndText ? totalImages : totalImages - 1;
            return {
                prev: index > 0 ? project.images[index - 1].image_path : null,
                next: index < lastSlide && !(hasEndText && index === totalImages - 1)
                    ? project.images[index + 1].image_path
                    : null,
                nextIsText: hasEndText && index === totalImages - 1,
            };
        }

        // Show the peeks for the current slide, if it has neighbours.
        function updatePeeks(project, index, hasEndText, totalImages) {
            const neighbours = neighbourPaths(project, index, hasEndText, totalImages);

            if (neighbours.prev) {
                showPeekImage(prevPeek, neighbours.prev, 'Previous photo');
            } else {
                hidePeek(prevPeek);
            }

            if (neighbours.next) {
                showPeekImage(nextPeek, neighbours.next, 'Next photo');
            } else if (neighbours.nextIsText) {
                showPeekText(nextPeek, 'End of series');
            } else {
                hidePeek(nextPeek);
            }
        }

        // Warm the cache so the new peeks can be painted in the same frame as
        // the photo, without an empty box while their thumbnail downloads.
        function preloadPeekThumbnails(project, index, hasEndText, totalImages) {
            const neighbours = neighbourPaths(project, index, hasEndText, totalImages);
            [neighbours.prev, neighbours.next].forEach(path => {
                if (!path) return;
                const thumbnail = new Image();
                thumbnail.decoding = 'async';
                thumbnail.src = `assets/thumbs/${path}`;
            });
        }

        // Keep each peek just outside the featured photo, clamped inside the
        // panel's white gutter. The photo is centred vertically, so only the
        // horizontal position has to be computed.
        function positionPeeks() {
            const panelRect = mainDisplay.getBoundingClientRect();
            const onEndText = featuredImg.style.display === 'none';
            const reference = onEndText ? endTextElem : featuredImg;
            const referenceRect = reference.getBoundingClientRect();
            const gap = parseFloat(
                getComputedStyle(document.documentElement).getPropertyValue('--peek-gap')
            ) || 10;
            const edge = 2; // minimum distance from the panel edge
            const referenceLeft = referenceRect.width ? referenceRect.left - panelRect.left : 0;
            const referenceRight = referenceRect.width
                ? referenceRect.right - panelRect.left
                : panelRect.width;

            if (!prevPeek.classList.contains('is-hidden')) {
                const width = prevPeek.offsetWidth;
                prevPeek.style.left = `${Math.max(edge, referenceLeft - gap - width)}px`;
            }
            if (!nextPeek.classList.contains('is-hidden')) {
                const width = nextPeek.offsetWidth;
                const left = Math.min(panelRect.width - width - edge, referenceRight + gap);
                nextPeek.style.left = `${Math.max(edge, left)}px`;
            }
        }

        // A missing thumbnail (e.g. a freshly added photo) falls back to the
        // full image instead of leaving a blank peek.
        [prevPeek, nextPeek].forEach(peek => {
            const image = peekImage(peek);
            image.addEventListener('error', () => {
                const path = image.dataset.path;
                if (!path || image.dataset.fallback) return;
                image.dataset.fallback = '1';
                image.src = `assets/photos/${path}`;
            });
        });

        // Bound once: the hooks always target the current project's slides.
        prevPeek.addEventListener('click', () => imageNavPrev && imageNavPrev());
        nextPeek.addEventListener('click', () => imageNavNext && imageNavNext());

        // The panel changes size with the viewport and the draggable sidebar.
        if (typeof ResizeObserver === 'function') {
            new ResizeObserver(positionPeeks).observe(mainDisplay);
        }

        // Initialize the first project
        updateProject();

        const scrollSpeed = 0.15; // Adjust this for scroll sensitivity (desktop wheel)

        // Gallery swipe: any vertical swipe switches to the next / previous project,
        // regardless of the distance (predictable: one project per swipe).
        let swipeStartX = 0;
        let swipeStartY = 0;
        let swipeMoved = false;

        // Wheel event (desktop)
        galleryContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            handleScroll(e.deltaY);
        });

        // Touch events (mobile) - a swipe always switches exactly one project
        galleryContainer.addEventListener('touchstart', (e) => {
            if (e.target.closest('.gallery-buttons')) return; // let the gallery-name row scroll natively
            if (e.touches.length > 0) {
                swipeStartX = e.touches[0].clientX;
                swipeStartY = e.touches[0].clientY;
                swipeMoved = false;
            }
        });

        galleryContainer.addEventListener('touchmove', (e) => {
            if (e.target.closest('.gallery-buttons')) return; // don't hijack the gallery-name scroll
            if (e.touches.length === 0) return;
            const dx = e.touches[0].clientX - swipeStartX;
            const dy = e.touches[0].clientY - swipeStartY;
            // Past a small tap threshold this is a swipe: suppress the title click
            if (!swipeMoved && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
                swipeMoved = true;
            }
            if (swipeMoved) {
                e.preventDefault();
            }
        }, { passive: false });

        galleryContainer.addEventListener('touchend', (e) => {
            if (!swipeMoved) return; // a tap: let the title's click select it
            const dx = e.changedTouches[0].clientX - swipeStartX;
            const dy = e.changedTouches[0].clientY - swipeStartY;
            const threshold = 30; // px, minimum distance for a swipe
            // Only vertical, dominant swipes switch projects
            if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > threshold) {
                if (dy < 0) {
                    swipeToProject(project_index + 1); // finger up -> next
                } else {
                    swipeToProject(project_index - 1); // finger down -> previous
                }
            }
        });

        galleryContainer.addEventListener('touchcancel', () => {
            // nothing to do; the touch was cancelled
        });

        // Switch to an adjacent project (clamped to the list bounds)
        function swipeToProject(index) {
            const nextIndex = Math.min(Math.max(index, 0), totalProjects - 1);
            if (nextIndex !== project_index) {
                projectTransition(nextIndex);
            }
        }

        // Unified scroll handler (desktop wheel: stepped movement, snaps via projectTransitionAnimation)
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

        // Switch to a different gallery file
        function switchGallery(file) {
            fetch(file)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    if (!data || !Array.isArray(data)) {
                        throw new Error('Invalid gallery data');
                    }
                    currentProjects = data.map(project => ({ ...project, images: expandProjectImages(project, availableFiles) }));
                    renderProjects();
                    currentPosition = 0;
                    project_index = 0;
                    projectGallery.style.transition = 'none';
                    projectGallery.style.transform = 'translateY(0px)';
                    updateProject();
                })
                .catch(error => {
                    console.error('Error loading gallery:', error);
                });
        }

        // Build the gallery-name buttons at the top of the gallery panel
        function buildGalleryButtons() {
            const galleryButtons = document.getElementById('gallery-buttons');
            galleryList.forEach((gallery, index) => {
                const btn = document.createElement('button');
                btn.classList.add('gallery-nav-btn', 'gallery-btn');
                btn.textContent = gallery.name;
                if (index === 0) {
                    btn.classList.add('active');
                }
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.gallery-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    switchGallery(gallery.file);
                });
                galleryButtons.appendChild(btn);
            });
        }

        // About button logic
        const backBtn = document.getElementById('back');
        const aboutBtn = document.getElementById('about');
        const aboutText = document.getElementById('about-text');
        const cursorLine = document.getElementById('cursor-line');
        const photoInfo = document.getElementById('photo-info');

        const normalModeElements = [projectGallery, mainDisplay, cursorLine, galleryNav, imageContainer, photoInfo];
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
            // Replace listeners from the previous project render so none stack up
            if (projectEventController) projectEventController.abort();
            projectEventController = new AbortController();
            const projectSignal = projectEventController.signal;

            let image_index = imageIndices[project_index] || 0; 
            const project = currentProjects[project_index];
            const totalImages = project.images.length;
            const hasEndText = !!(project['end-text']);
            const totalSlides = totalImages + (hasEndText ? 1 : 0);
            /*const photoTitle = document.getElementById('photo-title');*/
            const imageDesc = document.getElementById('photo-description');

            const imageCounter = document.getElementById('image-counter');

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

            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowLeft') {
                    showPrevImage();
                } else if (e.key === 'ArrowRight') {
                    showNextImage();
                }
            }, { signal: projectSignal });

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
            }, { signal: projectSignal });

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
                // Replace listeners from the previous image render so none stack up
                if (imageEventController) imageEventController.abort();
                imageEventController = new AbortController();
                const imageSignal = imageEventController.signal;

                // Update the featured display
                const project = currentProjects[project_index];
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
                // Store the position immediately so switching projects before
                // the photo loads keeps the selection.
                imageIndices[project_index] = image_index;

                // The counter, the peeks and the photo change at the same
                // moment: when the new photo is ready (or immediately for the
                // text slide). The peeks always describe the photo on screen,
                // and the counter never runs ahead of it.
                const slideIndex = image_index;
                const syncSlide = () => {
                    updatePeeks(project, slideIndex, hasEndText, totalImages);
                    positionPeeks();
                    imageCounter.textContent = `${slideIndex + 1} / ${totalSlides}`;
                };
                if (onEndText) {
                    // The text slide is laid out immediately: nothing to wait for.
                    syncSlide();
                } else {
                    preloadPeekThumbnails(project, slideIndex, hasEndText, totalImages);
                    featuredImg.addEventListener('load', syncSlide, { once: true, signal: imageSignal });
                    featuredImg.addEventListener('error', syncSlide, { once: true, signal: imageSignal });
                }

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
                    if (e.target.closest('.peek')) return; // double-clicking a peek must not toggle fullscreen
                    if (!document.fullscreenElement) {
                        enterFullscreen();
                    } else {
                        exitFullscreen();
                    }
                }, { signal: imageSignal });

                // Press 'f' to fullscreen
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'f' && !document.fullscreenElement) {
                        enterFullscreen();
                    }
                    if ((e.key === 'Escape') || (e.key === 'f') && document.fullscreenElement) {
                        exitFullscreen();
                    }
                }, { signal: imageSignal });

                /*
                // Exit fullscreen on click outside image
                document.addEventListener('click', (e) => {
                    if (document.fullscreenElement && e.target !== featuredImg) {
                        exitFullscreen();
                    }
                });
                */
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
