from flask import Flask, request, jsonify, render_template
import heapq

app = Flask(__name__)

def knapsack(cap, items):
    n = len(items)
    # matrix for dp
    dp = [[0 for _ in range(cap + 1)] for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        w = items[i-1]['weight']
        v = items[i-1]['value']
        for j in range(1, cap + 1):
            if w <= j:
                dp[i][j] = max(v + dp[i-1][j-w], dp[i-1][j])
            else:
                dp[i][j] = dp[i-1][j]
                
    # figure out which items we actually took
    res = []
    curr_w = cap
    for i in range(n, 0, -1):
        if dp[i][curr_w] != dp[i-1][curr_w]:
            res.append(items[i-1])
            curr_w -= items[i-1]['weight']
            
    # print("debug res:", res)
    return {"max_value": dp[n][cap], "selected": res}

def get_route(graph, start, end):
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

    # backtrack to get the path
    path = []
    curr = end
    while prev[curr] is not None:
        path.insert(0, curr)
        curr = prev[curr]
    if path:
        path.insert(0, curr)
        
    return {"path": path, "total_risk_cost": dist[end]}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/calculate', methods=['POST'])
def calc():
    data = request.json
    # print(data) 
    
    cap = data.get('truck_capacity', 50)
    items = data.get('supplies', [])
    
    # run both algos
    s_plan = knapsack(cap, items)
    r_plan = get_route(data.get('map_graph', {}), data.get('start_node', 'A'), data.get('end_node', 'D'))
    
    return jsonify({
        "supply_plan": s_plan,
        "route_plan": r_plan
    })

if __name__ == '__main__':
    app.run(debug=True)
