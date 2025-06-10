# ChunkHound Troubleshooting Guide

## Common Issues and Solutions

### Configuration Problems

#### Problem: "No configuration file found"
```
Error: No configuration file found, using defaults
```

**Solutions:**
1. Create a configuration file:
   ```bash
   chunkhound config template --output ~/.chunkhound/config.yaml
   ```

2. Use a specific config file:
   ```bash
   chunkhound --config ./my-config.yaml config list
   ```

3. Discover existing configs:
   ```bash
   chunkhound config discover
   ```

#### Problem: "Config file has structural issues"
```
❌ Configuration file has structural issues
• Missing "servers" section
• Server "local" missing required fields: ['base_url']
```

**Solutions:**
1. Validate and auto-fix:
   ```bash
   chunkhound config validate --fix
   ```

2. Generate a new template:
   ```bash
   chunkhound config template --type basic --output config.yaml
   ```

3. Check YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

#### Problem: "Server not found in servers"
```
Error: Server 'my-server' not found
```

**Solutions:**
1. List available servers:
   ```bash
   chunkhound config list
   ```

2. Add the missing server:
   ```bash
   chunkhound config add my-server --type openai --base-url https://api.openai.com/v1
   ```

### Server Connectivity Issues

#### Problem: "Connection refused" or "Cannot connect to host"
```
❌ Connection failed: Cannot connect to host localhost:8080 ssl:default [Errno 61] Connect call failed
```

**Common Causes & Solutions:**

1. **Server not running:**
   - Start your TEI server:
     ```bash
     docker run -p 8080:80 ghcr.io/huggingface/text-embeddings-inference:latest \
       --model-id sentence-transformers/all-MiniLM-L6-v2
     ```
   - Start Ollama:
     ```bash
     ollama serve
     ollama pull nomic-embed-text
     ```

2. **Wrong port or URL:**
   - Check server configuration:
     ```bash
     chunkhound config list
     ```
   - Update the URL:
     ```bash
     chunkhound config remove server-name
     chunkhound config add server-name --type tei --base-url http://localhost:8080
     ```

3. **Firewall blocking connection:**
   - Test connectivity manually:
     ```bash
     curl http://localhost:8080/health
     ```
   - Check firewall rules
   - Verify Docker port mapping

#### Problem: "SSL/TLS errors"
```
SSL connection error or certificate verification failed
```

**Solutions:**
1. Use HTTP for local servers:
   ```bash
   chunkhound config add local --base-url http://localhost:8080
   ```

2. For HTTPS servers, verify certificates:
   ```bash
   curl -v https://your-server.com/health
   ```

3. Skip SSL verification (development only):
   ```yaml
   servers:
     my-server:
       base_url: https://localhost:8080
       # Add custom SSL settings if needed
   ```

#### Problem: "Authentication failed" or "API key invalid"
```
❌ Authentication failed: Invalid API key
```

**Solutions:**
1. Set environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

2. Add API key to config:
   ```bash
   chunkhound config add openai --api-key your-api-key
   ```

3. Verify API key format and permissions:
   ```bash
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   ```

#### Problem: "You must provide a model parameter"
```
Error code: 400 - {'error': {'message': 'you must provide a model parameter', 'type': 'invalid_request_error', 'param': None, 'code': None}}
```

**Cause:** This error occurs when the CLI command is run without specifying a `--model` parameter and the system fails to use the default model.

**Solutions:**
1. **Specify model explicitly (immediate fix):**
   ```bash
   chunkhound run . --model text-embedding-3-small
   ```

2. **Update ChunkHound to latest version (permanent fix):**
   ```bash
   uv pip install --upgrade chunkhound
   ```

3. **Verify the fix is working:**
   ```bash
   # This should work without --model parameter
   chunkhound run . --db test.db
   ```

**Technical Details:**
- Fixed in version 0.1.0+ 
- Issue was in provider registry not respecting constructor defaults
- Now properly uses `text-embedding-3-small` as default when no model specified

