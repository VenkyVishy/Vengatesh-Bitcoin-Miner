from flask import Flask, render_template, jsonify
import requests, threading, time, sqlite3, os, subprocess

app = Flask(__name__)

# ✅ HARDCODED DETAILS
SLUSH_POOL_CONFIG = {
    'token': 'bF8swM9zKmpO6BBf',
    'username': 'Vengatesh_R',
    'worker': 'worker1',
    'wallet': 'bc1qlwlkg0gr7l0595sc4qmawqw47z2wvm7v64x2d4',
    'base_url': 'https://pool.braiins.com/api/'
}

mining_status = False
miner_process = None
current_stats = {
    'connected': False, 'hash_rate': 0, 'accepted_shares': 0,
    'rejected_shares': 0, 'hardware_errors': 0, 'utility': 0,
    'balance_confirmed': 0, 'balance_unconfirmed': 0,
    'last_update': None, 'status_message': 'Initializing...',
    'status': 'Stopped'
}

# 🧠 DB Init
def init_db():
    conn = sqlite3.connect('mining_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mining_stats
                 (timestamp TEXT, hash_rate REAL, accepted INTEGER,
                  rejected INTEGER, hardware_errors INTEGER,
                  utility REAL, balance_confirmed REAL, balance_unconfirmed REAL, status TEXT)''')
    conn.commit(); conn.close()
init_db()

# 🛰️ Slush Pool API
class SlushPoolAPI:
    def __init__(self, config):
        self.config = config
        self.last_request_time = 0
        self.min_request_interval = 6
    def _rate_limit(self):
        now = time.time()
        diff = now - self.last_request_time
        if diff < self.min_request_interval:
            time.sleep(self.min_request_interval - diff)
        self.last_request_time = time.time()
    def get_account_profile(self):
        try:
            self._rate_limit()
            res = requests.get(f"{self.config['base_url']}accounts/profile/json/btc/",
                               headers={'SlushPool-Auth-Token': self.config['token']}, timeout=15)
            return res.json() if res.status_code == 200 else None
        except: return None
    def get_worker_stats(self):
        try:
            self._rate_limit()
            res = requests.get(f"{self.config['base_url']}accounts/workers/json/btc/",
                               headers={'SlushPool-Auth-Token': self.config['token']}, timeout=15)
            return res.json() if res.status_code == 200 else None
        except: return None
    def withdraw(self):
        try:
            self._rate_limit()
            res = requests.post(f"{self.config['base_url']}accounts/wallet/send", 
                headers={'SlushPool-Auth-Token': self.config['token']},
                json={"currency": "btc", "to": self.config['wallet'], "amount": None})
            return res.json() if res.status_code == 200 else {'error': 'Failed'}
        except Exception as e:
            return {'error': str(e)}

def save_stats_to_db(stats):
    try:
        conn = sqlite3.connect('mining_data.db')
        c = conn.cursor()
        c.execute('''INSERT INTO mining_stats 
                     (timestamp, hash_rate, accepted, rejected, 
                      hardware_errors, utility, balance_confirmed, balance_unconfirmed, status) 
                     VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (stats['hash_rate'], stats['accepted_shares'], stats['rejected_shares'],
                   stats['hardware_errors'], stats['utility'], stats['balance_confirmed'],
                   stats['balance_unconfirmed'], stats['status']))
        conn.commit(); conn.close()
    except Exception as e:
        print("DB error:", e)

# 🔁 Background Updater
def update_mining_data():
    global current_stats
    api = SlushPoolAPI(SLUSH_POOL_CONFIG)
    while True:
        try:
            if mining_status:
                profile = api.get_account_profile()
                workers = api.get_worker_stats()
                if profile and workers:
                    btc = profile.get('btc', {})
                    current_stats['balance_confirmed'] = float(btc.get('confirmed_reward', 0))
                    current_stats['balance_unconfirmed'] = float(btc.get('unconfirmed_reward', 0))
                    total_hash = total_accepted = total_rejected = 0
                    for worker in workers.get('workers', {}).values():
                        total_hash += float(worker.get('last_share_rate', 0))
                        total_accepted += int(worker.get('accepted_shares', 0))
                        total_rejected += int(worker.get('rejected_shares', 0))
                    current_stats['hash_rate'] = total_hash
                    current_stats['accepted_shares'] = total_accepted
                    current_stats['rejected_shares'] = total_rejected
                    current_stats['utility'] = round(total_accepted / 60.0, 2) if total_accepted else 0
                    current_stats['connected'] = True
                    current_stats['status_message'] = "Connected to Slush Pool"
                    current_stats['last_update'] = time.strftime("%Y-%m-%d %H:%M:%S")
                    save_stats_to_db(current_stats)
                else:
                    current_stats['connected'] = False
                    current_stats['status_message'] = "Connection failed"
            else:
                current_stats['status_message'] = "Mining stopped"
        except Exception as e:
            current_stats['status_message'] = f"Error: {e}"
        time.sleep(10)
