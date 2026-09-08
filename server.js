import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import * as dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const PORT = 3000;

function getGitBlobSha(filePath, size) {
  try {
    const hash = crypto.createHash('sha1');
    hash.update(`blob ${size}\0`);
    const fd = fs.openSync(filePath, 'r');
    const buffer = Buffer.alloc(65536);
    let bytesRead;
    while ((bytesRead = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) {
      hash.update(buffer.subarray(0, bytesRead));
    }
    fs.closeSync(fd);
    return hash.digest('hex');
  } catch {
    return null;
  }
}

function getFileList(dir, base = '') {
  const results = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name === '.git' || entry.name === '__pycache__' || entry.name.startsWith('.')) {
        if (entry.name !== '.env.example' && entry.name !== '.gitignore') continue;
      }
      const relative = path.join(base, entry.name);
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push({ name: relative, type: 'directory' });
        results.push(...getFileList(fullPath, relative));
      } else {
        try {
          const stat = fs.statSync(fullPath);
          const sha = getGitBlobSha(fullPath, stat.size);
          results.push({ name: relative, type: 'file', size: stat.size, sha });
        } catch {
          results.push({ name: relative, type: 'file' });
        }
      }
    }
  } catch (err) {
    console.error('Error scanning directory:', err);
  }
  return results;
}

function fetchRemote(filePath, branch, res) {
  const repo = process.env.GITHUB_REPOSITORY || 'm4dc0w/song-recording-catalog-pipeline';
  const repoUrl = `https://raw.githubusercontent.com/${repo}/${branch}/${filePath}`;
  const options = {
    headers: {
      'User-Agent': 'Node-Server'
    }
  };
  if (process.env.GITHUB_PAT) {
    options.headers['Authorization'] = `token ${process.env.GITHUB_PAT}`;
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
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(data);
    });
  }).on('error', (err) => {
    res.writeHead(500);
    res.end(err.message);
  });
}

function fetchRemoteFiles(branch, callback) {
  const repo = process.env.GITHUB_REPOSITORY || 'm4dc0w/song-recording-catalog-pipeline';
  const apiUrl = `https://api.github.com/repos/${repo}/git/trees/${branch}?recursive=1`;
  const options = {
    headers: {
      'User-Agent': 'Node-Server'
    }
  };
  if (process.env.GITHUB_PAT) {
    options.headers['Authorization'] = `token ${process.env.GITHUB_PAT}`;
  }
  https.get(apiUrl, options, (githubRes) => {
    if (githubRes.statusCode === 404 && branch === 'main') {
      // Fallback to master if main doesn't exist
      fetchRemoteFiles('master', callback);
      return;
    }
    let data = '';
    githubRes.on('data', chunk => { data += chunk; });
    githubRes.on('end', () => {
      try {
        if (githubRes.statusCode >= 200 && githubRes.statusCode < 300) {
          const parsed = JSON.parse(data);
          const files = (parsed.tree || [])
            .filter(item => item.type === 'blob')
            .filter(item => {
              const p = item.path;
              if (p === '.git' || p.startsWith('.git/') || p.startsWith('node_modules/') || p.includes('__pycache__')) return false;
              if (p.startsWith('.') && p !== '.env.example' && p !== '.gitignore') return false;
              return true;
            })
            .map(item => ({ name: item.path, type: 'file', size: item.size, sha: item.sha }));
          callback(null, files);
        } else {
          callback(new Error(`GitHub API returned status ${githubRes.statusCode}`));
        }
      } catch (e) {
        callback(e);
      }
    });
  }).on('error', (err) => {
    callback(err);
  });
}