### Performance Issues

#### Problem: "Embeddings are too slow"
```
Embedding generation taking longer than expected
```

**Solutions:**

1. **Optimize batch size:**
   ```bash
   # Test different batch sizes
   chunkhound config benchmark --batch-sizes 1 8 16 32 64
   
   # Update optimal batch size
   chunkhound config add server-name --batch-size 32
   ```

2. **Use local servers:**
   ```bash
   # Switch to local TEI server
   chunkhound config switch local-tei
   ```

3. **Check server resources:**
   - Monitor CPU/memory usage
   - Ensure adequate GPU resources for TEI
   - Check network latency

4. **Optimize model selection:**
   ```bash
   # Use smaller, faster models
   chunkhound config add fast-server --model text-embedding-3-small
   ```

#### Problem: "High memory usage"
```
ChunkHound consuming excessive memory
```

**Solutions:**
1. Reduce batch size:
   ```bash
   chunkhound config add server-name --batch-size 8
   ```

2. Process files incrementally:
   ```bash
   chunkhound run . --no-embeddings  # Index structure only first
   ```

3. Exclude large files:
   ```bash
   chunkhound run . --exclude "*.log" --exclude "*/node_modules/*"
   ```

### Database Issues

#### Problem: "Database locked" or "Permission denied"
```
Database error: database is locked
```

**Solutions:**
1. Ensure no other ChunkHound processes are running:
   ```bash
   ps aux | grep chunkhound
   killall chunkhound
   ```

2. Check database file permissions:
   ```bash
   ls -la ~/.cache/chunkhound/chunks.duckdb
   chmod 644 ~/.cache/chunkhound/chunks.duckdb
   ```

3. Use a different database location:
   ```bash
   chunkhound run . --db ./my-chunks.duckdb
   ```

#### Problem: "Database corruption"
```
Database file appears to be corrupted
```

**Solutions:**
1. Backup and recreate database:
   ```bash
   mv ~/.cache/chunkhound/chunks.duckdb ~/.cache/chunkhound/chunks.duckdb.backup
   chunkhound run . --watch
   ```

2. Use database repair tools if available

### File Watching Issues

#### Problem: "File changes not detected"
```
Real-time file watching not working
```

**Solutions:**
1. Check file system limits:
   ```bash
   # Linux: Increase inotify limits
   echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

2. Verify file patterns:
   ```bash
   chunkhound run . --include "*.py" --include "*.js" --verbose
   ```

3. Check permissions:
   ```bash
   ls -la /path/to/watched/directory
   ```

#### Problem: "Too many file events"
```
File watcher overwhelmed with events
```

**Solutions:**
1. Increase debounce time:
   ```bash
   chunkhound run . --watch --debounce-ms 1000
   ```

2. Exclude noisy directories:
   ```bash
   chunkhound run . --exclude "*/node_modules/*" --exclude "*/.git/*"
   ```

### Embedding Quality Issues

#### Problem: "Poor search results"
```
Semantic search not returning relevant results
```

**Solutions:**

1. **Check embedding dimensions:**
   ```bash
   chunkhound config test server-name
   # Note the embedding dimensions
   ```

2. **Compare different models:**
   ```bash
   chunkhound config benchmark
   # Test search quality with different providers
   ```

3. **Verify model compatibility:**
   - Ensure all embeddings use the same model
   - Reindex if switching models
   ```bash
   rm ~/.cache/chunkhound/chunks.duckdb
   chunkhound run . --watch
   ```

4. **Check text preprocessing:**
   - Verify code is being chunked appropriately
   - Check for encoding issues

#### Problem: "Inconsistent embeddings"
```
Different embeddings for same text across runs
```

**Solutions:**
1. Check for model version changes:
   ```bash
   chunkhound config test server-name --text "test phrase"
   # Run multiple times, compare dimensions
   ```

2. Verify server stability:
   ```bash
   chunkhound config health --monitor
   ```

3. Use deterministic models when possible

### Resource Usage Issues

#### Problem: "High CPU usage"
```
ChunkHound consuming too much CPU
```

**Solutions:**
1. Reduce concurrency:
   ```bash
   # Check system resources
   htop
   
   # Reduce batch size
   chunkhound config add server-name --batch-size 8
   ```

2. Optimize file filtering:
   ```bash
   chunkhound run . --exclude "*/tests/*" --exclude "*/docs/*"
   ```

3. Process in smaller chunks:
   ```bash
   # Process one directory at a time
   chunkhound run ./src --no-watch
   chunkhound run ./lib --no-watch
   ```

#### Problem: "Disk space issues"
```
Running out of disk space for database
```

**Solutions:**
1. Check database size:
   ```bash
   du -h ~/.cache/chunkhound/chunks.duckdb
   ```

2. Clean up old data:
   ```bash
   # Remove and recreate database
   rm ~/.cache/chunkhound/chunks.duckdb
   ```

3. Use external storage:
   ```bash
   chunkhound run . --db /external/storage/chunks.duckdb
   ```

## Debugging Commands

### Enable Verbose Logging
```bash
# For run command
chunkhound run . --verbose

