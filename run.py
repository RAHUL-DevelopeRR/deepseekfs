"""Application entry point"""
import sys
import os
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import app.config as config
from app.logger import logger

def start_api():
    """Start FastAPI server"""
    import uvicorn
    from app.main import app
    
    logger.info(f"Starting API on http://{config.API_HOST}:{config.API_PORT}")
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info"
    )

def start_ui():
    """Start PyWebView UI"""
    time.sleep(2)  # Wait for API to start
    
    try:
        import webview
        from app.config import UI_TITLE, UI_WIDTH, UI_HEIGHT
        
        logger.info("Starting PyWebView UI...")
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>DeepSeekFS</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
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
                    max-width: 800px;
                    padding: 40px;
                }
                h1 {
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 32px;
                }
                .subtitle {
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 30px;
                }
                .search-box {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 30px;
                }
                input {
                    flex: 1;
                    padding: 12px 16px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 16px;
                    transition: border-color 0.3s;
                }
                input:focus {
                    outline: none;
                    border-color: #667eea;
                }
                button {
                    padding: 12px 32px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s;
                }
                button:hover {
                    transform: translateY(-2px);
                }
                button:active {
                    transform: translateY(0);
                }
                .results {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .result-item {
                    padding: 12px 16px;
                    background: #f5f5f5;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                    cursor: pointer;
                    transition: background 0.2s;
                }
                .result-item:hover {
                    background: #efefef;
                }
                .result-name {
                    font-weight: 600;
                    color: #333;
                    font-size: 14px;
                }
                .result-meta {
                    font-size: 12px;
                    color: #999;
                    margin-top: 4px;
                }
                .result-scores {
                    display: flex;
                    gap: 15px;
                    margin-top: 6px;
                    font-size: 11px;
                }
                .loading {
                    text-align: center;
                    padding: 20px;
                    color: #999;
                }
                .error {
                    padding: 12px 16px;
                    background: #ffebee;
                    color: #c62828;
                    border-radius: 8px;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔍 DeepSeekFS</h1>
                <p class="subtitle">Elite semantic file search engine</p>
                
                <div class="search-box">
                    <input 
                        type="text" 
                        id="query" 
                        placeholder="Search files... (e.g., 'invoice from last week', 'python projects')"
                        onkeypress="if(event.key==='Enter') search()"
                    >
                    <button onclick="search()">Search</button>
                </div>
                
                <div id="results" class="results"></div>
            </div>
            
            <script>
                async function search() {
                    const query = document.getElementById('query').value;
                    if (!query.trim()) return;
                    
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.innerHTML = '<div class="loading">⏳ Searching...</div>';
                    
                    try {
                        const response = await fetch('http://localhost:8000/search/', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({query, top_k: 10, use_time_ranking: true})
                        });
                        
                        const data = await response.json();
                        
                        if (data.results.length === 0) {
                            resultsDiv.innerHTML = '<div class="loading">No results found</div>';
                            return;
                        }
                        
                        resultsDiv.innerHTML = data.results.map(r => `
                            <div class="result-item">
                                <div class="result-name">${r.name}</div>
                                <div class="result-meta">${r.path}</div>
                                <div class="result-scores">
                                    <span>📊 Combined: ${(r.combined_score * 100).toFixed(1)}%</span>
                                    <span>🧠 Semantic: ${(r.semantic_score * 100).toFixed(1)}%</span>
                                    <span>⏱️ Time: ${(r.time_score * 100).toFixed(1)}%</span>
                                </div>
                            </div>
                        `).join('');
                    } catch (e) {
                        resultsDiv.innerHTML = `<div class="error">Error: ${e.message}</div>`;
                    }
                }
                
                // Focus on load
                window.addEventListener('load', () => document.getElementById('query').focus());
            </script>
        </body>
        </html>
        """
        
        webview.create_window(UI_TITLE, html=html, width=UI_WIDTH, height=UI_HEIGHT)
        webview.start()
    except Exception as e:
        logger.error(f"UI error: {e}")

if __name__ == "__main__":
    # Start API in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # Start UI in main thread
    start_ui()