const clientScript = String.raw`
function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(el) { el.classList.remove('active'); });
  
  var targetTab = document.getElementById('tab-' + tabId);
  if (targetTab) {
    targetTab.classList.add('active');
  }
  
  var activeBtn = btn;
  if (!activeBtn && typeof window !== 'undefined' && window.event && window.event.currentTarget && window.event.currentTarget.classList) {
    activeBtn = window.event.currentTarget;
  }
  if (!activeBtn && typeof document !== 'undefined') {
    activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(function(b) {
      return b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId);
    });
  }
  if (activeBtn && activeBtn.classList) {
    activeBtn.classList.add('active');
  }
  
  if (tabId === 'diffs') {
    loadDiffs();
  }
}

async function loadDiffs(force = false) {
  const container = document.getElementById('diff-container');
  const loader = document.getElementById('diff-loading');
  
  if (!container || !loader) return;

  // If we already loaded it and not forced, don't reload unless empty
  if (!force && container.innerHTML.trim() !== '' && !container.innerHTML.includes('No changes')) {
    return; 
  }
  
  loader.style.display = 'block';
  container.innerHTML = '';

  try {
    const [filesRes, remoteFilesRes] = await Promise.all([
      fetch('/api/files'),
      fetch('/api/remote-files')
    ]);
    const localData = await filesRes.json();
    const remoteData = remoteFilesRes.ok ? await remoteFilesRes.json() : { files: [] };

    const localFiles = (localData.files || []).filter(f => f.type === 'file');
    const remoteFiles = (remoteData.files || []).filter(f => f.type === 'file');

    const localFileMap = new Map(localFiles.map(f => [f.name, f]));
    const remoteFileMap = new Map(remoteFiles.map(f => [f.name, f]));

    // Union of all unique paths across local workspace and remote repository
    const allPaths = Array.from(new Set([...localFileMap.keys(), ...remoteFileMap.keys()])).sort();

    let unifiedDiffs = '';
    const stats = { added: 0, modified: 0, deleted: 0, binary: 0 };

    function isBinaryFile(filePath) {
      const binaryExtensions = [
        '.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma',
        '.mp4', '.mov', '.avi', '.mkv', '.webm',
        '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.svgz', '.bmp', '.tiff',
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe',
        '.zip', '.tar', '.gz', '.tgz', '.bz2', '.7z', '.rar',
        '.woff', '.woff2', '.ttf', '.eot', '.otf',
        '.pdf', '.bin', '.dat'
      ];
      const lower = filePath.toLowerCase();
      return binaryExtensions.some(function(ext) { return lower.endsWith(ext); });
    }

    for (const path of allPaths) {
      // Skip node_modules and .git internals
      if (path.startsWith('node_modules/') || path.startsWith('.git/') || path.includes('__pycache__')) continue;

      const hasLocal = localFileMap.has(path);
      const hasRemote = remoteFileMap.has(path);
      const localFile = localFileMap.get(path);
      const remoteFile = remoteFileMap.get(path);

      // Handle binary files without downloading large raw binary streams
      if (isBinaryFile(path)) {
        if (hasRemote && !hasLocal) {
          stats.deleted++;
          stats.binary++;
          unifiedDiffs += 'diff --git a/' + path + ' b/' + path + '\ndeleted file mode 100644\nBinary files a/' + path + ' and /dev/null differ\n\n';
        } else if (hasLocal && !hasRemote) {
          stats.added++;
          stats.binary++;
          unifiedDiffs += 'diff --git a/' + path + ' b/' + path + '\nnew file mode 100644\nBinary files /dev/null and b/' + path + ' differ\n\n';
        } else {
          // Both exist: check if modified via Git blob SHA or size
          const isDifferent = (localFile && remoteFile && localFile.sha && remoteFile.sha)
            ? (localFile.sha !== remoteFile.sha)
            : (localFile && remoteFile && typeof localFile.size === 'number' && typeof remoteFile.size === 'number' && localFile.size !== remoteFile.size);
          if (isDifferent) {
            stats.modified++;
            stats.binary++;
            unifiedDiffs += 'diff --git a/' + path + ' b/' + path + '\nBinary files a/' + path + ' and b/' + path + ' differ\n\n';
          }
        }
        continue;
      }

      // Fast check: if both exist and Git blob SHA matches, content is 100% identical
      if (hasLocal && hasRemote && localFile && remoteFile && localFile.sha && remoteFile.sha && localFile.sha === remoteFile.sha) {
        continue;
      }

      const [localRes, remoteRes] = await Promise.all([
        hasLocal ? fetch('/api/local?path=' + encodeURIComponent(path)) : Promise.resolve(null),
        hasRemote ? fetch('/api/remote?path=' + encodeURIComponent(path)) : Promise.resolve(null)
      ]);

      const localTextRaw = (localRes && localRes.ok) ? await localRes.text() : '';
      const remoteTextRaw = (remoteRes && remoteRes.ok) ? await remoteRes.text() : '';

      // Normalize line endings to prevent "all lines changed" issue
      const localText = localTextRaw.replace(/\r\n/g, '\n');
      const remoteText = remoteTextRaw.replace(/\r\n/g, '\n');

      if (hasLocal && hasRemote && localText === remoteText) {
        continue; // No changes detected
      }

      if (hasRemote && !hasLocal) {
        // Case 1: DELETED FILE (exists remotely on GitHub, deleted in local workspace)
        stats.deleted++;
        const patch = Diff.createPatch(path, remoteText, '');
        const hunkLines = patch.split('\n').slice(4).join('\n');
        const gitDiff = 'diff --git a/' + path + ' b/' + path + '\ndeleted file mode 100644\n--- a/' + path + '\n+++ /dev/null\n' + hunkLines + '\n';
        unifiedDiffs += gitDiff + '\n';
      } else if (hasLocal && !hasRemote) {
        // Case 2: ADDED FILE (created in local workspace, missing in remote repository)
        stats.added++;
        const patch = Diff.createPatch(path, '', localText);
        const hunkLines = patch.split('\n').slice(4).join('\n');
        const gitDiff = 'diff --git a/' + path + ' b/' + path + '\nnew file mode 100644\n--- /dev/null\n+++ b/' + path + '\n' + hunkLines + '\n';
        unifiedDiffs += gitDiff + '\n';
      } else {
        // Case 3: MODIFIED FILE (exists in both, content changed)
        stats.modified++;
        const patch = Diff.createPatch(path, remoteText, localText);
        const hunkLines = patch.split('\n').slice(4).join('\n');
        const gitDiff = 'diff --git a/' + path + ' b/' + path + '\n--- a/' + path + '\n+++ b/' + path + '\n' + hunkLines + '\n';
        unifiedDiffs += gitDiff + '\n';
      }
    }

    loader.style.display = 'none';

    if (!unifiedDiffs.trim()) {
      container.innerHTML = '<div class="no-changes">✅ No local changes detected. Your workspace is synced with GitHub.</div>';
      return;
    }

    // Summary bar above diffs
    const badges = [];
    if (stats.modified > 0) badges.push('<span style="color: #38bdf8;">✎ ' + stats.modified + ' Modified</span>');
    if (stats.added > 0) badges.push('<span style="color: #4ade80;">✚ ' + stats.added + ' Added</span>');
    if (stats.deleted > 0) badges.push('<span style="color: #f87171;">✖ ' + stats.deleted + ' Deleted</span>');
    if (stats.binary > 0) badges.push('<span style="color: #a78bfa;">📦 ' + stats.binary + ' Binary</span>');

    const summaryBar = badges.length > 0 ? '<div style="display: flex; gap: 16px; margin-bottom: 16px; font-size: 14px; font-weight: 600; padding: 12px 16px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;">' + badges.join('') + '</div>' : '';

    container.innerHTML = summaryBar + '<div id="diff2html-target"></div>';

    // Render the diff using diff2html
    const diffTarget = document.getElementById('diff2html-target');
    const diff2htmlUi = new Diff2HtmlUI(diffTarget, unifiedDiffs, {
      drawFileList: true,
      matching: 'lines',
      outputFormat: 'line-by-line',
      colorScheme: 'dark'
    });
    diff2htmlUi.draw();
    diff2htmlUi.highlightCode();

  } catch (err) {
    loader.style.display = 'none';
    container.innerHTML = '<div class="no-changes" style="color: var(--warning)">Failed to load diffs: ' + err.message + '</div>';
  }
}
`;

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', time: new Date().toISOString() }));
    return;
  }

  if (url.pathname === '/app.js') {
    res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8' });
    res.end(clientScript);
    return;
  }

  if (url.pathname === '/api/files') {
    const files = getFileList(__dirname);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ files }));
    return;
  }

  if (url.pathname === '/api/remote-files') {
    fetchRemoteFiles('main', (err, files) => {
      if (err) {
        console.warn('Could not fetch remote files:', err.message);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ files: [], warning: err.message }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ files }));
    });
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
    .d2h-file-wrapper { border-color: var(--border) !important; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }
    .loading { color: var(--accent); font-weight: 600; font-size: 16px; padding: 20px; text-align: center; }
    .no-changes { text-align: center; color: var(--success); font-size: 18px; padding: 40px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; }
    
    /* Diff2Html dark mode overrides */
    .d2h-code-line { color: #fff; }
    .d2h-del { background-color: rgba(248, 113, 113, 0.2) !important; border-color: rgba(248, 113, 113, 0.3) !important; }
    .d2h-ins { background-color: rgba(74, 222, 128, 0.2) !important; border-color: rgba(74, 222, 128, 0.3) !important; }
    .d2h-info { background-color: rgba(56, 189, 248, 0.1) !important; color: var(--text-muted) !important; }
    .d2h-emptyplaceholder { background-color: transparent !important; }
    .d2h-code-line-ctn { color: #cbd5e1 !important; }
    
    /* Diff2Html badges & file list */
    .d2h-tag { font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; margin-left: 8px; }
    .d2h-deleted-tag { background-color: rgba(248, 113, 113, 0.25) !important; color: #f87171 !important; border: 1px solid #f87171 !important; }
    .d2h-added-tag { background-color: rgba(74, 222, 128, 0.25) !important; color: #4ade80 !important; border: 1px solid #4ade80 !important; }
    .d2h-changed-tag { background-color: rgba(56, 189, 248, 0.25) !important; color: #38bdf8 !important; border: 1px solid #38bdf8 !important; }
    .d2h-file-list-wrapper { background-color: var(--card-bg) !important; border-color: var(--border) !important; border-radius: 8px; margin-bottom: 20px; }
    .d2h-file-list-header { color: var(--text) !important; border-bottom-color: var(--border) !important; }
    .d2h-file-list-line { color: var(--text-muted) !important; }
    .d2h-file-list-line a { color: var(--accent) !important; }
    .d2h-file-list-line:hover { background-color: rgba(255, 255, 255, 0.05) !important; }
    .d2h-lines-added { color: var(--success) !important; }
    .d2h-lines-deleted { color: #f87171 !important; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>Code Review & Dashboard</h1>
        <p>Sync Target: <strong>${process.env.GITHUB_REPOSITORY || 'm4dc0w/song-recording-catalog-pipeline'}</strong></p>
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
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <p style="color: var(--text-muted);">
          Comparing local workspace modifications against remote GitHub default branch.
        </p>
        <button class="tab-btn" style="background: var(--card-bg); border: 1px solid var(--border); font-size: 13px; padding: 6px 14px; color: #fff;" onclick="loadDiffs(true)">
          ⟳ Refresh Diffs
        </button>
      </div>
      <div id="diff-loading" class="loading" style="display: none;">Scanning local & remote repository files...</div>
      <div id="diff-container"></div>
    </div>
  </div>

  <!-- JS Dependencies for Diff -->
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/diff@5.1.0/dist/diff.min.js"></script>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/diff2html/bundles/js/diff2html-ui.min.js"></script>
  <script type="text/javascript" src="/app.js"></script>
</body>
</html>`;

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('Development server running on http://0.0.0.0:' + PORT);
});
