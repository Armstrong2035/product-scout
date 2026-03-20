(function() {
  // Dynamically infer API Base from where this script is hosted
  const currentScript = document.currentScript;
  const API_BASE = currentScript ? new URL(currentScript.src).origin : "https://productscout.shop";
  const SHOP_URL = window.Shopify ? window.Shopify.shop : new URL(window.location.href).searchParams.get('shop');

  if (!SHOP_URL) {
    console.error('[SCOUT] Missing Shop URL. Script will not initialize.');
    return;
  }

  // --- Helpers ---
  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  };

  const setCookie = (name, value) => {
    document.cookie = `${name}=${value}; path=/; max-age=31536000; samesite=lax`;
  };

  const generateUUID = () => crypto.randomUUID();

  // Initialize Session
  let sessionId = getCookie('scout_session_id');
  if (!sessionId) {
    sessionId = generateUUID();
    setCookie('scout_session_id', sessionId);
  }

  // --- UI Construction ---
  const style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = `${API_BASE}/static/scout-overlay.css`;
  document.head.appendChild(style);

  const container = document.createElement('div');
  container.id = 'scout-overlay-container';
  container.innerHTML = `
    <button class="scout-fab" id="scout-trigger">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
    </button>
    <div class="scout-drawer" id="scout-drawer">
      <div class="scout-header">
        <div class="scout-search-container">
          <svg class="scout-search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="text" class="scout-input" id="scout-search-input" placeholder="Ask for anything... (e.g. 'breathable shoes for Joint fatigue')">
        </div>
        <button id="scout-close" style="background:none; border:none; cursor:pointer; color:#64748b;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="scout-content" id="scout-results">
        <div style="text-align:center; padding: 40px; color:#64748b;">
          Find your perfect gear with AI-powered search.
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(container);

  // --- Functional Logic ---
  const trigger = document.getElementById('scout-trigger');
  const drawer = document.getElementById('scout-drawer');
  const close = document.getElementById('scout-close');
  const input = document.getElementById('scout-search-input');
  const resultsGrid = document.getElementById('scout-results');

  let currentSearchId = null;

  trigger.onclick = () => drawer.classList.add('open');
  close.onclick = () => drawer.classList.remove('open');

  input.onkeypress = (e) => {
    if (e.key === 'Enter') performSearch(input.value);
  };

  async function performSearch(query) {
    if (!query.trim()) return;

    resultsGrid.innerHTML = '<div class="scout-results-grid" id="scout-grid"></div>';
    const grid = document.getElementById('scout-grid');
    
    // Add skeletons
    for (let i = 0; i < 4; i++) {
        grid.innerHTML += `
            <div class="scout-card scout-skeleton" style="height:300px;"></div>
        `;
    }

    try {
      const response = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          shop_url: SHOP_URL,
          session_id: sessionId,
          limit: 10
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            handleStreamingEvent(data, grid);
          }
        }
      }
    } catch (err) {
      console.error('[SCOUT] Search failed:', err);
      resultsGrid.innerHTML = `<div style="color:red; text-align:center;">Something went wrong. Please try again.</div>`;
    }
  }

  function handleStreamingEvent(data, grid) {
    if (data.error) {
      console.error('[SCOUT SERVER ERROR]', data.error);
      document.getElementById('scout-results').innerHTML = `<div style="color:red; text-align:center; padding: 40px;">Oops, an error occurred!<br><br><small>${data.error}</small></div>`;
      return;
    }
    if (data.type === 'results') {
      currentSearchId = data.search_id;
      setCookie('scout_last_query', currentSearchId);
      renderInitialResults(data.results, grid);
    } else if (data.type === 'explanation') {
      updateJustification(data.index, data.explanation);
    }
  }

  function renderInitialResults(results, grid) {
    grid.innerHTML = ''; // Clear skeletons
    if (results.length === 0) {
      resultsGrid.innerHTML = '<div style="text-align:center; padding:40px;">No matches found. Try a different query.</div>';
      return;
    }

    results.forEach((prod, idx) => {
      // In a real implementation, we'd fetch product titles/images from Shopify Storefront API
      // For this demo, we'll use placeholders or IDs
      const card = document.createElement('div');
      card.className = 'scout-card';
      card.dataset.index = idx;
      card.dataset.id = prod.storefront_id;
      
      card.innerHTML = `
        <div style="padding:100px 0; background:#f1f5f9; display:flex; align-items:center; justify-content:center; color:#94a3b8;">
           <img class="scout-card-img" src="https://via.placeholder.com/400x400?text=Product+${idx+1}" alt="Product">
        </div>
        <div class="scout-card-info">
          <div class="scout-card-title">Product Candidate ${idx + 1}</div>
          <div class="scout-card-price">$ --.--</div>
          <button class="scout-add-btn">Add to Cart</button>
        </div>
        <div class="scout-ai-badge" id="scout-ai-${idx}">ⓘ</div>
        <div class="scout-ai-tooltip" id="scout-tooltip-${idx}">AI is analyzing why this fits your query...</div>
      `;

      card.addEventListener('click', () => trackEvent('click', prod.storefront_id, idx));
      card.querySelector('.scout-add-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          trackEvent('cart', prod.storefront_id, idx);
          alert('Added to cart! (Demo)');
      });

      grid.appendChild(card);
    });
  }

  function updateJustification(index, text) {
    const badge = document.getElementById(`scout-ai-${index}`);
    const tooltip = document.getElementById(`scout-tooltip-${index}`);
    if (badge && tooltip) {
      badge.classList.add('visible');
      tooltip.innerText = text;
    }
  }

  async function trackEvent(type, productId, position) {
    if (!currentSearchId) return;
    
    try {
      await fetch(`${API_BASE}/track/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_id: currentSearchId,
          shop_url: SHOP_URL,
          product_id: productId,
          position_clicked: position
        })
      });
    } catch (err) {
      console.warn('[SCOUT] Tracking failed:', err);
    }
  }

})();
