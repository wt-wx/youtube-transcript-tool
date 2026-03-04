import os
import time
import psutil
import uvicorn
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from src.core.config import Config
from typing import Dict, Any

app = FastAPI(title=f"Geniux Probe - {Config.NODE_NAME}")

# 基础配置
START_TIME = time.time()
PROBE_SECRET = os.getenv("PROBE_SECRET", "") # 可选：安全验证

def get_sys_info() -> Dict[str, Any]:
    """收集系统核心指标"""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None) # 非阻塞获取
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
    
    # Memory
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    
    # Disk (Root)
    du = psutil.disk_usage("/")
    
    # Network
    net_io = psutil.net_io_counters()
    
    # Uptime
    uptime_seconds = int(time.time() - START_TIME)
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "status": "online",
        "node_name": Config.NODE_NAME,
        "timestamp": datetime.now().isoformat(),
        "uptime": uptime_seconds,
        "boot_time": boot_time,
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(),
            "load": load_avg
        },
        "memory": {
            "total": vm.total,
            "available": vm.available,
            "used": vm.used,
            "percent": vm.percent,
            "swap_percent": sm.percent
        },
        "disk": {
            "total": du.total,
            "used": du.used,
            "free": du.free,
            "percent": du.percent
        },
        "network": {
            "sent": net_io.bytes_sent,
            "recv": net_io.bytes_recv
        }
    }

@app.get("/api/status")
async def api_status(token: str = None):
    # 如果设置了 secret，则进行简单验证
    if PROBE_SECRET and token != PROBE_SECRET:
        return {"error": "Unauthorized"}
    return get_sys_info()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return HTML_TEMPLATE

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geniux Probe - 节点监控</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background: radial-gradient(circle at top left, #1a1a2e, #16213e);
            color: #e2e8f0;
            min-height: 100vh;
        }
        .glass {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 1rem;
        }
        .status-pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .bg-glow {
            position: absolute;
            width: 300px;
            height: 300px;
            background: rgba(66, 153, 225, 0.2);
            filter: blur(80px);
            border-radius: 50%;
            z-index: -1;
        }
    </style>
