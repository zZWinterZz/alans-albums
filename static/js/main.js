// Basic JS starter
document.addEventListener('DOMContentLoaded', function(){
  console.log('alans-albums base.js loaded')

  // Reusable notes overlay handler for elements with .notes-toggle
  function initNotesOverlays(){
    document.querySelectorAll('.notes-toggle').forEach(function(btn){
      if(btn._notesInitialized) return;
      btn._notesInitialized = true;

      // If an overlay node exists in the same container, record its id on the button
      try{
        const container = btn.closest('.notes-container');
        if(container){
          const localOverlay = container.querySelector('.notes-overlay');
          if(localOverlay && localOverlay.id){ btn.dataset.overlayRef = localOverlay.id; }
        }
      }catch(e){}

      // helper to hide overlay cleanly
      function hideOverlay(btn, overlay){
        if(!overlay) return;
        if(overlay._notesLocked) return;
        overlay._notesLocked = true;
        overlay.classList.add('d-none');
        overlay.classList.remove('is-mounted');
        overlay.style.left = '';
        overlay.style.top = '';
        overlay.style.width = '';
        overlay.style.visibility = '';
        if(btn) btn.setAttribute('aria-expanded','false');
        if(window._notesOutsideClick){ document.removeEventListener('click', window._notesOutsideClick); window._notesOutsideClick = null; }
        if(window._notesEscKey){ document.removeEventListener('keydown', window._notesEscKey); window._notesEscKey = null; }
        // return overlay to its container if possible
        try{ const container = btn && btn.closest('.notes-container'); if(container && overlay.parentElement !== container) container.appendChild(overlay); }catch(e){/*ignore*/}
        // release lock shortly after hiding so subsequent toggles can run
        setTimeout(function(){ try{ overlay._notesLocked = false; }catch(e){} }, 50);
      }

      // helper to show overlay cleanly
      function showOverlay(btn, overlay){
        if(!overlay) return;
        if(overlay._notesLocked) return;
        overlay._notesLocked = true;
        // close any other mounted overlays first
        const mounted = Array.from(document.querySelectorAll('.notes-overlay.is-mounted'));
        mounted.forEach(function(o){ if(o !== overlay){ const b = document.querySelector(`[aria-controls="${o.id}"]`); hideOverlay(b,o); } });

        // mount and position
        overlay.classList.remove('d-none');
        overlay.classList.add('is-mounted');
        overlay.style.position = 'absolute';
        overlay.style.right = '';
        overlay.style.left = '0px';
        overlay.style.top = '0px';
        overlay.style.visibility = 'hidden';
        document.body.appendChild(overlay);
        if(btn) btn.setAttribute('aria-expanded','true');

        try{
          const brect = btn.getBoundingClientRect();
          const card = btn.closest('.card');
          const cardWidth = card ? card.getBoundingClientRect().width : 360;
          const maxWidth = Math.min(Math.max(240, cardWidth), 720);
          overlay.style.width = `${maxWidth}px`;
          const overlayWidth = overlay.offsetWidth || maxWidth;
          const docWidth = document.documentElement.clientWidth || window.innerWidth;
          const scrollX = window.scrollX || window.pageXOffset || 0;
          const scrollY = window.scrollY || window.pageYOffset || 0;
          let left = brect.left + scrollX;
          const minLeft = 8 + scrollX;
          const maxAllowedLeft = scrollX + Math.max(docWidth, overlayWidth) - overlayWidth - 8;
          left = Math.min(Math.max(minLeft, left), maxAllowedLeft);
          const top = brect.bottom + scrollY + 6;
          overlay.style.left = `${left}px`;
          overlay.style.top = `${top}px`;
          overlay.style.visibility = 'visible';
        }catch(e){ overlay.style.left='8px'; overlay.style.top='8px'; overlay.style.width='420px'; overlay.style.visibility='visible'; }

        // outside click / esc close
        window._notesOutsideClick = function(ev){ try{ if(!overlay.contains(ev.target) && !btn.contains(ev.target)){ hideOverlay(btn, overlay); } }catch(e){} };
        document.addEventListener('click', window._notesOutsideClick);
        window._notesEscKey = function(ev){ if(ev.key === 'Escape'){ if(!overlay.classList.contains('d-none')){ hideOverlay(btn, overlay); } } };
        document.addEventListener('keydown', window._notesEscKey);
        // release lock shortly after showing so hide can run on user action
        setTimeout(function(){ try{ overlay._notesLocked = false; }catch(e){} }, 50);
      }

      btn.addEventListener('click', async function(ev){
        // avoid re-entrancy/races from multiple handlers firing at once
        if(btn._notesBusy) return;
        btn._notesBusy = true;
          // debug: check-condition clicked
          try{
            // stopImmediatePropagation to avoid other click handlers
            try{ ev.stopImmediatePropagation(); }catch(e){}
          // prevent the document click handler from racing with this handler
          ev.preventDefault();
          ev.stopPropagation();
        const rid = btn.getAttribute('data-release-id');
        if(!rid) return;
          // Prefer an explicit overlay id set on the button (ensures uniqueness when the same listing appears twice)
      // Prefer explicit attributes, fall back to the overlayRef recorded at init
      const explicitOid = btn.getAttribute('data-overlay-id') || btn.dataset.overlayRef || '';
        const ariaOid = btn.getAttribute('aria-controls') || '';
          let overlay = null;
          const container = btn.closest('.notes-container');
            // Prefer aria-controls (explicit mapping in markup), then data-overlay-id, then fallbacks
            if(ariaOid){ overlay = document.getElementById(ariaOid) || null; }
            if(!overlay && explicitOid){
              // Try direct lookup by data-overlay-id
              overlay = document.getElementById(explicitOid) || null;
              // If not found globally, try to find an overlay inside the same container
              if(!overlay && container){
                try{ overlay = container.querySelector('#' + explicitOid) || container.querySelector('.notes-overlay'); }catch(e){ /* ignore selector errors */ }
              }
            }
          if(!overlay){
            const numeric = String(rid).match(/(\d+)/);
            const pk = numeric ? numeric[1] : null;
            // Prefer an overlay whose data-release-pk matches this id (will find the closest instance)
            if(pk){
              const overlays = Array.from(document.querySelectorAll(`.notes-overlay[data-release-pk="${pk}"]`));
              const btnSection = btn.getAttribute('data-section') || btn.dataset.section || '';
              // If we have a section, prefer an overlay in that section which matches aria/id/ref
              if(btnSection && overlays.length){
                // try ariaOid, explicitOid, overlayRef within that section
                overlay = overlays.find(o => o.dataset.section === btnSection && ( (ariaOid && o.id === ariaOid) || (explicitOid && o.id === explicitOid) || (btn.dataset && btn.dataset.overlayRef && o.id === btn.dataset.overlayRef) ));
                // otherwise pick any overlay in the same section
                if(!overlay) overlay = overlays.find(o => o.dataset.section === btnSection) || null;
              }
              // if still not found, fall back to first overlay for the release
              if(!overlay && overlays.length) overlay = overlays[0];
            }
            // Fallback to legacy id-based lookup
            if(!overlay && pk){ overlay = document.getElementById('manage-notes-' + pk) || document.getElementById('notes-' + pk) || null; }
          }
    if(!overlay){ /* overlay not found */ }
        if(!overlay) return;
  /* overlay selected: { ariaOid, explicitOid, overlayId: overlay && overlay.id } */
  // toggle based on current mounted state
        const mounted = overlay.classList.contains('is-mounted') && !overlay.classList.contains('d-none');
        if(mounted){
          hideOverlay(btn, overlay);
          return;
        }
        // show it
        showOverlay(btn, overlay);

        // If overlay has dataset.loaded or contains static content, skip fetch
        if(overlay.dataset.loaded === '1' || overlay.textContent.trim().length > 0) return;
        const numeric = String(rid).match(/(\d+)/);
        if(numeric){
          const id = numeric[1];
          try{
            const resp = await fetch(`/manage/discogs/release_details/${id}/`);
            if(resp.ok){
              const data = await resp.json();
              // Populate any overlay instances bound to this release id (featured + all-listing instances)
              const overlays = Array.from(document.querySelectorAll(`.notes-overlay[data-release-pk="${id}"]`));
              overlays.forEach(function(o){
                const body = o.querySelector('.card-body');
                if(body) body.innerHTML = notesToHtml(data.notes || '');
                o.dataset.loaded = '1';
              });
            }
          }catch(e){ /* ignore */ }
        }
        }finally{
          // clear busy after a short delay to allow any document click handlers to finish
          setTimeout(function(){ btn._notesBusy = false; }, 50);
        }
      });
    });
  }

  // init on load and expose for dynamic content
  initNotesOverlays();
  window.initNotesOverlays = initNotesOverlays;
  // Small helper: escape HTML then convert our [[REMOVE:...]] tokens to highlighted spans
  function escapeHtml(str){
    if(!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function notesToHtml(raw){
    const esc = escapeHtml(raw || '');
    // Replace marker tokens like [[REMOVE:some text]] with a highlighted span
    return esc.replace(/\[\[REMOVE:(.*?)\]\]/g, function(_, inner){
      const t = inner.trim();
      return `<span class="remove-highlight">${t}</span>`;
    }).replace(/\[\[REMOVE:image\]\]/g, '<span class="remove-highlight">image</span>');
  }
  // expose helper globally so template-level scripts can reuse it
  window.notesToHtml = notesToHtml;
  
  // --- Image viewer: full-screen/cycling viewer for listing images ---
  function initImageViewer(){
    if(window._imageViewerInitialized) return;
    window._imageViewerInitialized = true;

    // Create viewer DOM once and append to body
    function createViewer(){
      if(document.getElementById('image-viewer')) return document.getElementById('image-viewer');
      const wrap = document.createElement('div');
      wrap.id = 'image-viewer';
      wrap.className = 'image-viewer d-none';
      wrap.innerHTML = `
        <div class="iv-backdrop" data-role="backdrop"></div>
        <div class="iv-inner" role="dialog" aria-modal="true" aria-hidden="true" tabindex="-1">
          <button class="iv-close btn btn-sm" aria-label="Close viewer">×</button>
          <div class="iv-stage text-center">
            <div class="iv-img-wrap">
              <img class="iv-img" src="" alt="" />
            </div>
            <div class="iv-caption small text-muted mt-2"></div>
            <div class="iv-controls mt-2 d-flex gap-2 justify-content-center align-items-center">
              <button class="iv-prev btn btn-sm" aria-label="Previous image">‹</button>
              <button class="iv-zoom-toggle btn btn-sm" aria-label="Toggle zoom">🔍</button>
              <button class="iv-next btn btn-sm" aria-label="Next image">›</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(wrap);
      return wrap;
    }

    const viewer = createViewer();
    const inner = viewer.querySelector('.iv-inner');
    const imgWrap = viewer.querySelector('.iv-img-wrap');
    const imgEl = viewer.querySelector('.iv-img');
    const captionEl = viewer.querySelector('.iv-caption');
    const btnClose = viewer.querySelector('.iv-close');
    const btnPrev = viewer.querySelector('.iv-prev');
    const btnNext = viewer.querySelector('.iv-next');
    const btnZoom = viewer.querySelector('.iv-zoom-toggle');
    const backdrop = viewer.querySelector('.iv-backdrop');

    let images = [];
    let index = 0;
    let triggerEl = null;
    // simple viewer state (no zoom/pan)
    let prevBodyOverflow = '';

    // Map-style transform approach: maintain a scale and offsets and apply
    // transform: translate(x,y) scale(z) to the image (transform-origin: top left).
  let ivZoom = 1;
  let IV_MIN_ZOOM = 0.5;
  const IV_MAX_ZOOM = 5;
    let ivOffsetX = 0, ivOffsetY = 0;
    let isDragging = false;
    let dragStart = {x:0,y:0, startOffsetX:0, startOffsetY:0};

    // Apply the transform to the image element
    function applyTransform(){
      try{
        imgEl.style.transformOrigin = 'top left';
        imgEl.style.transform = `translate(${Math.round(ivOffsetX)}px, ${Math.round(ivOffsetY)}px) scale(${ivZoom})`;
      }catch(e){}
    }

    // Compute minimum zoom so the image at least fills the viewport (or a sensible fraction)
    function computeMinZoom(naturalW, naturalH){
      try{
        const crect = imgWrap.getBoundingClientRect();
        const cw = crect.width || Math.min(window.innerWidth, 900);
        const ch = crect.height || Math.min(window.innerHeight, 700);
        const minZoomW = cw / (naturalW || 1);
        const minZoomH = ch / (naturalH || 1);
        // prefer filling height (so image is large) but ensure we don't go tiny
        return Math.max(minZoomW, minZoomH, 0.1);
      }catch(e){ return 0.5; }
    }

    function clampOffsets(){
      try{
        // Use clientWidth/clientHeight to avoid layout rounding issues
        // and compute strict min/max relative to the content box.
        const cw = Math.max(0, imgWrap.clientWidth || imgWrap.getBoundingClientRect().width || Math.min(window.innerWidth, 900));
        const ch = Math.max(0, imgWrap.clientHeight || imgWrap.getBoundingClientRect().height || Math.min(window.innerHeight, 700));
        const naturalW = imgEl.naturalWidth || imgEl.offsetWidth || cw;
        const naturalH = imgEl.naturalHeight || imgEl.offsetHeight || ch;
        const scaledW = naturalW * ivZoom;
        const scaledH = naturalH * ivZoom;

        // Slack / overscroll: allow a little extra pan beyond strict edges for
        // a looser feel. Use 10% of the viewport as the slack amount.
        const slackX = Math.round(cw * 0.10);
        const slackY = Math.round(ch * 0.10);

        if (scaledW <= cw) {
          // Center but allow +/- slack around the center position
          const centerX = (cw - scaledW) / 2;
          const minC = centerX - slackX;
          const maxC = centerX + slackX;
          ivOffsetX = Math.max(minC, Math.min(ivOffsetX, maxC));
        } else {
          // Allow panning beyond the strict edge by slack
          const minOffsetX = Math.min(0, cw - scaledW) - slackX;
          const maxOffsetX = 0 + slackX;
          ivOffsetX = Math.max(minOffsetX, Math.min(ivOffsetX, maxOffsetX));
        }

        if (scaledH <= ch) {
          const centerY = (ch - scaledH) / 2;
          const minCY = centerY - slackY;
          const maxCY = centerY + slackY;
          ivOffsetY = Math.max(minCY, Math.min(ivOffsetY, maxCY));
        } else {
          const minOffsetY = Math.min(0, ch - scaledH) - slackY;
          const maxOffsetY = 0 + slackY;
          ivOffsetY = Math.max(minOffsetY, Math.min(ivOffsetY, maxOffsetY));
        }
      }catch(e){}
    }

    // Reset viewer to a simple fitted state (no zoom/pan)
    function resetToFitAndCenter(){
      try{
        // ensure the wrapper fills available space and centers its content
        try{
          imgWrap.style.display = 'flex';
          imgWrap.style.alignItems = 'center';
          imgWrap.style.justifyContent = 'center';
          imgWrap.style.width = '100%';
          imgWrap.style.maxWidth = '90vw';
          imgWrap.style.boxSizing = 'border-box';
          imgWrap.style.minHeight = '40vh';
          imgWrap.style.maxHeight = '80vh';
        }catch(e){}
        imgEl.style.display = 'block';
        imgEl.style.margin = '0 auto';
        imgEl.style.transform = 'none';
        imgEl.style.transformOrigin = '';
        imgEl.style.width = 'auto';
        imgEl.style.height = 'auto';
        imgEl.style.maxWidth = '90vw';
        imgEl.style.maxHeight = '80vh';
        imgEl.style.objectFit = 'contain';
        try{ ivZoom = IV_MIN_ZOOM = 1; ivOffsetX = 0; ivOffsetY = 0; }catch(e){}
      }catch(e){}
    }

    function zoomAtPoint(viewX, viewY, factor){
      try{
        const naturalW = imgEl.naturalWidth || imgEl.offsetWidth || 1000;
        const naturalH = imgEl.naturalHeight || imgEl.offsetHeight || 600;
        const prevZoom = ivZoom;
        let newZoom = prevZoom * factor;
        newZoom = Math.max(IV_MIN_ZOOM, Math.min(IV_MAX_ZOOM, newZoom));
        if(newZoom === prevZoom) return;
        // map-space point
        const mapX = (viewX - ivOffsetX) / prevZoom;
        const mapY = (viewY - ivOffsetY) / prevZoom;
        ivOffsetX = viewX - mapX * newZoom;
        ivOffsetY = viewY - mapY * newZoom;
        ivZoom = newZoom;
        // If the new scaled image fits the wrapper, center it explicitly
        try{
          const crect = imgWrap.getBoundingClientRect();
          const cw = crect.width || Math.min(window.innerWidth, 900);
          const ch = crect.height || Math.min(window.innerHeight, 700);
          const scaledW = naturalW * ivZoom;
          const scaledH = naturalH * ivZoom;
          if (scaledW <= cw + 1 && scaledH <= ch + 1) {
            ivOffsetX = (cw - scaledW) / 2;
            ivOffsetY = (ch - scaledH) / 2;
          } else {
            clampOffsets();
          }
        }catch(e){ clampOffsets(); }
        applyTransform();
      }catch(e){}
    }

    // Block scroll/touch events that originate outside the viewer (capture phase)
    function globalWheelCapture(ev){
      try{
        if(!viewer.contains(ev.target)){
          ev.preventDefault(); ev.stopImmediatePropagation();
          return false;
        }
      }catch(e){}
    }

    function showViewer(){
      try{
        viewer.classList.remove('d-none');
        inner.setAttribute('aria-hidden','false');
        // focus management
        try{ btnClose.focus(); }catch(e){ /* ignore focus errors */ }
        document.addEventListener('keydown', keyHandler);
        // prevent body scrolling and background interactions while viewer open
        try{ prevBodyOverflow = document.body.style.overflow || ''; document.body.style.overflow = 'hidden'; }catch(e){}
        // install capture-phase handlers to reliably stop background scrolling
        window.addEventListener('wheel', globalWheelCapture, { passive: false, capture: true });
        window.addEventListener('touchmove', globalWheelCapture, { passive: false, capture: true });
        // ensure inner and imgWrap allow centering
        try{
          inner.style.display = 'flex';
          inner.style.alignItems = 'center';
          inner.style.justifyContent = 'center';
          inner.style.boxSizing = 'border-box';
          imgWrap.style.display = 'flex';
          imgWrap.style.alignItems = 'center';
          imgWrap.style.justifyContent = 'center';
          imgWrap.style.width = '100%';
          imgWrap.style.maxWidth = '90vw';
          imgWrap.style.margin = '0 auto';
        }catch(e){}
      }catch(err){ console.error('image viewer show error', err); }
    }
    function hideViewer(){
      viewer.classList.add('d-none');
      inner.setAttribute('aria-hidden','true');
      document.removeEventListener('keydown', keyHandler);
      // reset zoom/pan
      resetToFitAndCenter();
      // restore body scrolling and remove blockers
      try{ document.body.style.overflow = prevBodyOverflow || ''; }catch(e){}
      try{ window.removeEventListener('wheel', globalWheelCapture, { passive: false, capture: true }); }catch(e){}
      try{ window.removeEventListener('touchmove', globalWheelCapture, { passive: false, capture: true }); }catch(e){}
      // return focus
      try{ if(triggerEl && typeof triggerEl.focus === 'function') triggerEl.focus(); }catch(e){}
      triggerEl = null;
    }

    function keyHandler(ev){
      if(ev.key === 'Escape') { hideViewer(); }
      else if(ev.key === 'ArrowLeft') { prevImage(); }
      else if(ev.key === 'ArrowRight') { nextImage(); }
    }

    function updateImage(){
      if(!images || !images.length) return;
      const src = images[index] || '';
      // we will size and center the image when it loads
      imgEl.onload = function(){
        try{
          // Ensure wrapper is prepared for map-style transform mode: we want
          // the image positioned at the top-left of the wrapper so translate
          // offsets are applied from a consistent origin. Avoid centering here;
          // resetToFitAndCenter() will configure centering for the non-zoomed mode.
          try{
            inner.style.width = '100%';
            imgWrap.style.display = 'block';
            imgWrap.style.position = 'relative';
            imgWrap.style.overflow = 'hidden';
            imgWrap.style.width = '100%';
            imgWrap.style.maxWidth = '90vw';
            imgWrap.style.boxSizing = 'border-box';
            imgWrap.style.minHeight = '40vh';
          }catch(e){}
            const naturalW = imgEl.naturalWidth || imgEl.width || 1600;
            const naturalH = imgEl.naturalHeight || imgEl.height || 900;
            // set intrinsic pixel size so transforms scale from natural dimensions
            imgEl.style.width = naturalW + 'px';
            imgEl.style.height = naturalH + 'px';
            // Position the image at top-left of the wrapper when using transforms
            imgEl.style.display = 'block';
            imgEl.style.margin = '0';
            imgEl.style.position = 'absolute';
            imgEl.style.left = '0px';
            imgEl.style.top = '0px';
            // compute minimum zoom that keeps transforms valid. Allow zooming
            // out to natural size (1.0) by clamping the computed minimum to
            // at most 1. This ensures users can always zoom back to 1x.
            IV_MIN_ZOOM = Math.min(1, computeMinZoom(naturalW, naturalH));
            try{
              const crect = imgWrap.getBoundingClientRect();
              const cw = crect.width || Math.min(window.innerWidth, 900);
              const ch = crect.height || Math.min(window.innerHeight, 700);
              const fitScale = Math.min(cw / naturalW, ch / naturalH);
              // If the image fits the viewport at natural size, start at 1.0
              if (naturalW <= cw && naturalH <= ch) {
                ivZoom = 1;
              } else {
                // otherwise scale down to fit, clamped to min/max
                ivZoom = Math.max(IV_MIN_ZOOM, Math.min(IV_MAX_ZOOM, fitScale));
              }
            }catch(e){ ivZoom = Math.min(1, IV_MIN_ZOOM || 1); }
            // center image for the newly loaded frame and apply transform.
            // Compute a natural center position (so the image starts centered
            // even when we allow small overscroll). We'll set ivOffset to the
            // center point then clamp (which will respect slack if present).
            try{
              const crect2 = imgWrap.getBoundingClientRect();
              const cw2 = crect2.width || Math.min(window.innerWidth, 900);
              const ch2 = crect2.height || Math.min(window.innerHeight, 700);
              const scaledW2 = naturalW * ivZoom;
              const scaledH2 = naturalH * ivZoom;
              ivOffsetX = (cw2 - scaledW2) / 2;
              ivOffsetY = (ch2 - scaledH2) / 2;
            }catch(e){ ivOffsetX = 0; ivOffsetY = 0; }
            clampOffsets();
            applyTransform();
        }catch(e){}
      };
      imgEl.src = src;
      captionEl.textContent = `${index+1} / ${images.length}`;
      // preload neighbors
      preload(index-1); preload(index+1);
    }

    function preload(i){
      if(i < 0 || i >= images.length) return;
      const p = new Image(); p.src = images[i];
    }

    function prevImage(){
      if(!images.length) return;
      index = (index - 1 + images.length) % images.length;
      updateImage();
    }
    function nextImage(){
      if(!images.length) return;
      index = (index + 1) % images.length;
      updateImage();
    }

    btnClose.addEventListener('click', function(){ hideViewer(); });
    backdrop.addEventListener('click', function(){ hideViewer(); });
    btnPrev.addEventListener('click', function(){ prevImage(); });
    btnNext.addEventListener('click', function(){ nextImage(); });
    // hide zoom control for now (no zoom/pan behavior)
    try{ btnZoom.style.display = 'none'; }catch(e){}

    // Re-introduce map-style zoom/pan handlers (translate+scale) using
    // zoomAtPoint / clampOffsets / applyTransform so zoom is pointer-centered.
    try{ btnZoom.style.display = ''; }catch(e){}

    // wheel to zoom (pointer-centered)
    imgWrap.addEventListener('wheel', function(ev){
      if(!images.length) return;
      ev.preventDefault(); ev.stopImmediatePropagation();
      const crect = imgWrap.getBoundingClientRect();
      const cx = ev.clientX - crect.left;
      const cy = ev.clientY - crect.top;
      const delta = ev.deltaY || ev.wheelDelta || -ev.detail;
      const factor = (delta < 0) ? 1.12 : 0.9; // negative delta -> zoom in
      zoomAtPoint(cx, cy, factor);
    }, { passive:false });

    // pointer-based panning when zoomed (translate offsets)
    imgWrap.addEventListener('pointerdown', function(ev){
      // Only allow panning when the scaled image is larger than the wrapper
      try{
        const cw = imgWrap.clientWidth || imgWrap.getBoundingClientRect().width || window.innerWidth;
        const ch = imgWrap.clientHeight || imgWrap.getBoundingClientRect().height || window.innerHeight;
        const naturalW = imgEl.naturalWidth || imgEl.offsetWidth || cw;
        const naturalH = imgEl.naturalHeight || imgEl.offsetHeight || ch;
        const scaledW = naturalW * ivZoom;
        const scaledH = naturalH * ivZoom;
        if (scaledW <= cw + 1 && scaledH <= ch + 1) return; // image fits, no panning
      }catch(e){ /* fallback to previous guard */ if(ivZoom <= IV_MIN_ZOOM + 0.0001) return; }
      ev.preventDefault(); ev.stopImmediatePropagation();
      isDragging = true; try{ imgWrap.setPointerCapture(ev.pointerId); }catch(e){}
      dragStart = { x: ev.clientX, y: ev.clientY, startOffsetX: ivOffsetX, startOffsetY: ivOffsetY };
      imgWrap.style.cursor = 'grabbing';
    });
    imgWrap.addEventListener('pointermove', function(ev){
      if(!isDragging) return;
      ev.preventDefault(); ev.stopImmediatePropagation();
      const dx = ev.clientX - dragStart.x;
      const dy = ev.clientY - dragStart.y;
      ivOffsetX = dragStart.startOffsetX + dx;
      ivOffsetY = dragStart.startOffsetY + dy;
      clampOffsets();
      applyTransform();
    });
    imgWrap.addEventListener('pointerup', function(ev){ if(isDragging){ isDragging = false; try{ imgWrap.releasePointerCapture(ev.pointerId); }catch(e){} imgWrap.style.cursor=''; } });
    imgWrap.addEventListener('pointercancel', function(){ if(isDragging){ isDragging = false; imgWrap.style.cursor=''; } });

    // double-click toggles zoom around the pointer position
    imgWrap.addEventListener('dblclick', function(ev){
      ev.preventDefault(); ev.stopImmediatePropagation();
      const crect = imgWrap.getBoundingClientRect();
      const cx = ev.clientX - crect.left;
      const cy = ev.clientY - crect.top;
      if(ivZoom <= IV_MIN_ZOOM + 0.0001){
        zoomAtPoint(cx, cy, Math.min(2 / ivZoom, IV_MAX_ZOOM / ivZoom));
      } else {
        ivZoom = IV_MIN_ZOOM;
        // If the image at min zoom fits the wrapper, center it explicitly
        try{
          const naturalW = imgEl.naturalWidth || imgEl.offsetWidth || 1000;
          const naturalH = imgEl.naturalHeight || imgEl.offsetHeight || 600;
          const cw = crect.width || Math.min(window.innerWidth, 900);
          const ch = crect.height || Math.min(window.innerHeight, 700);
          const scaledW = naturalW * ivZoom;
          const scaledH = naturalH * ivZoom;
          if (scaledW <= cw + 1 && scaledH <= ch + 1){
            ivOffsetX = (cw - scaledW) / 2;
            ivOffsetY = (ch - scaledH) / 2;
          }
        }catch(e){}
        clampOffsets();
        applyTransform();
      }
    });

    // zoom toggle button: center zoom on viewport center
    btnZoom.addEventListener('click', function(){
      try{
        const crect = imgWrap.getBoundingClientRect();
        const cx = crect.width / 2;
        const cy = crect.height / 2;
        if(ivZoom <= IV_MIN_ZOOM + 0.0001){
          zoomAtPoint(cx, cy, Math.min(2 / ivZoom, IV_MAX_ZOOM / ivZoom));
        } else {
          ivZoom = IV_MIN_ZOOM;
          // If the image at min zoom fits the wrapper, center it explicitly
          try{
            const naturalW = imgEl.naturalWidth || imgEl.offsetWidth || 1000;
            const naturalH = imgEl.naturalHeight || imgEl.offsetHeight || 600;
            const cw = crect.width || Math.min(window.innerWidth, 900);
            const ch = crect.height || Math.min(window.innerHeight, 700);
            const scaledW = naturalW * ivZoom;
            const scaledH = naturalH * ivZoom;
            if (scaledW <= cw + 1 && scaledH <= ch + 1){
              ivOffsetX = (cw - scaledW) / 2;
              ivOffsetY = (ch - scaledH) / 2;
            }
          }catch(e){}
          clampOffsets(); applyTransform();
        }
      }catch(e){}
    });

    // public open function
    function openViewer(list, start, trigger){
      if(!list || !list.length) return;
      images = list.slice(0);
      index = Math.max(0, start || 0);
      triggerEl = trigger || null;
  // opening viewer, images count: (hidden for release)
      // Ensure the viewer is visible before we measure sizing in updateImage
      try{ showViewer(); }catch(e){ console.error('showViewer failed', e); }
      try{ updateImage(); }catch(e){ console.error('updateImage failed', e); }
    }

    // Attach click handlers to existing and future .check-condition-btn via delegation/init
    function initButtons(){
      document.querySelectorAll('.check-condition-btn').forEach(function(btn){
        if(btn._ivInit) return; btn._ivInit = true;
        btn.addEventListener('click', function(ev){
          ev.preventDefault(); ev.stopPropagation();
          // find nearby listing-images container
          let container = btn.closest('.card');
          let imgs = [];
          try{
            const listNode = container ? container.querySelector('.listing-images') : null;
            if(listNode){
              Array.from(listNode.querySelectorAll('img')).forEach(function(i){ 
                if(!i) return;
                const candidate = i.dataset && (i.dataset.fullSrc || i.dataset.large || i.dataset.full) || i.getAttribute && (i.getAttribute('data-full') || i.getAttribute('data-large')) || i.src;
                if(candidate) imgs.push(candidate);
              });
            }
          }catch(e){}
          // fallback to card thumb if no additional images
          try{ if(!imgs.length){ const thumb = container ? container.querySelector('img.card-img-top') : null; if(thumb && thumb.src) imgs.push(thumb.src); } }catch(e){}
          if(!imgs.length) return;
          openViewer(imgs, 0, btn);
        });
      });
    }

    // initialize any existing buttons now
    initButtons();
    // Fallback: delegated click handler so dynamically inserted or missed buttons still open the viewer
    document.addEventListener('click', function(ev){
      try{
        const btn = ev.target.closest && ev.target.closest('.check-condition-btn');
        if(!btn) return;
        // Prevent duplicate handling when initButtons already wired this element
        if(btn._ivInit) return;
        ev.preventDefault(); ev.stopPropagation();
        let container = btn.closest('.card');
        let imgs = [];
  try{ const listNode = container ? container.querySelector('.listing-images') : null; if(listNode) Array.from(listNode.querySelectorAll('img')).forEach(function(i){ if(!i) return; const candidate = i.dataset && (i.dataset.fullSrc || i.dataset.large || i.dataset.full) || i.getAttribute && (i.getAttribute('data-full') || i.getAttribute('data-large')) || i.src; if(candidate) imgs.push(candidate); }); }catch(e){}
        try{ if(!imgs.length){ const thumb = container ? container.querySelector('img.card-img-top') : null; if(thumb && thumb.src) imgs.push(thumb.src); } }catch(e){}
        if(!imgs.length) return;
        openViewer(imgs, 0, btn);
      }catch(e){/* ignore */}
    });
    // expose for dynamic content
    window.initImageViewerButtons = initButtons;
    window.openListingImageViewer = openViewer;
  }
  // initialize image viewer once DOM is ready
  initImageViewer();
  // Eagerly fetch formats_lines for all visible cards on the current page (concurrency-limited)
  (function(){
    const cards = Array.from(document.querySelectorAll('.card[data-release-id]'));
    if(!cards.length) return;
    const concurrency = 4;
    let idx = 0;
    async function worker(){
      while(true){
        const i = idx++;
        if(i >= cards.length) return;
        const card = cards[i];
        const releaseId = card.getAttribute('data-release-id');
        if(!releaseId) continue;
        const idMatch = String(releaseId).match(/(\d+)/);
        if(!idMatch) continue;
        const id = idMatch[1];
        try{
          const resp = await fetch(`/manage/discogs/release_details/${id}/`);
          if(!resp.ok) continue;
          const data = await resp.json();
          if(data.formats_lines && data.formats_lines.length){
            const formatsArea = card.querySelector('.formats-area');
            if(formatsArea){
              let html = '<ul class="list-unstyled small mb-1">';
              for(const line of data.formats_lines){
                html += `<li>${line}</li>`;
              }
              html += '</ul>';
              formatsArea.innerHTML = html;
            }
          }
          // Populate all overlay instances associated with this release id
          if(data.notes){
            const overlays = Array.from(document.querySelectorAll(`.notes-overlay[data-release-pk="${id}"]`));
            overlays.forEach(function(o){
              const body = o.querySelector('.card-body');
              if(body) body.innerHTML = notesToHtml(data.notes || '');
              o.dataset.loaded = '1';
            });
          }
        }catch(err){ /* ignore */ }
      }
    }
    for(let i=0;i<concurrency;i++) worker();
  })();
});
