#!/bin/bash
# Monitor VS Code MCP server with debug logging

echo "Setting up debug logging in VS Code container..."

# Create logs directory in container
docker exec chunkhound-mcp-test mkdir -p /test-logs

# Create a monitoring script in the container
docker exec chunkhound-mcp-test bash -c 'cat > /monitor-mcp.sh << "EOF"
#!/bin/bash
# Find and monitor MCP processes

echo "Monitoring MCP processes..."
echo "Debug logs will be written to: /test-logs/mcp-*.log"

# Set debug environment for all new processes
export CHUNKHOUND_DEBUG_LOG=/test-logs/mcp-\$(date +%s).log

# Monitor process creation
while true; do
    # Find chunkhound mcp processes
    pgrep -f "chunkhound mcp" > /tmp/mcp-pids 2>/dev/null
    
    if [ -s /tmp/mcp-pids ]; then
        echo "Found MCP processes:"
        while read pid; do
            if [ -d /proc/$pid ]; then
                echo "  PID $pid: $(cat /proc/$pid/cmdline | tr '\0' ' ')"
                # Try to inject debug env - this wont work for running processes but shows intent
                echo "  Working dir: $(readlink /proc/$pid/cwd)"
            fi
        done < /tmp/mcp-pids
    fi
    
    # Check for any debug logs
    if ls /test-logs/mcp-*.log 2>/dev/null | head -1 > /dev/null; then
        echo "Debug logs found:"
        ls -la /test-logs/mcp-*.log
    fi
    
    sleep 5
done
EOF
chmod +x /monitor-mcp.sh'

# Start monitoring in background
docker exec -d chunkhound-mcp-test /monitor-mcp.sh

echo ""
echo "Monitoring started. Now:"
echo "1. Open http://localhost:8080 in your browser"
echo "2. Password: test-mcp-2025"
echo "3. Install the MCP extension if needed"
echo "4. Try to use ChunkHound MCP server"
echo ""
echo "To check for errors:"
echo "docker exec chunkhound-mcp-test ls -la /test-logs/"
echo "docker exec chunkhound-mcp-test tail -f /test-logs/mcp-*.log"
echo ""
echo "To see container output:"
echo "docker logs -f chunkhound-mcp-test"