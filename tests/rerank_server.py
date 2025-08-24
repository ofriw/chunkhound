#!/usr/bin/env python3
"""
Mock reranking server for testing multi-hop semantic search.

This lightweight server provides a Cohere-compatible /rerank endpoint
for testing purposes without requiring heavy dependencies like vLLM.
"""

import asyncio
import json
import sys
from typing import Any

import httpx
from loguru import logger

# Configure logger for testing
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


class MockRerankServer:
    """Mock reranking server with Cohere-compatible API."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.host = host
        self.port = port
        self.server = None
        self.site = None
        
    async def health_handler(self, request: dict) -> dict:
        """Handle health check requests."""
        return {"healthy": True, "service": "mock-rerank-server"}
    
    async def rerank_handler(self, request: dict) -> dict:
        """Handle reranking requests with Cohere-compatible API."""
        try:
            # Parse request body
            body = request.get("body", {})
            
            # Extract parameters
            model = body.get("model", "mock-reranker")
            query = body.get("query", "")
            documents = body.get("documents", [])
            top_n = body.get("top_n")
            
            # Calculate mock relevance scores
            results = []
            for idx, doc in enumerate(documents):
                score = self._calculate_relevance(query, doc)
                results.append({
                    "index": idx,
                    "relevance_score": score
                })
            
            # Sort by score descending
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Apply top_n if specified
            if top_n is not None and top_n > 0:
                results = results[:top_n]
            
            logger.debug(f"Reranked {len(documents)} documents, returning {len(results)} results")
            
            return {
                "results": results,
                "model": model,
                "meta": {"api_version": "v1"}
            }
            
        except Exception as e:
            logger.error(f"Error in rerank handler: {e}")
            return {
                "error": str(e),
                "status": 400
            }
    
    def _calculate_relevance(self, query: str, document: str) -> float:
        """
        Calculate mock relevance score using simple heuristics.
        
        This is for testing only - uses basic text similarity.
        """
        if not query or not document:
            return 0.0
        
        # Convert to lowercase for comparison
        query_lower = query.lower()
        doc_lower = document.lower()
        
        # Simple scoring heuristics
        score = 0.0
        
        # 1. Exact query match
        if query_lower in doc_lower:
            score += 0.5
        
        # 2. Word overlap (Jaccard similarity)
        query_words = set(query_lower.split())
        doc_words = set(doc_lower.split())
        
        if query_words and doc_words:
            intersection = query_words & doc_words
            union = query_words | doc_words
            if union:
                jaccard = len(intersection) / len(union)
                score += jaccard * 0.3
        
        # 3. Keyword matching for common programming terms
        programming_keywords = {
            "function", "class", "method", "def", "import", 
            "return", "async", "await", "api", "endpoint"
        }
        
        query_has_keywords = bool(query_words & programming_keywords)
        doc_has_keywords = bool(doc_words & programming_keywords)
        
        if query_has_keywords and doc_has_keywords:
            score += 0.2
        
        # Ensure score is between 0 and 1
        return min(max(score, 0.0), 1.0)
    
    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming HTTP requests."""
        try:
            # Read request
            request_data = await reader.read(65536)  # 64KB max
            request_str = request_data.decode('utf-8')
            
            # Parse HTTP request
            lines = request_str.split('\r\n')
            if not lines:
                return
                
            # Get request line
            request_line = lines[0].split()
            if len(request_line) < 2:
                return
                
            method = request_line[0]
            path = request_line[1]
            
            # Find body (after empty line)
            body_str = ""
            body_start = False
            for line in lines:
                if body_start:
                    body_str += line
                elif line == "":
                    body_start = True
            
            # Parse JSON body if present
            body = {}
            if body_str:
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    pass
            
            # Route request
            if path == "/health":
                response_data = await self.health_handler({"method": method})
            elif path == "/rerank":
                response_data = await self.rerank_handler({"method": method, "body": body})
            else:
                response_data = {"error": "Not found", "status": 404}
            
            # Prepare response
            status = response_data.pop("status", 200)
            status_text = "OK" if status == 200 else "Bad Request" if status == 400 else "Not Found"
            response_body = json.dumps(response_data)
            
            # Send HTTP response
            response = f"HTTP/1.1 {status} {status_text}\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += "Connection: close\r\n"
            response += "\r\n"
            response += response_body
            
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def start(self) -> None:
        """Start the mock server."""
        logger.info(f"Starting mock rerank server on {self.host}:{self.port}")
        
        self.server = await asyncio.start_server(
            self.handle_request,
            self.host,
            self.port
        )
        
        logger.info(f"Mock rerank server listening on http://{self.host}:{self.port}")
        logger.info(f"Endpoints: /health, /rerank")
    
    async def stop(self) -> None:
        """Stop the mock server."""
        if self.server:
            logger.info("Stopping mock rerank server")
            self.server.close()
            await self.server.wait_closed()
            self.server = None
    
    async def serve_forever(self) -> None:
        """Run the server until interrupted."""
        if not self.server:
            await self.start()
        
        async with self.server:
            await self.server.serve_forever()


async def test_server():
    """Test the mock server with a sample request."""
    # Start server
    server = MockRerankServer()
    await server.start()
    
    try:
        # Give server time to start
        await asyncio.sleep(0.1)
        
        # Test health endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/health")
            print(f"Health check: {response.status_code} - {response.json()}")
            
            # Test rerank endpoint
            rerank_request = {
                "model": "test-model",
                "query": "python function definition",
                "documents": [
                    "def calculate_sum(a, b): return a + b",
                    "import numpy as np",
                    "class Calculator: pass",
                    "function add(x, y) { return x + y; }"
                ]
            }
            
            response = await client.post(
                "http://localhost:8001/rerank",
                json=rerank_request
            )
            print(f"Rerank response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
    finally:
        await server.stop()


def main():
    """Run the mock rerank server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mock reranking server for testing")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--test", action="store_true", help="Run test mode")
    
    args = parser.parse_args()
    
    if args.test:
        # Run test mode
        asyncio.run(test_server())
    else:
        # Run server
        server = MockRerankServer(host=args.host, port=args.port)
        try:
            asyncio.run(server.serve_forever())
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")


if __name__ == "__main__":
    main()