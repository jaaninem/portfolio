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
        let imageNavGo = null; // jump straight to a slide index
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
        // Each side of the featured photo gets a strip of faint thumbnails for
        // the adjacent slides. The strips sit in the panel's white gutter and
        // hold as many thumbnails as fit, so the featured photo keeps its size.
        const featuredImg = document.getElementById('featured-image');
        const endTextElem = document.getElementById('project-end-text');
        const prevStrip = document.getElementById('prev-peeks');
        const nextStrip = document.getElementById('next-peeks');

        const PEEK_MAX = 5; // upper bound of thumbnails per side
        const PEEK_EDGE = 2; // minimum distance between a strip and the panel edge
        const PEEK_MOBILE_QUERY = '(max-width: 768px)';

        // Custom properties holding a clamp() keep their token text when read
        // back, so measure a hidden probe element for the resolved width.
        const peekProbe = document.createElement('div');
        peekProbe.className = 'peek peek-probe';
        peekProbe.setAttribute('aria-hidden', 'true');
        mainDisplay.appendChild(peekProbe);

        function peekMetrics() {
            const styles = getComputedStyle(document.documentElement);
            const read = (name, fallback) => {
                const value = parseFloat(styles.getPropertyValue(name));
                return Number.isFinite(value) ? value : fallback;
            };
            return {
                width: peekProbe.getBoundingClientRect().width || 46,
                gap: read('--peek-gap', 10),
                spacing: read('--peek-spacing', 8),
            };
        }

        // How many thumbnails fit between the photo's edge and the panel edge.
        function peekCapacity(gutter, metrics) {
            if (window.matchMedia(PEEK_MOBILE_QUERY).matches) return 1;
            const usable = gutter - PEEK_EDGE - metrics.gap + metrics.spacing;
            const fit = Math.floor(usable / (metrics.width + metrics.spacing));
            return Math.min(PEEK_MAX, Math.max(1, fit));
        }

        // The slides up to `count` steps away on one side of the current one.
        // The end-of-series slide becomes a text card and always ends the strip.
        function peekItems(project, index, hasEndText, totalImages, direction, count) {
            const lastSlide = hasEndText ? totalImages : totalImages - 1;
            const items = [];
            for (let step = 1; step <= count; step += 1) {
                const slide = index + direction * step;
                if (slide < 0 || slide > lastSlide) break;
                if (hasEndText && slide === totalImages) {
                    items.push({
                        slide,
                        text: true,
                        label: step === 1 ? 'End of series' : `End of series (${step} ahead)`,
                    });
                    break;
                }
                items.push({
                    slide,
                    path: project.images[slide].image_path,
                    label: direction < 0
                        ? (step === 1 ? 'Previous photo' : `Previous photo (${step} back)`)
                        : (step === 1 ? 'Next photo' : `Next photo (${step} ahead)`),
                });
            }
            return items;
        }

        // Which slides sit on each side of the current one (prefetch only).
        function neighbourPaths(project, index, hasEndText, totalImages) {
            const lastSlide = hasEndText ? totalImages : totalImages - 1;
            return {
                prev: index > 0 ? project.images[index - 1].image_path : null,
                next: index < lastSlide && !(hasEndText && index === totalImages - 1)
                    ? project.images[index + 1].image_path
                    : null,
            };
        }

        function createPeek() {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'peek';
            const image = document.createElement('img');
            image.className = 'peek-img';
            image.alt = '';
            image.decoding = 'async';
            // A missing thumbnail (e.g. a freshly added photo) falls back to
            // the full image instead of leaving a blank peek.
            image.addEventListener('error', () => {
                const path = image.dataset.path;
                if (!path || image.dataset.fallback) return;
                image.dataset.fallback = '1';
                image.src = `assets/photos/${path}`;
            });
            const label = document.createElement('span');
            label.className = 'peek-label';
            label.setAttribute('aria-hidden', 'true');
            label.textContent = 'Fin';
            button.append(image, label);
            return button;
        }

        function applyPeek(button, item) {
            button.dataset.slide = String(item.slide);
            button.setAttribute('aria-label', item.label);
            button.classList.toggle('is-text', !!item.text);
            const image = button.querySelector('.peek-img');
            if (item.text) {
                image.removeAttribute('src');
                image.dataset.path = '';
                image.dataset.fallback = '';
                return;
            }
            if (image.dataset.path !== item.path) {
                image.dataset.path = item.path;
                image.dataset.fallback = '';
                image.src = `assets/thumbs/${item.path}`;
            }
        }

        // Reuse the existing buttons so a slide change only swaps their content.
        function renderPeekStrip(strip, items) {
            while (strip.children.length > items.length) {
                strip.lastElementChild.remove();
            }
            items.forEach((item, position) => {
                let button = strip.children[position];
                if (!button) {
                    button = createPeek();
                    strip.appendChild(button);
                }
                applyPeek(button, item);
            });
        }

        // Where the photo (or the end-text block) sits inside the panel.
        function peekGeometry() {
            const panelRect = mainDisplay.getBoundingClientRect();
            const reference = featuredImg.style.display === 'none' ? endTextElem : featuredImg;
            const referenceRect = reference.getBoundingClientRect();
            if (!referenceRect.width) return null;
            return {
                panelWidth: panelRect.width,
                referenceLeft: referenceRect.left - panelRect.left,
                referenceRight: referenceRect.right - panelRect.left,
            };
        }
        // Each strip sits as a unit just outside the photo, clamped inside the
        // panel's white gutter. The photo is centred vertically, so only the
        // horizontal position has to be computed.
        function positionPeekStrips(geometry, metrics) {
            if (prevStrip.children.length) {
                const width = prevStrip.getBoundingClientRect().width;
                prevStrip.style.left = `${Math.max(PEEK_EDGE, geometry.referenceLeft - metrics.gap - width)}px`;
            }
            if (nextStrip.children.length) {
                const width = nextStrip.getBoundingClientRect().width;
                const left = Math.min(
                    geometry.panelWidth - width - PEEK_EDGE,
                    geometry.referenceRight + metrics.gap
                );
                nextStrip.style.left = `${Math.max(PEEK_EDGE, left)}px`;
            }
        }

        // The current slide's neighbour context, kept so the strips can be
        // rebuilt when the panel is resized without a slide change.
        let peekContext = null;

        function refreshPeeks() {
            if (!peekContext) return;
            const geometry = peekGeometry();
            if (!geometry) return;
            const { project, index, hasEndText, totalImages } = peekContext;
            const metrics = peekMetrics();
            const counts = {
                prev: peekCapacity(geometry.referenceLeft, metrics),
                next: peekCapacity(geometry.panelWidth - geometry.referenceRight, metrics),
            };
            renderPeekStrip(prevStrip, peekItems(project, index, hasEndText, totalImages, -1, counts.prev));
            renderPeekStrip(nextStrip, peekItems(project, index, hasEndText, totalImages, 1, counts.next));
            positionPeekStrips(geometry, metrics);
            preloadPeekThumbnails(project, index, totalImages, Math.max(counts.prev, counts.next));
        }

        // Show the peeks for the current slide: remember the context, then build.
        function updatePeeks(project, index, hasEndText, totalImages) {
            peekContext = { project, index, hasEndText, totalImages };
            refreshPeeks();
        }

        // Warm the cache for every thumbnail the strips can show, so an update
        // never leaves an empty box.
        const preloadedThumbs = new Set();
        function preloadPeekThumbnails(project, index, totalImages, lookahead) {
            const lastPhoto = totalImages - 1;
            for (let position = index - lookahead; position <= index + lookahead; position += 1) {
                if (position < 0 || position > lastPhoto) continue;
                const url = `assets/thumbs/${project.images[position].image_path}`;
                if (preloadedThumbs.has(url)) continue;
                preloadedThumbs.add(url);
                const thumbnail = new Image();
                thumbnail.decoding = 'async';
                thumbnail.src = url;
            }
            if (preloadedThumbs.size > 200) preloadedThumbs.clear();
        }

        // Originals known to be loaded, so a slide change can paint the full
        // photo directly instead of a thumbnail preview.
        const PREFETCH_LIMIT = 6;
        const PREFETCH_DELAY = 300; // ms of calm before fetching neighbours
        const prefetchedPhotos = new Map();
        const prefetchingPhotos = new Set();
        let prefetchTimer = 0;
        let pendingFullPhoto = null;
        let previewSized = false;

        function rememberPhoto(url, image) {
            prefetchingPhotos.delete(url);
            prefetchedPhotos.set(url, image);
            while (prefetchedPhotos.size > PREFETCH_LIMIT) {
                prefetchedPhotos.delete(prefetchedPhotos.keys().next().value);
            }
        }

        // Download an original in the background with low priority, so the
        // next slide can usually be painted at full quality straight away.
        function prefetchPhoto(url) {
            if (!url || prefetchedPhotos.has(url) || prefetchingPhotos.has(url)) return;
            prefetchingPhotos.add(url);
            const image = new Image();
            image.decoding = 'async';
            image.fetchPriority = 'low';
            image.addEventListener('load', () => rememberPhoto(url, image), { once: true });
            image.addEventListener('error', () => prefetchingPhotos.delete(url), { once: true });
            image.src = url;
        }

        // Fetch the originals on both sides once the user pauses, so rapid
        // swipes do not download slides that are skipped.
        function scheduleNeighbourPrefetch(project, index, hasEndText, totalImages) {
            clearTimeout(prefetchTimer);
            prefetchTimer = setTimeout(() => {
                const neighbours = neighbourPaths(project, index, hasEndText, totalImages);
                [neighbours.prev, neighbours.next].forEach(path => {
                    if (path) prefetchPhoto(`assets/photos/${path}`);
                });
            }, PREFETCH_DELAY);
        }

        function cancelPendingFullPhoto() {
            if (!pendingFullPhoto) return;
            const image = pendingFullPhoto;
            pendingFullPhoto = null;
            image.src = '';
        }

        // Load the original off-screen. The thumbnail preview, or the previous
        // photo, stays visible until the file is ready to paint.
        function loadFullPhoto(url, signal) {
            const image = new Image();
            image.decoding = 'async';
            pendingFullPhoto = image;
            image.addEventListener('load', () => {
                if (pendingFullPhoto !== image) return;
                pendingFullPhoto = null;
                rememberPhoto(url, image);
                featuredImg.src = url;
                featuredImg.addEventListener('load', () => {
                    clearPreviewSize();
                    refreshPeeks();
                }, { once: true, signal });
            }, { once: true });
            image.addEventListener('error', () => {
                if (pendingFullPhoto === image) pendingFullPhoto = null;
            }, { once: true });
            image.src = url;
        }

        // A 300 px thumbnail keeps its natural size under the photo's
        // max-width/max-height rules, so it would appear smaller than the
        // original. Size it to the box the original will occupy instead.
        function sizePreviewToContainer() {
            if (!featuredImg.naturalWidth || !featuredImg.naturalHeight) return;
            const styles = getComputedStyle(imageContainer);
            const boxWidth = imageContainer.clientWidth
                - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
            const boxHeight = imageContainer.clientHeight
                - parseFloat(styles.paddingTop) - parseFloat(styles.paddingBottom);
            const imageStyles = getComputedStyle(featuredImg);
            const resolve = (value, base) => {
                if (!value || value === 'none') return Infinity;
                return value.endsWith('%') ? base * parseFloat(value) / 100 : parseFloat(value);
            };
            const maxWidth = resolve(imageStyles.maxWidth, boxWidth);
            const maxHeight = resolve(imageStyles.maxHeight, boxHeight);
            const aspect = featuredImg.naturalWidth / featuredImg.naturalHeight;
            let width = maxWidth;
            let height = width / aspect;
            if (height > maxHeight) {
                height = maxHeight;
                width = height * aspect;
            }
            featuredImg.style.width = `${width}px`;
            featuredImg.style.height = `${height}px`;
            previewSized = true;
        }

        function clearPreviewSize() {
            featuredImg.style.width = '';
            featuredImg.style.height = '';
            previewSized = false;
        }

        // Bound once: a click anywhere on a strip jumps straight to that slide.
        [prevStrip, nextStrip].forEach(strip => {
            strip.addEventListener('click', (event) => {
                const button = event.target.closest('.peek');
                if (!button) return;
                const slide = Number(button.dataset.slide);
                if (Number.isInteger(slide) && imageNavGo) imageNavGo(slide);
            });
        });

        // The panel changes size with the viewport and the draggable sidebar.
        if (typeof ResizeObserver === 'function') {
            new ResizeObserver(() => {
                if (previewSized) sizePreviewToContainer();
                refreshPeeks();
            }).observe(mainDisplay);
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

            // Jump straight to a slide (clamped to the project's slides)
            function showSlide(target) {
                const lastSlide = hasEndText ? totalImages : totalImages - 1;
                if (target < 0 || target > lastSlide || target === image_index) return;
                image_index = target;
                updateImage();
            }

            // Show previous image
            function showPrevImage() {
                showSlide(image_index - 1);
            }

            // Show next image (or the end-text slide)
            function showNextImage() {
                showSlide(image_index + 1);
            }
            // Keep the touch-swipe and peek hooks pointing at this project's navigation
            imageNavNext = showNextImage;
            imageNavPrev = showPrevImage;
            imageNavGo = showSlide;

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
                    clearPreviewSize();
                    endTextElem.classList.remove('hidden');
                    endTextElem.textContent = project['end-text'];
                } else {
                    featuredImg.style.display = '';
                    endTextElem.classList.add('hidden');
                    const image = project.images[image_index];
                    if (project) {
                        console.log('Selected project:', project);
                        /*featuredImg.alt = project['project-title'];*/
                        imageDesc.textContent = image.description || '';
                    }
                }
                // Store the position immediately so switching projects before
                // the photo loads keeps the selection.
                imageIndices[project_index] = image_index;
                clearTimeout(prefetchTimer);
                cancelPendingFullPhoto();

                // The counter and the peeks change with the visible slide. On a
                // photo slide that is either the prefetched original or the
                // cached thumbnail acting as an instant preview.
                const slideIndex = image_index;
                const syncSlide = () => {
                    updatePeeks(project, slideIndex, hasEndText, totalImages);
                    imageCounter.textContent = `${slideIndex + 1} / ${totalSlides}`;
                };
                if (onEndText) {
                    // The text slide is laid out immediately: nothing to wait for.
                    syncSlide();
                } else {
                    const image = project.images[slideIndex];
                    const thumbUrl = `assets/thumbs/${image.image_path}`;
                    const photoUrl = `assets/photos/${image.image_path}`;

                    const showingPreview = !prefetchedPhotos.has(photoUrl);
                    if (!showingPreview) {
                        // Ready at full quality: no preview frame at all.
                        featuredImg.src = photoUrl;
                    } else {
                        // Show the small copy immediately, then upgrade it.
                        featuredImg.src = thumbUrl;
                        loadFullPhoto(photoUrl, imageSignal);
                    }
                    // The counter and the peeks follow the image that is
                    // actually painted: the preview, or the original if ready.
                    const revealSlide = () => {
                        if (showingPreview) {
                            sizePreviewToContainer();
                        } else {
                            clearPreviewSize();
                        }
                        syncSlide();
                    };
                    featuredImg.addEventListener('load', revealSlide, { once: true, signal: imageSignal });
                    featuredImg.addEventListener('error', revealSlide, { once: true, signal: imageSignal });
                    scheduleNeighbourPrefetch(project, slideIndex, hasEndText, totalImages);
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
