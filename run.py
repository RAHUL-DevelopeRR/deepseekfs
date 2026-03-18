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
    time.sleep(3)  # Wait for API to fully start
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
                html, body { width:100%; height:100%; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                    max-width: 900px;
                    max-height: 85vh;
                    padding: 40px;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }
                h1 { color:#333; margin-bottom:6px; font-size:30px; }
                .subtitle { color:#888; font-size:13px; margin-bottom:16px; }
                .status-bar {
                    background: #f0f7ff;
                    border: 1px solid #c8e0ff;
                    border-radius: 8px;
                    padding: 10px 14px;
                    font-size: 12px;
                    color: #3a6fc4;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    min-height: 24px;
                }
                .dot { width:8px; height:8px; background:#3a6fc4; border-radius:50%; animation: pulse 1.5s infinite; }
                @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
                .search-box { display:flex; gap:10px; margin-bottom:20px; }
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
                button:active { transform:translateY(0); }
                .results { display:flex; flex-direction:column; gap:10px; overflow-y:auto; flex:1; }
                .result-item {
                    padding:12px 16px;
                    background:#f7f7f7; border-radius:8px;
                    border-left:4px solid #667eea; cursor:pointer;
                    transition:background 0.2s;
                }
                .result-item:hover { background:#efefef; }
                .result-name { font-weight:600; color:#333; font-size:14px; }
                .result-path { font-size:11px; color:#aaa; margin-top:3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                .result-scores { display:flex; gap:14px; margin-top:6px; font-size:11px; color:#666; flex-wrap:wrap; }
                .loading { text-align:center; padding:20px; color:#aaa; }
                .error { color:#c62828; background:#ffebee; padding:10px; border-radius:6px; font-size:12px; }
            </style>
        </head>
        <body>
        <div class="container">
            <h1>\ud83d\udd0d DeepSeekFS</h1>
            <p class="subtitle">Elite semantic file search engine</p>
            <div class="status-bar"><div class="dot"></div><span id="status">Connecting...</span></div>
            <div class="search-box">
                <input type="text" id="query" placeholder="Search: 'SWOT analysis', 'python project', 'resume'..."
                    onkeypress="if(event.key==='Enter') search()" autofocus>
                <button onclick="search()">Search</button>
            </div>
            <div id="results" class="results"></div>
        </div>
        <script>
            const API = 'http://localhost:8000';
            let statusUpdateInterval = null;

            async function updateStatus() {
                try {
                    const r = await fetch(API + '/health');
                    if (!r.ok) throw new Error('API returned ' + r.status);
                    const d = await r.json();
                    const stats = d.index_stats || {};
                    const count = stats.total_documents || 0;
                    document.getElementById('status').textContent = count > 0
                        ? '\ud83d\udcc4 ' + count + ' files indexed'
                        : '\u23f3 Indexing in progress...';
                } catch(e) {
                    document.getElementById('status').textContent = '\u26a0\ufe0f API connecting...';
                }
            }

            async function search() {
                const query = document.getElementById('query').value.trim();
                if (!query) return;
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<div class="loading">\u23f3 Searching...</div>';
                try {
                    const r = await fetch(API + '/search/', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query, top_k: 10, use_time_ranking: true})
                    });
                    if (!r.ok) throw new Error('Search failed: ' + r.status);
                    const data = await r.json();
                    if (!data.results || data.results.length === 0) {
                        resultsDiv.innerHTML = '<div class="loading">No results found. Indexing may still be running.</div>';
                        return;
                    }
                    resultsDiv.innerHTML = data.results.map(res => `
                        <div class="result-item" onclick="openFile('${res.path.replace(/\\/g, '\\\\').replace(/'/g, \"\\\"\")}')"
                            title="${res.path}">
                            <div style="display:flex;align-items:center;gap:8px">
                                <span style="background:#e8e8ff;color:#3a3a7a;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">${res.extension}</span>
                                <span class="result-name">${res.name}</span>
                            </div>
                            <div class="result-path">${res.path}</div>
                            <div class="result-scores">
                                <span>\ud83d\udcca Score: ${(res.combined_score*100).toFixed(1)}%</span>
                                <span>\ud83e\udde0 Semantic: ${(res.semantic_score*100).toFixed(1)}%</span>
                                <span>\u23f1\ufe0f Time: ${(res.time_score*100).toFixed(1)}%</span>
                            </div>
                        </div>
                    `).join('');
                } catch(e) {
                    resultsDiv.innerHTML = '<div class="error">Error: ' + e.message + '</div>';
                }
            }

            // Update status every 2 seconds
            updateStatus();
            statusUpdateInterval = setInterval(updateStatus, 2000);

            function openFile(path) {
                fetch(API + '/open?path=' + encodeURIComponent(path)).catch(() => {});
            }
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
        logger.info(f"Open browser: http://localhost:{config.API_PORT}")
        return False
    return True


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    ui_running = start_ui()
    if not ui_running:
        # No GUI available — keep the API server alive
        logger.info("Running in headless mode. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down.")
