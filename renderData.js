document.addEventListener("DOMContentLoaded", () => {
    Promise.all([
        fetch('data.json').then(r => r.ok ? r.json() : {}).catch(e => ({})),
        fetch('api/manual-data').then(r => r.ok ? r.json() : {}).catch(e => {
            return fetch('manual_data.json').then(r => r.ok ? r.json() : {}).catch(e => ({}));
        })
    ])
    .then(([scraperData, manualData]) => {
        if (scraperData.status && scraperData.status !== 'success') return;
  
        const data = {
            status: scraperData.status || 'success',
            latest_jobs: scraperData.latest_jobs || [],
            private_jobs: scraperData.private_jobs || [],
            remote_jobs: scraperData.remote_jobs || [],
            results: scraperData.results || [],
            admit_cards: scraperData.admit_cards || [],
            answer_keys: scraperData.answer_keys || []
        };

        // -------------------------
        // 1. Homepage Logic (index.html)
        // -------------------------
        const buildPostUrl = (item, category) => {
          const params = new URLSearchParams({ id: item.id });
          if (category) params.set('cat', category);
          return `post.html?${params.toString()}`;
        };

        const renderList = (containerId, scraperItems, manualItems, colorVar, category) => {
          const container = document.getElementById(containerId);
          if (!container) return;
          
          container.innerHTML = '';
          const items = [...(manualItems || []), ...(scraperItems || [])];
          
          if (!items || items.length === 0) {
              container.innerHTML = `<a class="entry" href="#"><div class="entry-text">No updates available.</div></a>`;
              return;
          }

          items.slice(0, 10).forEach((item, idx) => {
            const a = document.createElement('a');
            a.className = 'entry';
            a.href = item.url ? item.url : buildPostUrl(item, category);
            
            let html = `<span class="entry-dot" style="background:var(${colorVar});"></span>`;
            html += `<div><div class="entry-text">${item.title}</div>`;
            
            if (idx < 3) {
               html += `<span class="tag-new" style="margin-left: 5px; font-size:10px; padding: 2px 4px; background:var(${colorVar}); color:#fff; border-radius:4px;">NEW</span>`;
            }
            html += `</div>`;
            a.innerHTML = html;
            
            container.appendChild(a);
          });
        };

        const setText = (id, value) => {
          const el = document.getElementById(id);
          if (el) el.textContent = value;
        };
  
        // index.html containers
        renderList('live-government-jobs', data.latest_jobs, manualData.jobs, '--green', 'latest_jobs');
        renderList('live-latest-jobs', data.latest_jobs, manualData.jobs, '--green', 'latest_jobs');
        renderList('live-private-jobs', data.private_jobs, [], '--blue', 'private_jobs');
        renderList('live-remote-jobs', data.remote_jobs, [], '--dark', 'remote_jobs');
        renderList('live-admit-cards', data.admit_cards, manualData.admitcard, '--purple', 'admit_cards');
        renderList('live-results', data.results, manualData.results, '--red', 'results');
        
        setText('govt-jobs-count', `${(data.latest_jobs || []).length + (manualData.jobs || []).length} live`);
        setText('private-jobs-count', `${(data.private_jobs || []).length} live`);
        setText('remote-jobs-count', `${(data.remote_jobs || []).length} live`);


        // -------------------------
        // 2. Category Pages Logic
        // -------------------------
        
        // Helper to map scraped data (title, source, id) to the rich format
        const buildRichItem = (item, typeParams) => {
            let base = {
                id: item.id,
                t: item.title,
                org: 'Live Update (' + (item.source || 'Scraped') + ')',
                cat: 'Live',
                st: item.state_label || item.state || 'All India',
                ico: typeParams.ico || '🔥',
                bg: '#FEF2F2',
                url: buildPostUrl(item, typeParams.category),
                appDisp: item.applicant_count_display || '',
                appLabel: item.applicant_metric_label || '',
                appNote: item.applicant_metric_note || '',
                note: 'Scraped successfully. Click to view local details.'
            };
            return Object.assign(base, typeParams.extra);
        };

        // If on Latest Jobs page
        if (typeof JOBS !== 'undefined' && typeof applyAll === 'function') {
            if (manualData.jobs && manualData.jobs.length > 0) {
                const mappedManual = manualData.jobs.map(item => ({
                    id: item.id, t: item.title, org: item.org || 'Official', cat: item.cat || 'Job', 
                    st: item.state || 'All India', ico: '💼', bg: '#FFF3EB', url: item.url || buildPostUrl(item, 'jobs'),
                    vac: item.vac || 0, lastDate: item.lastDate || 'Asified', bdg: item.badge, note: item.note
                }));
                JOBS.unshift(...mappedManual);
            }
            if (data.latest_jobs) {
                const mapped = data.latest_jobs.map(item => buildRichItem(item, {
                    ico: '💼',
                    category: 'latest_jobs',
                    extra: {
                        bdg: 'hot', type: 'Govt Job', qual: 'See post', edu: 'See post', age: 'See post',
                        fee: 'See post', sal: 'See post', as: 'Live update', ld: 'See post', ed: 'As notified',
                        vac: 0, date: 'Apply Now'
                    }
                }));
                JOBS.unshift(...mapped);
            }
            applyAll();
        }

        // If on Results page
        if (typeof RESULTS !== 'undefined' && typeof applyAll === 'function') {
            if (manualData.results && manualData.results.length > 0) {
                const mappedManual = manualData.results.map(item => ({
                    id: item.id, t: item.title, org: item.org || 'Official', cat: item.cat || 'Result', 
                    st: 'All India', ico: '🏆', bg: '#F0FDF4', url: item.url || buildPostUrl(item, 'results'),
                    status: 'OUT', badge: item.badge || 'out', type: item.type || 'Result', cutoff: item.cutoff || 'Available', date: item.date || 'Just Now'
                }));
                RESULTS.unshift(...mappedManual);
            }
            if (data.results) {
                const mapped = data.results.map(item => buildRichItem(item, {
                    ico: '🏆',
                    category: 'results',
                    extra: { status: 'OUT', badge: 'out', type: 'Result', cutoff: 'Available', date: 'Just Now' }
                }));
                RESULTS.unshift(...mapped);
            }
            applyAll();
        }

        // If on Admit Card page
        if (typeof CARDS !== 'undefined' && typeof applyAll === 'function') {
            if (manualData.admitcard && manualData.admitcard.length > 0) {
                const mappedManual = manualData.admitcard.map(item => ({
                    id: item.id, t: item.title, org: item.org || 'Official', cat: item.cat || 'Updates', 
                    st: 'All India', ico: '🎟️', bg: '#F5F3FF', url: item.url || buildPostUrl(item, 'admitcard'),
                    status: item.status || 'OUT', badge: 'out', examDate: item.examDate || 'Check specific notice', releaseDate: item.relDate || 'Just Now'
                }));
                CARDS.unshift(...mappedManual);
            }
            if (data.admit_cards) {
                const mapped = data.admit_cards.map(item => buildRichItem(item, {
                    ico: '🎟️',
                    category: 'admit_cards',
                    extra: { status: 'OUT', badge: 'out', examDate: 'Live Update', releaseDate: 'Just Now' }
                }));
                CARDS.unshift(...mapped);
            }
            applyAll();
        }

        // If on Answer Key page
        if (typeof AK !== 'undefined' && typeof applyAll === 'function') {
            if (manualData.answerkey && manualData.answerkey.length > 0) {
                const mappedManual = manualData.answerkey.map(item => ({
                    id: item.id, t: item.title, org: item.org || 'Official', cat: item.cat || 'Updates', 
                    st: 'All India', ico: '🔑', bg: '#FEF2F2', url: item.url || buildPostUrl(item, 'answerkey'),
                    keytype: item.keytype || 'FINAL', badge: 'new', objDate: item.objDate || 'Closed', objUrl: ''
                }));
                AK.unshift(...mappedManual);
            }
            if (data.answer_keys) {
                const mapped = data.answer_keys.map(item => buildRichItem(item, {
                    ico: '🔑',
                    category: 'answer_keys',
                    extra: { keytype: 'FINAL', badge: 'new', objDate: 'Closed', objUrl: '' }
                }));
                AK.unshift(...mapped);
            }
            applyAll();
        }

      })
      .catch(error => {
        console.error('Error fetching live data:', error);
      });
  });
