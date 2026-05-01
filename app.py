from flask import Flask, request, jsonify, render_template
import heapq
import sqlite3
import datetime
import numpy as np
import csv
from io import StringIO

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('optim_flow.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS simulations 
                 (id INTEGER PRIMARY KEY, date TEXT, route TEXT, cost REAL, payload_value INTEGER)''')
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
    
    baseline_cost = dist[end]

    simulated_costs = []
    for _ in range(1000):
        sim_cost = 0
        for i in range(len(path)-1):
            base_edge = graph[path[i]][path[i+1]]
            fluctuation = np.random.uniform(0.8, 2.5) 
            sim_cost += (base_edge * fluctuation)
        simulated_costs.append(sim_cost)
        
    avg_sim_cost = round(np.mean(simulated_costs), 2)
    efficiency_score = round(len([c for c in simulated_costs if c <= baseline_cost * 1.5]) / 10, 1)
    
    # Cost breakdown for each edge in the path
    cost_breakdown = []
    for i in range(len(path)-1):
        cost_breakdown.append({
            "from": path[i],
            "to": path[i+1],
            "cost": graph[path[i]][path[i+1]]
        })

    return {
        "path": path, 
        "baseline": baseline_cost, 
        "avg_simulated": avg_sim_cost, 
        "success_prob": efficiency_score,
        "cost_breakdown": cost_breakdown
    }

@app.route('/')
def home():
    conn = sqlite3.connect('optim_flow.db')
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
    
    conn = sqlite3.connect('optim_flow.db')
    c = conn.cursor()
    c.execute("INSERT INTO simulations (date, route, cost, payload_value) VALUES (?, ?, ?, ?)",
              (date_str, route_str, r_plan['avg_simulated'], s_plan['max_value']))
    conn.commit()
    conn.close()
    
    new_log = {"date": date_str, "route": route_str, "risk": r_plan['avg_simulated'], "payload_value": s_plan['max_value']}
    
    return jsonify({"supply_plan": s_plan, "route_plan": r_plan, "new_log": new_log})

@app.route('/api/validate-network', methods=['POST'])
def validate_network():
    data = request.json
    graph = data['graph']
    start = data['start']
    end = data['end']
    
    if start not in graph or end not in graph:
        return jsonify({"valid": False, "message": f"Start or end node not in graph"})
    
    visited = set()
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            queue.append(neighbor)
    
    if end not in visited:
        return jsonify({"valid": False, "message": f"No path exists from {start} to {end}"})
    
    return jsonify({"valid": True})

@app.route('/api/statistics', methods=['GET'])
def statistics():
    conn = sqlite3.connect('optim_flow.db')
    c = conn.cursor()
    c.execute("SELECT cost, payload_value FROM simulations")
    results = c.fetchall()
    conn.close()
    
    if not results:
        return jsonify({"error": "No data"})
    
    costs = [r[0] for r in results]
    values = [r[1] for r in results]
    
    costs.sort()
    values.sort()
    
    return jsonify({
        "min_cost": round(min(costs), 2),
        "max_cost": round(max(costs), 2),
        "avg_cost": round(sum(costs) / len(costs), 2),
        "median_cost": round(costs[len(costs)//2], 2),
        "min_value": min(values),
        "max_value": max(values),
        "avg_value": round(sum(values) / len(values), 2),
        "total_simulations": len(results)
    })

@app.route('/api/export-csv', methods=['GET'])
def export_csv():
    conn = sqlite3.connect('optim_flow.db')
    c = conn.cursor()
    c.execute("SELECT * FROM simulations ORDER BY id DESC")
    results = c.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Date', 'Route', 'Cost', 'Payload Value'])
    writer.writerows(results)
    
    return output.getvalue(), 200, {'Content-Disposition': 'attachment; filename=OptimFlow_Report.csv'}

@app.route('/api/delete-history', methods=['POST'])
def delete_history():
    conn = sqlite3.connect('optim_flow.db')
    c = conn.cursor()
    c.execute("DELETE FROM simulations")
    conn.commit()
    conn.close()
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(debug=True)
