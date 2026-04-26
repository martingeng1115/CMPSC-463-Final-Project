from flask import Flask, request, jsonify, render_template
import heapq
import sqlite3
import datetime
import numpy as np

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('crisis_logs.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS simulations 
                 (id INTEGER PRIMARY KEY, date TEXT, route TEXT, risk REAL, payload_value INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def optimize_supplies_2d(weight_cap, volume_cap, items):
    n = len(items)
    dp = [[[0 for _ in range(volume_cap + 1)] for _ in range(weight_cap + 1)] for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        w = items[i-1]['weight']
        vol = items[i-1]['volume']
        val = items[i-1]['value']
        
        for curr_w in range(weight_cap + 1):
            for curr_vol in range(volume_cap + 1):
                if w <= curr_w and vol <= curr_vol:
                    dp[i][curr_w][curr_vol] = max(val + dp[i-1][curr_w-w][curr_vol-vol], dp[i-1][curr_w][curr_vol])
                else:
                    dp[i][curr_w][curr_vol] = dp[i-1][curr_w][curr_vol]
                    
    res = []
    cw, cv = weight_cap, volume_cap
    for i in range(n, 0, -1):
        if dp[i][cw][cv] != dp[i-1][cw][cv]:
            res.append(items[i-1])
            cw -= items[i-1]['weight']
            cv -= items[i-1]['volume']
            
    return {"max_value": dp[n][weight_cap][volume_cap], "selected": res}

def get_route_and_sim(graph, start, end):
    q = []
    heapq.heappush(q, (0, start))
    dist = {n: float('inf') for n in graph}
    dist[start] = 0
    prev = {n: None for n in graph}

    while q:
        curr_dist, curr_node = heapq.heappop(q)
        if curr_dist > dist[curr_node]: 
            continue
        if curr_node == end: 
            break

        for neighbor, weight in graph[curr_node].items():
            d = curr_dist + weight
            if d < dist[neighbor]:
                dist[neighbor] = d
                prev[neighbor] = curr_node
                heapq.heappush(q, (d, neighbor))

    path = []
    curr = end
    while prev[curr] is not None:
        path.insert(0, curr)
        curr = prev[curr]
    if path: 
        path.insert(0, curr)
    
    baseline_risk = dist[end]

    simulated_risks = []
    for _ in range(1000):
        sim_risk = 0
        for i in range(len(path)-1):
            base_edge = graph[path[i]][path[i+1]]
            fluctuation = np.random.uniform(0.8, 2.5) 
            sim_risk += (base_edge * fluctuation)
        simulated_risks.append(sim_risk)
        
    avg_sim_risk = round(np.mean(simulated_risks), 2)
    success_prob = round(len([r for r in simulated_risks if r <= baseline_risk * 1.5]) / 10, 1)

    return {"path": path, "baseline": baseline_risk, "avg_simulated": avg_sim_risk, "success_prob": success_prob}

@app.route('/')
def home():
    conn = sqlite3.connect('crisis_logs.db')
    c = conn.cursor()
    c.execute("SELECT * FROM simulations ORDER BY id DESC LIMIT 5")
    history = c.fetchall()
    conn.close()
    return render_template('index.html', history=history)

@app.route('/api/simulate', methods=['POST'])
def simulate():
    data = request.json
    
    s_plan = optimize_supplies_2d(data['weight_cap'], data['volume_cap'], data['supplies'])
    r_plan = get_route_and_sim(data['graph'], data['start'], data['end'])
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    route_str = " -> ".join(r_plan['path'])
    
    conn = sqlite3.connect('crisis_logs.db')
    c = conn.cursor()
    c.execute("INSERT INTO simulations (date, route, risk, payload_value) VALUES (?, ?, ?, ?)",
              (date_str, route_str, r_plan['avg_simulated'], s_plan['max_value']))
    conn.commit()
    conn.close()
    
    new_log = {"date": date_str, "route": route_str, "risk": r_plan['avg_simulated'], "payload_value": s_plan['max_value']}
    
    return jsonify({"supply_plan": s_plan, "route_plan": r_plan, "new_log": new_log})

if __name__ == '__main__':
    app.run(debug=True)
