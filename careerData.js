document.addEventListener('DOMContentLoaded', function () {
  var pageType = document.body.getAttribute('data-page-type');
  var CONFIG = {
    private_jobs: {
      label: 'Private Jobs',
      title: 'Private Jobs 2026',
      badge: 'Live company hiring',
      subtitle: 'Fresh private-sector openings collected from major career portals with salary, experience and location snippets.',
      accent: '#1D4ED8',
      accentSoft: '#EFF6FF',
      empty: 'No private jobs matched your current search.'
    },
    remote_jobs: {
      label: 'Remote Jobs',
      title: 'Remote Jobs 2026',
      badge: 'Work from anywhere',
      subtitle: 'Remote-first openings collected from leading remote job boards so visitors can quickly find distributed roles.',
      accent: '#0F172A',
      accentSoft: '#E2E8F0',
      empty: 'No remote jobs matched your current search.'
    }
  };

  var meta = CONFIG[pageType];
  if (!meta) return;

  document.documentElement.style.setProperty('--page-accent', meta.accent);
  document.documentElement.style.setProperty('--page-accent-soft', meta.accentSoft);
  document.title = meta.title + ' - OnlyJobs';

  var mapText = {
    pageBadge: meta.badge,
    pageTitle: meta.title,
    pageSubtitle: meta.subtitle,
    bcLabel: meta.label,
    searchInput: 'Search ' + meta.label.toLowerCase() + '...'
  };

  Object.keys(mapText).forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (id === 'searchInput') el.placeholder = mapText[id];
    else el.textContent = mapText[id];
  });

  var allItems = [];
  var filteredItems = [];
  var activeSource = 'all';
  var currentSearch = '';

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function buildPostUrl(item) {
    return 'post.html?id=' + encodeURIComponent(item.id) + '&cat=' + encodeURIComponent(pageType);
  }

  function getSummary(item) {
    if (item.salary) return item.salary;
    if (item.experience) return item.experience;
    return item.state_label || 'See listing';
  }

  function buildSourceFilters(items) {
    var sources = ['all'];
    items.forEach(function (item) {
      var source = item.source || 'OnlyJobs';
      if (sources.indexOf(source) === -1) sources.push(source);
    });

    var wrap = document.getElementById('sourceFilters');
    wrap.innerHTML = '';
    sources.forEach(function (source) {
      var button = document.createElement('button');
      button.className = 'chip' + (source === activeSource ? ' on' : '');
      button.textContent = source === 'all' ? 'All Sources' : source;
      button.onclick = function () {
        activeSource = source;
        buildSourceFilters(allItems);
        applyFilters();
      };
      wrap.appendChild(button);
    });
  }

  function renderList() {
    var list = document.getElementById('jobList');
    var count = document.getElementById('jobCount');
    count.textContent = filteredItems.length + ' jobs';

    if (!filteredItems.length) {
      list.innerHTML = '<div class="empty-state"><h3>No jobs found</h3><p>' + escapeHtml(meta.empty) + '</p></div>';
      return;
    }

    var html = '';
    filteredItems.forEach(function (item) {
      var location = item.job_location || item.state_label || (pageType === 'remote_jobs' ? 'Remote' : 'Location not specified');
      var company = item.company || item.source || 'OnlyJobs';
      var tags = [];
      if (item.source) tags.push('<span class="tag">' + escapeHtml(item.source) + '</span>');
      if (item.salary) tags.push('<span class="tag">' + escapeHtml(item.salary) + '</span>');
      if (item.experience) tags.push('<span class="tag">' + escapeHtml(item.experience) + '</span>');
      (item.skills || []).slice(0, 3).forEach(function (skill) {
        tags.push('<span class="tag">' + escapeHtml(skill) + '</span>');
      });

      html += ''
        + '<article class="job-card">'
        + '  <div class="job-main">'
        + '    <div class="job-title"><a href="' + buildPostUrl(item) + '">' + escapeHtml(item.title) + '</a></div>'
        + '    <div class="job-meta">' + escapeHtml(company) + ' · ' + escapeHtml(location) + '</div>'
        + '    <div class="job-tags">' + tags.join('') + '</div>'
        + '    <div class="job-note">Posted: ' + escapeHtml(item.posted_at || 'Recently updated') + ' · Highlight: ' + escapeHtml(getSummary(item)) + '</div>'
        + '  </div>'
        + '  <div class="job-actions">'
        + '    <a class="btn-secondary" href="' + buildPostUrl(item) + '">View Details</a>'
        + '    <a class="btn-primary" href="' + escapeHtml(item.original_url || '#') + '" target="_blank" rel="noopener">Open Source</a>'
        + '  </div>'
        + '</article>';
    });

    list.innerHTML = html;
  }

  function applyFilters() {
    filteredItems = allItems.filter(function (item) {
      var source = item.source || 'OnlyJobs';
      var text = [
        item.title,
        item.company,
        item.job_location,
        item.state_label,
        item.salary,
        item.experience,
        (item.skills || []).join(' '),
        source
      ].join(' ').toLowerCase();

      var sourceMatch = activeSource === 'all' || source === activeSource;
      var searchMatch = !currentSearch || text.indexOf(currentSearch) > -1;
      return sourceMatch && searchMatch;
    });
    renderList();
  }

  fetch('data.json')
    .then(function (response) { return response.json(); })
    .then(function (data) {
      allItems = Array.isArray(data[pageType]) ? data[pageType].slice() : [];
      buildSourceFilters(allItems);
      applyFilters();
    })
    .catch(function () {
      document.getElementById('jobList').innerHTML = '<div class="empty-state"><h3>Unable to load jobs</h3><p>Check that <code>data.json</code> is available for this page.</p></div>';
    });

  document.getElementById('searchInput').addEventListener('input', function (event) {
    currentSearch = event.target.value.trim().toLowerCase();
    applyFilters();
  });
});
