import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const PORT = 3000;

function getFileList(dir, base = '') {
  const results = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name === '.git' || entry.name.startsWith('.')) {
        if (entry.name !== '.env.example' && entry.name !== '.gitignore') continue;
      }
      const relative = path.join(base, entry.name);
      if (entry.isDirectory()) {
        results.push({ name: relative, type: 'directory' });
        results.push(...getFileList(path.join(dir, entry.name), relative));
      } else {
        results.push({ name: relative, type: 'file' });
      }
    }
  } catch (err) {
    console.error('Error scanning directory:', err);
  }
  return results;
}

function fetchRemote(filePath, branch, res) {
  const repoUrl = `https://raw.githubusercontent.com/m4dc0w/song-recording-catalog-pipeline/${branch}/${filePath}`;
  const options = {};
  if (process.env.GITHUB_PAT) {
    options.headers = {
      'Authorization': `token ${process.env.GITHUB_PAT}`
    };
  }
  https.get(repoUrl, options, (githubRes) => {
    if (githubRes.statusCode === 404 && branch === 'main') {
      // Fallback to master if main doesn't exist
      fetchRemote(filePath, 'master', res);
      return;
    }
    if (githubRes.statusCode === 404) {
      res.writeHead(404);
      res.end('');
      return;
    }
    let data = '';
    githubRes.on('data', chunk => { data += chunk; });
    githubRes.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(data);
    });
  }).on('error', (err) => {
    res.writeHead(500);
    res.end(err.message);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', time: new Date().toISOString() }));
    return;
  }

  if (url.pathname === '/api/files') {
    const files = getFileList(__dirname);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ files }));
    return;
  }

  if (url.pathname === '/api/local') {
    const filePath = url.searchParams.get('path');
    try {
      const content = fs.readFileSync(path.join(__dirname, filePath), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(content);
    } catch (err) {
      res.writeHead(404);
      res.end('');
    }
    return;
  }

  if (url.pathname === '/api/remote') {
    const filePath = url.searchParams.get('path');
    fetchRemote(filePath, 'main', res);
    return;
  }

  // Serve Main Dashboard & Diff Viewer
  const files = getFileList(__dirname);
  const pythonFiles = files.filter(f => f.name.endsWith('.py'));
  const envExists = fs.existsSync(path.join(__dirname, '.env'));

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Song Recording Catalog Pipeline</title>
  
  <!-- CSS for Diff2Html -->
  <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/diff2html/bundles/css/diff2html.min.css" />
  
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0ea5e9;
      --success: #22c55e;
      --warning: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      padding: 32px 20px;
      line-height: 1.5;
    }
    .container { max-width: 900px; margin: 0 auto; }
    header {
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 16px;
    }
    .title-group h1 { font-size: 24px; font-weight: 700; color: #fff; }
    .title-group p { color: var(--text-muted); font-size: 14px; margin-top: 4px; }
    
    /* Tabs */
    .tabs {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      padding: 8px 16px;
      border-radius: 6px;
      transition: background 0.2s, color 0.2s;
    }
    .tab-btn:hover { background: rgba(255,255,255,0.05); color: #fff; }
    .tab-btn.active {
      background: var(--card-bg);
      color: var(--accent);
      border: 1px solid var(--border);
    }
    
    .tab-content { display: none; }
    .tab-content.active { display: block; }

    /* Dashboard Styles */
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    .card h2 { font-size: 15px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px; }
    .stat-value { font-size: 28px; font-weight: 700; color: #fff; }
    .stat-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
    
    .file-list { list-style: none; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 28px; }
    .file-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 18px; border-bottom: 1px solid var(--border); font-size: 14px; font-family: monospace; }
    .file-item:last-child { border-bottom: none; }
    
    /* Diff Styles */
    #diff-container { margin-top: 16px; }
    .d2h-file-header { background-color: var(--card-bg) !important; color: #fff !important; border-color: var(--border) !important; }
    .d2h-file-wrapper { border-color: var(--border) !important; border-radius: 8px; overflow: hidden; }
    .loading { color: var(--accent); font-weight: 600; font-size: 16px; padding: 20px; text-align: center; }
    .no-changes { text-align: center; color: var(--success); font-size: 18px; padding: 40px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; }
    
    /* Diff2Html dark mode overrides */
    .d2h-code-line { color: #fff; }
    .d2h-del { background-color: rgba(248, 113, 113, 0.2) !important; border-color: rgba(248, 113, 113, 0.3) !important; }
    .d2h-ins { background-color: rgba(74, 222, 128, 0.2) !important; border-color: rgba(74, 222, 128, 0.3) !important; }
    .d2h-info { background-color: rgba(56, 189, 248, 0.1) !important; color: var(--text-muted) !important; }
    .d2h-emptyplaceholder { background-color: transparent !important; }
    .d2h-code-line-ctn { color: #cbd5e1 !important; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>Code Review & Dashboard</h1>
        <p>Sync Target: <strong>m4dc0w/song-recording-catalog-pipeline</strong></p>
      </div>
    </header>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('dashboard')">Dashboard</button>
      <button class="tab-btn" onclick="switchTab('diffs')">Diff Viewer (Review PR)</button>
    </div>

    <!-- Dashboard Tab -->
    <div id="tab-dashboard" class="tab-content active">
      <div class="grid">
        <div class="card">
          <h2>Python Modules</h2>
          <div class="stat-value">${pythonFiles.length}</div>
          <div class="stat-desc">Python source files active</div>
        </div>
        <div class="card">
          <h2>Environment Status</h2>
          <div class="stat-value" style="font-size: 20px; color: ${envExists ? 'var(--success)' : 'var(--warning)'}; padding-top: 6px;">
            ${envExists ? 'Configured (.env)' : '.env.example Available'}
          </div>
        </div>
        <div class="card">
          <h2>Code Review</h2>
          <div class="stat-value" style="font-size: 20px; color: var(--accent); padding-top: 6px; cursor: pointer" onclick="switchTab('diffs')">
            Review Changes &rarr;
          </div>
          <div class="stat-desc">Visually inspect edits</div>
        </div>
      </div>
      
      <h3 style="margin-bottom:12px;font-size:16px;">Active Files</h3>
      <ul class="file-list">
        ${files.filter(f => f.type === 'file').slice(0, 10).map(f => `
          <li class="file-item">
            <span>📄 ${f.name}</span>
          </li>
        `).join('')}
        ${files.length > 10 ? '<li class="file-item"><span>... and more</span></li>' : ''}
      </ul>
    </div>

    <!-- Diff Viewer Tab -->
    <div id="tab-diffs" class="tab-content">
      <p style="color: var(--text-muted); margin-bottom: 20px;">
        Comparing local workspace modifications against the remote GitHub repository default branch.
      </p>
      <div id="diff-loading" class="loading" style="display: none;">Generating line-by-line diffs...</div>
      <div id="diff-container"></div>
    </div>
  </div>

  <!-- JS Dependencies for Diff -->
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/diff@5.1.0/dist/diff.min.js"></script>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/diff2html/bundles/js/diff2html-ui.min.js"></script>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      
      document.getElementById('tab-' + tabId).classList.add('active');
      event.currentTarget.classList.add('active');
      
      if (tabId === 'diffs') {
        loadDiffs();
      }
    }

    async function loadDiffs() {
      const container = document.getElementById('diff-container');
      const loader = document.getElementById('diff-loading');
      
      // If we already loaded it, don't reload unless empty
      if (container.innerHTML.trim() !== '' && !container.innerHTML.includes('No changes')) {
        return; 
      }
      
      loader.style.display = 'block';
      container.innerHTML = '';

      try {
        const filesRes = await fetch('/api/files');
        const { files } = await filesRes.json();
        const fileList = files.filter(f => f.type === 'file');

        let unifiedDiffs = '';

        for (const file of fileList) {
          const path = file.name;
          // Skip known binary types
          if (path.endsWith('.wav') || path.endsWith('.mp3') || path.endsWith('.pyc')) continue;

          const [localRes, remoteRes] = await Promise.all([
            fetch('/api/local?path=' + encodeURIComponent(path)),
            fetch('/api/remote?path=' + encodeURIComponent(path))
          ]);

          const localTextRaw = localRes.ok ? await localRes.text() : '';
          const remoteTextRaw = remoteRes.ok ? await remoteRes.text() : '';

          // Normalize line endings to prevent "all lines changed" issue
          const localText = localTextRaw.replace(/\\r\\n/g, '\\n');
          const remoteText = remoteTextRaw.replace(/\\r\\n/g, '\\n');

          if (localText === remoteText) continue; // No changes detected

          // Create unified diff string using jsdiff
          const patch = Diff.createTwoFilesPatch(
            path, 
            path, 
            remoteText, 
            localText, 
            undefined, 
            undefined
          );
          unifiedDiffs += patch + '\\n';
        }

        loader.style.display = 'none';

        if (!unifiedDiffs.trim()) {
          container.innerHTML = '<div class="no-changes">✅ No local changes detected. Your workspace is synced with GitHub.</div>';
          return;
        }

        // Render the diff using diff2html
        const diff2htmlUi = new Diff2HtmlUI(container, unifiedDiffs, {
          drawFileList: true,
          matching: 'lines',
          outputFormat: 'line-by-line',
          colorScheme: 'dark' // If supported by the bundle
        });
        diff2htmlUi.draw();
        diff2htmlUi.highlightCode();

      } catch (err) {
        loader.style.display = 'none';
        container.innerHTML = '<div class="no-changes" style="color: var(--warning)">Failed to load diffs: ' + err.message + '</div>';
      }
    }
  </script>
</body>
</html>`;

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('Development server running on http://0.0.0.0:' + PORT);
});
