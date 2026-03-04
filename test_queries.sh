#!/bin/bash
# Product Scout - Search Test Suite
# Run from the VPS: bash test_queries.sh
# Or individually: curl -X POST http://localhost:8000/search -H "Content-Type: application/json" -d '{"query": "...", "site_id": "test-store.myshopify.com"}'

SITE_ID="test-store.myshopify.com"
BASE_URL="http://localhost:8000"

run_query() {
  local label="$1"
  local query="$2"
  echo ""
  echo "=========================================="
  echo "TEST: $label"
  echo "QUERY: \"$query\""
  echo "=========================================="
  curl -s -X POST "$BASE_URL/search" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\", \"site_id\": \"$SITE_ID\"}" | \
    python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            event = d.get('event')
            ms = d.get('_ms', '?')
            if event == 'products':
                print(f'[{ms}ms] PRODUCTS:')
                for p in d.get('data', []):
                    print(f\"  - {p['handle']} (score: {p['score']:.2f})\")
            elif event == 'reasoning':
                print(f'[{ms}ms] REASONING:')
                for p in d.get('data', []):
                    print(f\"  - {p['handle']}: {p.get('reason', '')}\")
            elif event == 'empty':
                print(f'[{ms}ms] NO RESULTS FOUND')
        except: pass
"
  echo ""
}

# --- Keyword intent (obvious matches) ---
run_query "Direct keyword" "snowboard"
run_query "Specific sport" "tennis racket"
run_query "Sport equipment" "boxing"

# --- Semantic intent (indirect matches) ---
run_query "Winter sport general" "something fun to do in the snow"
run_query "Cardio workout" "I want to get into cardio"
run_query "Home gym" "I am setting up a home gym"
run_query "Recovery" "my muscles are sore after workouts"
run_query "Outdoor adventure" "outdoor adventure for the weekend"

# --- Gift/occasion intent ---
run_query "Gift for athlete" "birthday gift for someone who loves sports"
run_query "Gift for runner" "gift for a runner"

# --- Problem-oriented (no product name) ---
run_query "Hydration problem" "I keep forgetting to drink water during workouts"
run_query "Sleep tracking" "I want to track my sleep and heart rate"
run_query "Lose weight" "I want to lose weight at home"

# --- Cross-category discovery ---
run_query "Team sports" "something to play with friends outside"
run_query "Flexibility" "I want to improve my flexibility and balance"

echo "=============================="
echo "All tests complete."
echo "=============================="
