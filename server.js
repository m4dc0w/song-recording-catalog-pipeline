import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;

function getFileList(dir, base = '') {
  const results = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name === '.git') continue;
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

  // Serve Main Dashboard
  const files = getFileList(__dirname);
  const pythonFiles = files.filter(f => f.name.endsWith('.py'));
  const envExists = fs.existsSync(path.join(__dirname, '.env'));
  const envExampleExists = fs.existsSync(path.join(__dirname, '.env.example'));

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Song Recording Catalog Pipeline</title>
  <meta property="og:title" content="Song Recording Catalog Pipeline">
  <meta name="description" content="Audio segmentation and cataloging pipeline syncing with Planning Center and Gemini.">
  <meta property="og:description" content="Audio segmentation and cataloging pipeline syncing with Planning Center and Gemini.">
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
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      padding: 32px 20px;
      line-height: 1.5;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 16px;
    }
    .title-group h1 {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #fff;
    }
    .title-group p {
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }
    .badge-live {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(34, 197, 94, 0.15);
      color: var(--success);
      border: 1px solid rgba(34, 197, 94, 0.3);
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-live::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 8px var(--success);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }
    .card h2 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 12px;
    }
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: #fff;
    }
    .stat-desc {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .section-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .file-list {
      list-style: none;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 28px;
    }
    .file-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 18px;
      border-bottom: 1px solid var(--border);
      font-size: 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .file-item:last-child {
      border-bottom: none;
    }
    .file-tag {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
    }
    .instructions {
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      font-size: 14px;
    }
    .instructions h3 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 8px;
      color: #fff;
    }
    .instructions p {
      color: var(--text-muted);
      margin-bottom: 12px;
    }
    pre {
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      color: #38bdf8;
      overflow-x: auto;
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>Song Recording Catalog Pipeline</h1>
        <p>GitHub Repository: <strong>m4dc0w/song-recording-catalog-pipeline</strong></p>
      </div>
      <div class="badge-live">Dev Server Active</div>
    </header>

    <div class="grid">
      <div class="card">
        <h2>Python Modules</h2>
        <div class="stat-value">${pythonFiles.length}</div>
        <div class="stat-desc">Python source & test files active</div>
      </div>
      <div class="card">
        <h2>Environment Status</h2>
        <div class="stat-value" style="font-size: 20px; color: ${envExists ? 'var(--success)' : 'var(--warning)'}; padding-top: 6px;">
          ${envExists ? 'Configured (.env)' : '.env.example Available'}
        </div>
        <div class="stat-desc">${envExists ? '.env configured' : 'Config template updated'}</div>
      </div>
      <div class="card">
        <h2>GitHub Sync</h2>
        <div class="stat-value" style="font-size: 20px; color: var(--accent); padding-top: 6px;">
          Ready to Sync
        </div>
        <div class="stat-desc">Changes can be committed via AI Studio</div>
      </div>
    </div>

    <div class="section-title">
      <span>Active Repository Files</span>
    </div>
    <ul class="file-list">
      ${pythonFiles.map(f => `
        <li class="file-item">
          <span>📄 ${f.name}</span>
          <span class="file-tag">Python</span>
        </li>
      `).join('')}
      <li class="file-item">
        <span>⚙️ .env.example</span>
        <span class="file-tag">Config</span>
      </li>
      <li class="file-item">
        <span>📖 README.md</span>
        <span class="file-tag">Docs</span>
      </li>
    </ul>

    <div class="instructions">
      <h3>Local Pipeline Execution</h3>
      <p>This repository is designed to run locally with Python 3 and FFmpeg for processing audio recordings:</p>
      <pre># 1. Install dependencies
pip install python-dotenv requests google-genai

# 2. Configure environment
cp .env.example .env

# 3. Run the orchestrator
python pipeline_orchestrator.py</pre>
    </div>
  </div>
</body>
</html>`;

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Development server running on http://0.0.0.0:${PORT}`);
});
