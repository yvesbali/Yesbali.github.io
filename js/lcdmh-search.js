/**
 * LCDMH Search Module
 * Client-side video search for hub pages
 * Lightweight vanilla JS, no external dependencies
 */

(function() {
  'use strict';

  // CSS Variables from site theme
  const THEME = {
    orange: '#e67e22',
    orangeDark: '#d35400',
    noir: '#1a1a1a',
    muted: '#555',
    bg: '#f7f7f5',
    card: '#fff',
    border: '#e5e5e5',
    alt: '#f0ede8'
  };

  // Module state
  let searchIndex = null;
  let isInitialized = false;

  /**
   * Load search index JSON
   */
  async function loadSearchIndex() {
    if (searchIndex) return searchIndex;

    try {
      const response = await fetch('/data/search-index.json');
      if (!response.ok) throw new Error('Search index not found');
      searchIndex = await response.json();
      return searchIndex;
    } catch (error) {
      console.error('Failed to load search index:', error);
      return [];
    }
  }

  /**
   * Normalize text for search (lowercase, remove accents)
   */
  function normalizeText(text) {
    if (!text) return '';
    return text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, ''); // Remove diacritics
  }

  /**
   * Search videos by query
   */
  function searchVideos(query, videos) {
    if (!query || query.length < 2) return [];

    const normalized = normalizeText(query);
    const results = [];

    for (const video of videos) {
      const score = calculateRelevance(normalized, video);
      if (score > 0) {
        results.push({ ...video, score });
      }
    }

    // Sort by relevance
    return results.sort((a, b) => b.score - a.score);
  }

  /**
   * Calculate relevance score for a video
   */
  function calculateRelevance(query, video) {
    let score = 0;

    // Title match (highest weight)
    const titleNorm = normalizeText(video.title);
    if (titleNorm.includes(query)) {
      score += 100;
      if (titleNorm.startsWith(query)) score += 50;
    }

    // Description match
    const descNorm = normalizeText(video.description);
    if (descNorm.includes(query)) score += 30;

    // Tags match
    for (const tag of video.tags || []) {
      if (normalizeText(tag).includes(query)) score += 20;
    }

    // Zone match
    const zoneNorm = normalizeText(video.zone);
    if (zoneNorm.includes(query)) score += 15;

    return score;
  }

  /**
   * Create HTML for a search result card
   */
  function createResultCard(video) {
    const card = document.createElement('div');
    card.className = 'lcdmh-search-result-card';
    card.style.cssText = `
      background: ${THEME.card};
      border: 1px solid ${THEME.border};
      border-radius: 12px;
      overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s;
      display: flex;
      flex-direction: column;
      cursor: pointer;
      text-decoration: none;
    `;

    card.onmouseover = function() {
      this.style.transform = 'translateY(-3px)';
      this.style.boxShadow = '0 8px 25px rgba(0,0,0,.08)';
    };
    card.onmouseout = function() {
      this.style.transform = 'translateY(0)';
      this.style.boxShadow = 'none';
    };

    // Thumbnail
    const thumb = document.createElement('div');
    thumb.style.cssText = `
      position: relative;
      aspect-ratio: 16/9;
      overflow: hidden;
      background: ${THEME.alt};
    `;

    const img = document.createElement('img');
    img.src = video.thumbnail;
    img.alt = video.title;
    img.style.cssText = 'width: 100%; height: 100%; object-fit: cover; display: block;';
    img.loading = 'lazy';

    const playBtn = document.createElement('div');
    playBtn.style.cssText = `
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 54px;
      height: 54px;
      background: rgba(0,0,0,.6);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
    `;

    const playIcon = document.createElement('div');
    playIcon.style.cssText = `
      width: 0;
      height: 0;
      border-left: 20px solid #fff;
      border-top: 11px solid transparent;
      border-bottom: 11px solid transparent;
      margin-left: 5px;
    `;

    playBtn.appendChild(playIcon);
    thumb.appendChild(img);
    thumb.appendChild(playBtn);

    // Content
    const content = document.createElement('div');
    content.style.cssText = `
      padding: 1rem 1.2rem 1.2rem;
      flex: 1;
      display: flex;
      flex-direction: column;
    `;

    // Title
    const title = document.createElement('h3');
    title.textContent = video.title;
    title.style.cssText = `
      font-family: 'Montserrat', sans-serif;
      font-size: 0.95rem;
      font-weight: 700;
      color: ${THEME.noir};
      margin: 0 0 0.6rem 0;
      line-height: 1.3;
    `;

    // Tags
    const tagsDiv = document.createElement('div');
    tagsDiv.style.cssText = 'display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.7rem;';

    const videoTags = video.tags || [];
    for (const tag of videoTags.slice(0, 2)) {
      const tagEl = document.createElement('span');
      tagEl.textContent = tag;
      tagEl.style.cssText = `
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.2rem 0.65rem;
        border-radius: 20px;
        background: ${THEME.alt};
        color: ${THEME.muted};
      `;
      tagsDiv.appendChild(tagEl);
    }

    // Zone info
    let zoneText = video.zone ? video.zone : video.pageUrl.split('/').pop().replace('.html', '');
    if (zoneText && zoneText.length > 40) zoneText = zoneText.substring(0, 40) + '...';

    const zoneEl = document.createElement('p');
    zoneEl.textContent = zoneText || 'Road Trip';
    zoneEl.style.cssText = `
      font-size: 0.8rem;
      color: ${THEME.muted};
      margin: 0 0 0.5rem 0;
    `;

    // Link button
    const link = document.createElement('a');
    link.href = video.link;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Voir sur YouTube →';
    link.style.cssText = `
      display: inline-block;
      color: ${THEME.orange};
      font-weight: 600;
      font-size: 0.9rem;
      margin-top: auto;
      text-decoration: none;
      transition: text-decoration 0.2s;
    `;
    link.onmouseover = function() { this.style.textDecoration = 'underline'; };
    link.onmouseout = function() { this.style.textDecoration = 'none'; };

    content.appendChild(title);
    content.appendChild(tagsDiv);
    content.appendChild(zoneEl);
    content.appendChild(link);

    card.appendChild(thumb);
    card.appendChild(content);

    return card;
  }

  /**
   * Create and show search modal
   */
  function createSearchModal() {
    // Modal overlay
    const modal = document.createElement('div');
    modal.id = 'lcdmh-search-modal';
    modal.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.6);
      display: flex;
      align-items: flex-start;
      justify-content: center;
      z-index: 3000;
      padding: 2rem 1rem;
      overflow-y: auto;
    `;

    // Modal content
    const content = document.createElement('div');
    content.className = 'lcdmh-search-modal-content';
    content.style.cssText = `
      background: ${THEME.card};
      border-radius: 16px;
      max-width: 900px;
      width: 100%;
      padding: 2rem;
      max-height: 85vh;
      overflow-y: auto;
      box-shadow: 0 20px 60px rgba(0,0,0,.3);
    `;

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.type = 'button';
    closeBtn.className = 'lcdmh-search-close';
    closeBtn.style.cssText = `
      position: absolute;
      top: 1.5rem;
      right: 1.5rem;
      background: none;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      color: ${THEME.muted};
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background 0.2s, color 0.2s;
    `;
    closeBtn.onmouseover = function() {
      this.style.background = THEME.alt;
      this.style.color = THEME.noir;
    };
    closeBtn.onmouseout = function() {
      this.style.background = 'none';
      this.style.color = THEME.muted;
    };

    // Title
    const title = document.createElement('h2');
    title.textContent = 'Rechercher dans les Road Trips';
    title.style.cssText = `
      font-family: 'Montserrat', sans-serif;
      font-size: 1.5rem;
      font-weight: 800;
      color: ${THEME.noir};
      margin: 0 0 1.5rem 0;
    `;

    // Search input
    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'lcdmh-search-input';
    input.placeholder = 'Taper au moins 2 caractères...';
    input.style.cssText = `
      width: 100%;
      padding: 0.75rem 1rem;
      font-size: 1rem;
      border: 2px solid ${THEME.border};
      border-radius: 8px;
      font-family: 'Inter', sans-serif;
      transition: border-color 0.2s;
      margin-bottom: 1.5rem;
      box-sizing: border-box;
    `;
    input.onfocus = function() {
      this.style.borderColor = THEME.orange;
    };
    input.onblur = function() {
      this.style.borderColor = THEME.border;
    };

    // Results container
    const results = document.createElement('div');
    results.id = 'lcdmh-search-results';
    results.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.5rem;
      min-height: 2rem;
    `;

    // No results message
    const noResults = document.createElement('p');
    noResults.id = 'lcdmh-search-no-results';
    noResults.style.cssText = `
      color: ${THEME.muted};
      text-align: center;
      padding: 2rem 0;
      grid-column: 1 / -1;
      display: none;
    `;
    noResults.textContent = 'Aucune vidéo trouvée. Essayez d\'autres termes.';

    results.appendChild(noResults);

    content.appendChild(closeBtn);
    content.appendChild(title);
    content.appendChild(input);
    content.appendChild(results);
    modal.appendChild(content);

    // Close handlers
    const closeModal = function() {
      modal.remove();
      isInitialized = false;
    };

    closeBtn.onclick = closeModal;
    modal.onclick = function(e) {
      if (e.target === modal) closeModal();
    };

    // Keyboard handler
    const keyHandler = function(e) {
      if (e.key === 'Escape') {
        closeModal();
        document.removeEventListener('keydown', keyHandler);
      }
    };
    document.addEventListener('keydown', keyHandler);

    // Search handler
    input.oninput = async function() {
      const query = this.value;
      const resultsDiv = document.getElementById('lcdmh-search-results');
      const noResults = document.getElementById('lcdmh-search-no-results');

      if (query.length < 2) {
        resultsDiv.innerHTML = '';
        resultsDiv.appendChild(noResults);
        return;
      }

      if (!searchIndex) {
        searchIndex = await loadSearchIndex();
      }

      const videos = searchVideos(query, searchIndex);

      resultsDiv.innerHTML = '';

      if (videos.length === 0) {
        resultsDiv.appendChild(noResults);
      } else {
        for (const video of videos) {
          resultsDiv.appendChild(createResultCard(video));
        }
      }
    };

    document.body.appendChild(modal);
    input.focus();
  }

  /**
   * Add search button to nav
   */
  function initializeSearch() {
    if (isInitialized) return;
    isInitialized = true;

    const nav = document.getElementById('lcdmh-nav');
    if (!nav) return;

    const navLinks = nav.querySelector('.lcdmh-nav-links');
    if (!navLinks) return;

    // Create search button
    const searchLi = document.createElement('li');
    searchLi.className = 'lcdmh-search-nav-item';

    const searchBtn = document.createElement('button');
    searchBtn.type = 'button';
    searchBtn.className = 'lcdmh-search-btn';
    searchBtn.innerHTML = '🔍';
    searchBtn.title = 'Rechercher les vidéos';
    searchBtn.style.cssText = `
      background: none;
      border: none;
      cursor: pointer;
      font-size: 1.2rem;
      padding: 0.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
      color: ${THEME.noir};
    `;

    searchBtn.onmouseover = function() {
      this.style.transform = 'scale(1.15)';
      this.style.color = THEME.orange;
    };
    searchBtn.onmouseout = function() {
      this.style.transform = 'scale(1)';
      this.style.color = THEME.noir;
    };

    searchBtn.onclick = function(e) {
      e.preventDefault();
      createSearchModal();
    };

    searchLi.appendChild(searchBtn);

    // Insert before desktop CTAs
    const desktopCtas = navLinks.querySelector('.lcdmh-desktop-cta');
    if (desktopCtas) {
      navLinks.insertBefore(searchLi, desktopCtas);
    } else {
      navLinks.appendChild(searchLi);
    }
  }

  /**
   * Initialize when DOM is ready
   */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSearch);
  } else {
    initializeSearch();
  }

  // Re-initialize if nav is loaded dynamically
  if (window.MutationObserver) {
    new MutationObserver(function(mutations) {
      for (const mutation of mutations) {
        if (mutation.addedNodes.length) {
          for (const node of mutation.addedNodes) {
            if (node.id === 'lcdmh-nav' || (node.nodeType === 1 && node.querySelector('#lcdmh-nav'))) {
              setTimeout(initializeSearch, 100);
              break;
            }
          }
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  }

})();
