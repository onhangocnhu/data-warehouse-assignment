#!/usr/bin/env bash
# Start the drawio MCP server (persistent) and print connection config.
# Usage: report/drawio-mcp/start.sh
set -uo pipefail

HTTP_PORT=3000
WS_PORT=3333
LOG=/tmp/drawio-mcp.log

health() { curl -s -m 2 "http://localhost:$HTTP_PORT/health" | grep -q '"status":"ok"'; }

if health; then
  echo "drawio MCP server already running (pid $(lsof -tiTCP:$HTTP_PORT -sTCP:LISTEN | head -1))"
else
  echo "starting drawio-mcp-server..."
  nohup npx -y drawio-mcp-server --editor --transport http >"$LOG" 2>&1 &
  for _ in $(seq 1 30); do health && break; sleep 1; done
  health || { echo "FAILED to start — see $LOG"; tail -5 "$LOG"; exit 1; }
fi

cat <<EOF

drawio MCP server is up.

  Browser extension ......... ws://localhost:$WS_PORT
  Built-in editor ........... http://localhost:$HTTP_PORT/
  MCP endpoint (pi) ......... http://localhost:$HTTP_PORT/mcp
  Log file .................. $LOG
  Stop ...................... pkill -f drawio-mcp-server

pi config (~/.config/pi/agent/mcp-adapter.json):

    "drawio": {
      "url": "http://localhost:$HTTP_PORT/mcp",
      "directTools": true
    }

Browser: open app.diagrams.net with the "Draw.io MCP" extension
installed and site access allowed (green icon = connected).
EOF
