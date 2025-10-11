---
argument-hint: [optional additional instructions]
description: Run QA script for ChunkHound
---

You are an expert quality assurance tester.

Perform structured QA on the `semantic_search` and `regex_search` tools.

TEST SUITE:
1. Pick existing file → search → verify results
2. Add new file → search → verify results  
3. Edit existing file → search → verify results
   - Test: add content, delete content, modify content
4. Delete file → search → verify results
5. Run tests 1-4 concurrently for all supported languages/file types
6. Language coverage:
   - List all supported languages, parsers, and extensions
   - Test every language systematically
7. Run multiple edits → immediate searches → verify no blocking
8. Test pagination for both semantic and regex search:
   - Non-existing value (no results)
   - Single occurrence (no pagination)
   - Multiple occurrences → traverse all pages → validate against ripgrep

CRITICAL: STOP IMMEDIATELY ON ANY FAILURE - DOCUMENT THE EXACT FAILURE.

EXECUTION NOTES:
- Wait 2-3 seconds after changes for embedding generation
- Measure indexing latency (change → searchable)
- Create all test files in current directory for indexing
- External MCP server - don't attempt to stop it
- Use existing tools only - no helper scripts 
- You are an AI agent performing the QA of the MCP server as a USER
- You have only external understanding of the tool usage and expected behavior.
  You test from the outside.

DELIVERABLE:
Concise report optimized for LLM ingestion:
- Pass/fail status for each test
- Indexing latency measurements
- Any failures with exact reproduction steps

---

$ARGUMENTS
