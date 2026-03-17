"""Application entry point"""
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import app.config as config
from app.logger import logger


def start_api():
    import uvicorn
    from app.main import app
    logger.info(f"Starting API on http://{config.API_HOST}:{config.API_PORT}")
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT, log_level="info")


def start_ui():
    time.sleep(2)  # Wait for API
    try:
        import webview

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>DeepSeekFS</title>
            <style>
                * { margin:0; padding:0; box-sizing:border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    width: 100%;
                    max-width: 860px;
                    padding: 40px;
                }
                h1 { color:#333; margin-bottom:6px; font-size:30px; }
                .subtitle { color:#888; font-size:13px; margin-bottom:6px; }
                .status-bar {
                    background: #f0f7ff;
                    border: 1px solid #c8e0ff;
                    border-radius: 8px;
                    padding: 8px 14px;
                    font-size: 12px;
                    color: #3a6fc4;
                    margin-bottom: 22px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .dot { width:8px; height:8px; background:#3a6fc4; border-radius:50%; animation: pulse 1.5s infinite; }
                @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
                .search-box { display:flex; gap:10px; margin-bottom:24px; }
                input {
                    flex:1; padding:12px 16px;
                    border:2px solid #e0e0e0; border-radius:8px;
                    font-size:15px; transition:border-color 0.3s;
                }
                input:focus { outline:none; border-color:#667eea; }
                button {
                    padding:12px 28px;
                    background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                    color:white; border:none; border-radius:8px;
                    font-size:15px; font-weight:600; cursor:pointer;
                    transition:transform 0.2s;
                }
                button:hover { transform:translateY(-2px); }
                .results { display:flex; flex-direction:column; gap:10px; max-height:420px; overflow-y:auto; }
                .result-item {
                    padding:12px 16px;
                    background:#f7f7f7; border-radius:8px;
                    border-left:4px solid #667eea; cursor:pointer;
                    transition:background 0.2s;
                }
                .result-item:hover { background:#efefef; }
                .result-name { font-weight:600; color:#333; font-size:14px; }
                .result-path { font-size:11px; color:#aaa; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
                .result-scores { display:flex; gap:14px; margin-top:6px; font-size:11px; color:#666; }
                .badge {
                    display:inline-block; padding:2px 8px;
                    border-radius:12px; font-size:10px; font-weight:600;
                    background:#ede9fe; color:#6d28d9;
                }
                .loading { text-align:center; padding:24px; color:#aaa; }
                .indexing-note {
                    background:#fff8e1; border:1px solid #ffe082;
                    border-radius:8px; padding:10px 14px;
                    font-size:12px; color:#856404; margin-bottom:16px;
                }
            </style>
        </head>
        <body>
        <div class="container">
            <h1>&#128269; DeepSeekFS</h1>
            <p class="subtitle">Elite semantic file search engine &mdash; powered by AI</p>

            <div class="status-bar">
                <div class="dot"></div>
                <span id="status">Checking index status...</span>
            </div>

            <div class="indexing-note" id="indexNote" style="display:none">
                &#9888;&#65039; Background indexing is in progress. Results will grow as more files are indexed.
            </div>

            <div class="search-box">
                <input
                    type="text" id="query"
                    placeholder="Search: 'invoice last week', 'python project', 'resume'..."
                    onkeypress="if(event.key==='Enter') search()"
                >
                <button onclick="search()">Search</button>
            </div>

            <div id="results" class="results"></div>
        </div>

        <script>
            const API = 'http://localhost:8000';

            async function updateStatus() {
                try {
                    const r = await fetch(`${API}/health`);
                    const d = await r.json();
                    const stats = d.index_stats;
                    const paths = (stats.watch_paths || []).join(', ');
                    document.getElementById('status').textContent =
                        `&#128196; ${stats.total_documents} files indexed  |  Watching: ${paths || 'scanning...'}` ;
                    if (stats.total_documents === 0) {
                        document.getElementById('indexNote').style.display = 'block';
                    }
                } catch(e) {
                    document.getElementById('status').textContent = 'API starting...';
                }
            }

            async function search() {
                const query = document.getElementById('query').value.trim();
                if (!query) return;
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<div class="loading">&#9203; Searching...</div>';
                try {
                    const r = await fetch(`${API}/search/`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query, top_k: 10, use_time_ranking: true})
                    });
                    const data = await r.json();
                    if (!data.results || data.results.length === 0) {
                        resultsDiv.innerHTML = '<div class="loading">No results found. Indexing may still be running.</div>';
                        return;
                    }
                    resultsDiv.innerHTML = data.results.map(res => `
                        <div class="result-item" onclick="openFile('${res.path.replace(/\\/g, '\\\\')}')">
                            <div style="display:flex;align-items:center;gap:8px">
                                <span class="badge">${res.extension}</span>
                                <span class="result-name">${res.name}</span>
                            </div>
                            <div class="result-path">${res.path}</div>
                            <div class="result-scores">
                                <span>&#128202; Combined: ${(res.combined_score*100).toFixed(1)}%</span>
                                <span>&#129504; Semantic: ${(res.semantic_score*100).toFixed(1)}%</span>
                                <span>&#8987;&#65039; Time: ${(res.time_score*100).toFixed(1)}%</span>
                                <span>&#128190; ${(res.size/1024).toFixed(1)} KB</span>
                            </div>
                        </div>
                    `).join('');
                } catch(e) {
                    resultsDiv.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
                }
            }

            function openFile(path) {
                // Opens file location via API
                fetch(`${API}/open?path=${encodeURIComponent(path)}`).catch(() => {});
            }

            // Update status every 5 seconds
            updateStatus();
            setInterval(updateStatus, 5000);

            window.addEventListener('load', () => document.getElementById('query').focus());
        </script>
        </body>
        </html>
        """

        webview.create_window(
            config.UI_TITLE, html=html,
            width=config.UI_WIDTH, height=config.UI_HEIGHT
        )
        webview.start()
    except Exception as e:
        logger.error(f"UI error: {e}")
        logger.info(f"Open browser manually: http://localhost:{config.API_PORT}/docs")


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    start_ui()