threading.Thread(target=update_mining_data, daemon=True).start()

# 🚀 Flask Routes
@app.route('/')
def index(): return render_template('index.html', stats=current_stats)

@app.route('/start_mining')
def start_mining():
    global miner_process, mining_status
    if miner_process is None:
        # 🔁 Use Braiins OS+ CLI command or simple ping loop as placeholder
        miner_process = subprocess.Popen(
            ["ping", "127.0.0.1", "-t"],  # Replace with real miner call
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        mining_status = True; current_stats['status'] = 'Mining'
    return jsonify({'status': 'Mining started'})

@app.route('/stop_mining')
def stop_mining():
    global miner_process, mining_status
    if miner_process:
        miner_process.terminate(); miner_process = None
    mining_status = False; current_stats['status'] = 'Stopped'
    return jsonify({'status': 'Mining stopped'})

@app.route('/get_status')
def get_status(): return jsonify(current_stats)

@app.route('/withdraw_now')
def withdraw_now():
    api = SlushPoolAPI(SLUSH_POOL_CONFIG)
    result = api.withdraw()
    return jsonify(result)

# 🧱 Template Generator
if __name__ == '__main__':
    if not os.path.exists('templates'): os.makedirs('templates')
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w') as f:
            f.write('''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Crypto Mining Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font/css/materialdesignicons.min.css">
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-900 text-white min-h-screen flex flex-col items-center py-10">
<h1 class="text-4xl font-bold mb-8">⛏️ Crypto Mining Dashboard</h1>
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full px-4">
<div class="bg-gray-800 rounded-lg p-6 shadow-md"><div class="flex items-center mb-2">
<span class="mdi mdi-speedometer text-green-400 text-3xl mr-3"></span><h2 class="text-xl font-semibold">Hash Rate</h2>
</div><p id="hash_rate" class="text-2xl">0 H/s</p></div>
<div class="bg-gray-800 rounded-lg p-6 shadow-md"><div class="flex items-center mb-2">
<span class="mdi mdi-check-decagram text-blue-400 text-3xl mr-3"></span><h2 class="text-xl font-semibold">Accepted Shares</h2>
</div><p id="accepted_shares" class="text-2xl">0</p></div>
<div class="bg-gray-800 rounded-lg p-6 shadow-md"><div class="flex items-center mb-2">
<span class="mdi mdi-currency-btc text-yellow-400 text-3xl mr-3"></span><h2 class="text-xl font-semibold">Confirmed Balance</h2>
</div><p id="balance_confirmed" class="text-2xl">0 BTC</p></div></div>
<div class="mt-10 flex gap-6">
<button onclick="startMining()" class="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-semibold flex items-center gap-2">
<span class="mdi mdi-play-circle-outline text-xl"></span> Start Mining</button>
<button onclick="stopMining()" class="bg-red-600 hover:bg-red-700 px-6 py-3 rounded-lg font-semibold flex items-center gap-2">
<span class="mdi mdi-stop-circle-outline text-xl"></span> Stop Mining</button>
<button onclick="withdraw()" class="bg-yellow-600 hover:bg-yellow-700 px-6 py-3 rounded-lg font-semibold flex items-center gap-2">
<span class="mdi mdi-cash-refund text-xl"></span> Withdraw</button></div>
<div class="mt-10 text-center"><p id="status_text" class="text-lg mb-2">Status: <span class="font-bold text-yellow-400">Loading...</span></p>
<span id="status_icon" class="mdi mdi-progress-clock text-yellow-400 text-4xl animate-spin"></span></div>
<script>
function startMining() {
fetch('/start_mining').then(res => res.json()).then(() => Swal.fire('✅ Started', 'Mining started.', 'success'));
}
function stopMining() {
fetch('/stop_mining').then(res => res.json()).then(() => Swal.fire('🛑 Stopped', 'Mining stopped.', 'info'));
}
function withdraw() {
fetch('/withdraw_now').then(res => res.json()).then(data => {
Swal.fire('💸 Withdrawal', data.status || JSON.stringify(data), data.error ? 'error' : 'success');
});
}
function getStatus() {
fetch('/get_status').then(res => res.json()).then(data => {
document.getElementById('hash_rate').textContent = `${data.hash_rate} H/s`;
document.getElementById('accepted_shares').textContent = data.accepted_shares;
document.getElementById('balance_confirmed').textContent = `${data.balance_confirmed} BTC`;
document.getElementById('status_text').innerHTML = `Status: <span class="font-bold text-${data.status === 'Mining' ? 'green' : 'red'}-400">${data.status}</span>`;
document.getElementById('status_icon').className = data.status === 'Mining'
? 'mdi mdi-bitcoin text-green-400 text-4xl animate-pulse' : 'mdi mdi-stop text-red-400 text-4xl';
});
}
getStatus(); setInterval(getStatus, 2000);
</script></body></html>''')
    app.run(host="0.0.0.0", port=5000, debug=True)