</head>
<body x-data="probeApp()" x-init="init()">
    <div class="bg-glow top-0 left-0"></div>
    <div class="bg-glow bottom-0 right-0" style="background: rgba(159, 122, 234, 0.15);"></div>

    <div class="container mx-auto px-4 py-8 max-w-5xl relative">
        <!-- Header -->
        <header class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold tracking-tight text-white mb-1" x-text="'Geniux Node ' + data.node_name">Geniux Node Probe</h1>
                <p class="text-slate-400 flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-green-500 status-pulse"></span>
                    <span x-text="data.node_name + ' 节点实时监控中'">LA 节点实时监控中</span>
                </p>
            </div>
            <div class="glass px-4 py-2 flex items-center gap-4">
                <div class="text-right">
                    <p class="text-xs text-slate-500 uppercase font-semibold">Uptime</p>
                    <p class="font-mono text-sm" x-text="formatUptime(data.uptime)">00:00:00</p>
                </div>
                <i data-lucide="server" class="text-blue-400 w-5 h-5"></i>
            </div>
        </header>

        <!-- Main Stats Grid -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <!-- CPU -->
            <div class="glass p-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                        <i data-lucide="cpu" class="w-6 h-6"></i>
                    </div>
                    <span class="text-xs font-mono text-slate-500" x-text="data.cpu.cores + ' Cores'"></span>
                </div>
                <h3 class="text-slate-400 text-sm font-medium mb-1">CPU 使用率</h3>
                <div class="flex items-end gap-2">
                    <span class="text-3xl font-bold" x-text="data.cpu.percent + '%'">0%</span>
                </div>
                <div class="w-full bg-slate-800 h-1.5 rounded-full mt-4">
                    <div class="bg-blue-500 h-1.5 rounded-full transition-all duration-500" :style="'width: ' + data.cpu.percent + '%'"></div>
                </div>
            </div>

            <!-- Memory -->
            <div class="glass p-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                        <i data-lucide="database" class="w-6 h-6"></i>
                    </div>
                    <span class="text-xs font-mono text-slate-500" x-text="formatBytes(data.memory.total)"></span>
                </div>
                <h3 class="text-slate-400 text-sm font-medium mb-1">内存占用</h3>
                <div class="flex items-end gap-2">
                    <span class="text-3xl font-bold" x-text="data.memory.percent + '%'">0%</span>
                </div>
                <div class="w-full bg-slate-800 h-1.5 rounded-full mt-4">
                    <div class="bg-emerald-500 h-1.5 rounded-full transition-all duration-500" :style="'width: ' + data.memory.percent + '%'"></div>
                </div>
            </div>

            <!-- Disk -->
            <div class="glass p-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="p-2 bg-amber-500/10 rounded-lg text-amber-400">
                        <i data-lucide="hard-drive" class="w-6 h-6"></i>
                    </div>
                    <span class="text-xs font-mono text-slate-500" x-text="formatBytes(data.disk.total)"></span>
                </div>
                <h3 class="text-slate-400 text-sm font-medium mb-1">存储空间</h3>
                <div class="flex items-end gap-2">
                    <span class="text-3xl font-bold" x-text="data.disk.percent + '%'">0%</span>
                </div>
                <div class="w-full bg-slate-800 h-1.5 rounded-full mt-4">
                    <div class="bg-amber-500 h-1.5 rounded-full transition-all duration-500" :style="'width: ' + data.disk.percent + '%'"></div>
                </div>
            </div>

            <!-- Load -->
            <div class="glass p-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="p-2 bg-rose-500/10 rounded-lg text-rose-400">
                        <i data-lucide="activity" class="w-6 h-6"></i>
                    </div>
                </div>
                <h3 class="text-slate-400 text-sm font-medium mb-1">系统负载 (1m)</h3>
                <div class="flex items-end gap-2">
                    <span class="text-3xl font-bold" x-text="data.cpu.load[0].toFixed(2)">0.00</span>
                </div>
                <p class="text-xs text-slate-500 mt-4">5m: <span x-text="data.cpu.load[1].toFixed(2)"></span> | 15m: <span x-text="data.cpu.load[2].toFixed(2)"></span></p>
            </div>
        </div>

        <!-- Charts Area -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div class="glass p-6">
                <h3 class="text-white font-semibold mb-6 flex items-center gap-2">
                    <i data-lucide="trending-up" class="w-4 h-4"></i> CPU & Memory 趋势
                </h3>
                <canvas id="sysChart" height="200"></canvas>
            </div>
            <div class="glass p-6">
                <h3 class="text-white font-semibold mb-6 flex items-center gap-2">
                    <i data-lucide="arrow-up-down" class="w-4 h-4"></i> 网络流量
                </h3>
                <div class="space-y-6">
                    <div>
                        <div class="flex justify-between text-sm mb-2">
                            <span class="text-slate-400 flex items-center gap-1"><i data-lucide="upload-cloud" class="w-3 h-3"></i> Total Sent</span>
                            <span class="font-mono text-blue-400" x-text="formatBytes(data.network.sent)"></span>
                        </div>
                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div class="bg-blue-400 h-full w-1/3 opacity-50"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-2">
                            <span class="text-slate-400 flex items-center gap-1"><i data-lucide="download-cloud" class="w-3 h-3"></i> Total Received</span>
                            <span class="font-mono text-emerald-400" x-text="formatBytes(data.network.recv)"></span>
                        </div>
                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div class="bg-emerald-400 h-full w-2/3 opacity-50"></div>
                        </div>
                    </div>
                    <div class="pt-4 border-t border-white/5">
                        <p class="text-xs text-slate-500 italic">部署时间: <span x-text="data.boot_time"></span></p>
                    </div>
                </div>
            </div>
        </div>
        
        <footer class="text-center text-slate-500 text-sm">
            Powered by Geniux OS Probe &bull; Refreshed every 5s
        </footer>
    </div>

    <script>
        function probeApp() {
            return {
                data: {
                    node_name: '...',
                    uptime: 0,
                    boot_time: '-',
                    cpu: { percent: 0, cores: 0, load: [0,0,0] },
                    memory: { total: 0, percent: 0 },
                    disk: { total: 0, percent: 0 },
                    network: { sent: 0, recv: 0 }
                },
                chart: null,
                maxHistory: 20,
                history: {
                    labels: [],
                    cpu: [],
                    mem: []
                },
                init() {
                    lucide.createIcons();
                    this.fetchData();
                    setInterval(() => this.fetchData(), 5000);
                    this.initChart();
                },
                async fetchData() {
                    try {
                        const res = await fetch('/api/status');
                        const json = await res.json();
                        this.data = json;
                        this.updateChart(json);
                    } catch (e) {
                        console.error("Fetch failed", e);
                    }
                },
                initChart() {
                    const ctx = document.getElementById('sysChart').getContext('2d');
                    this.chart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: this.history.labels,
                            datasets: [
                                {
                                    label: 'CPU %',
                                    data: this.history.cpu,
                                    borderColor: '#3b82f6',
                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                    fill: true,
                                    tension: 0.4,
                                    pointRadius: 0
                                },
                                {
                                    label: 'Mem %',
                                    data: this.history.mem,
                                    borderColor: '#10b981',
                                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                    fill: true,
                                    tension: 0.4,
                                    pointRadius: 0
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { display: false } },
                            scales: {
                                y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } },
                                x: { grid: { display : false }, ticks: { display: false } }
                            }
                        }
                    });
                },
                updateChart(json) {
                    const now = new Date().toLocaleTimeString();
                    this.history.labels.push(now);
                    this.history.cpu.push(json.cpu.percent);
                    this.history.mem.push(json.memory.percent);
                    
                    if (this.history.labels.length > this.maxHistory) {
                        this.history.labels.shift();
                        this.history.cpu.shift();
                        this.history.mem.shift();
                    }
                    this.chart.update();
                },
                formatBytes(bytes) {
                    if (bytes === 0) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                },
                formatUptime(seconds) {
                    const h = Math.floor(seconds / 3600);
                    const m = Math.floor((seconds % 3600) / 60);
                    const s = seconds % 60;
                    return [h, m, s].map(v => v < 10 ? "0" + v : v).join(":");
                }
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # 使用端口 9527 (经典梗)
    uvicorn.run(app, host="0.0.0.0", port=9527)