# For MCP server
chunkhound mcp --verbose

# Check logs in detail
chunkhound config health --monitor
```

### System Information
```bash
# Check versions
chunkhound --version
python --version

# Check configuration
chunkhound config discover
chunkhound config validate

# Test connectivity
chunkhound config batch-test --timeout 30
```

### Network Diagnostics
```bash
# Test server connectivity
curl -v http://localhost:8080/health

# Check DNS resolution
nslookup api.openai.com

# Test API endpoints
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"input": "test", "model": "text-embedding-3-small"}' \
     https://api.openai.com/v1/embeddings
```

## Getting Help

### Command-line Help
```bash
chunkhound --help
chunkhound config --help
chunkhound config add --help
```

### Configuration Validation
```bash
chunkhound config validate --fix
chunkhound config discover
```

### Performance Analysis
```bash
chunkhound config benchmark
chunkhound config health --monitor
```

### Export Debug Information
```bash
# Export configuration for support
chunkhound config export debug-config.yaml

# Test all servers
chunkhound config batch-test > debug-test-results.txt

# System information
chunkhound --version > debug-info.txt
python --version >> debug-info.txt
uname -a >> debug-info.txt
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `No configuration file found` | Missing config | `chunkhound config template` |
| `Server 'X' not found` | Server not configured | `chunkhound config add X` |
| `Cannot connect to host` | Server not running | Start server or check URL |
| `Invalid API key` | Wrong/missing API key | Set environment variable |
| `You must provide a model parameter` | Registry bug (fixed in v0.1.0+) | Update ChunkHound or use `--model` |
| `Database is locked` | Multiple processes | Kill other instances |
| `Permission denied` | File permissions | Check file/directory permissions |
| `Connection timeout` | Network/server issues | Check network and server status |
| `YAML parsing error` | Invalid config syntax | Validate YAML syntax |
| `Health check failed` | Server unhealthy | Check server logs and status |

## Performance Benchmarks

### Expected Performance
- **Local TEI**: 300-1000 embeddings/sec
- **OpenAI API**: 100-500 embeddings/sec
- **Ollama**: 50-200 embeddings/sec

### Optimization Targets
- **Batch size**: 16-64 for most servers
- **Response time**: <100ms for local, <500ms for remote
- **Memory usage**: <2GB for typical projects
- **CPU usage**: <50% during indexing

If performance is significantly below these targets, use the troubleshooting steps above.

## Contact and Support

1. **Check documentation**: Read CLI guide and examples
2. **Search issues**: Look for similar problems in GitHub issues
3. **Create minimal reproduction**: Provide config and error details
4. **Include debug information**: Version, configuration, logs

For additional help, consult the project documentation or create an issue with:
- ChunkHound version
- Operating system
- Configuration file (sanitized)
- Error messages and logs
- Steps to reproduce