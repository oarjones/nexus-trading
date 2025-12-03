# MCP Servers Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
COPY mcp_servers/requirements.txt mcp_servers_requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r mcp_servers_requirements.txt

# Copy application code
COPY config/ config/
COPY src/ src/
COPY mcp_servers/ mcp_servers/

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app

USER mcp

# Default command (override in docker-compose)
CMD ["python", "-m", "market_data.server"]
