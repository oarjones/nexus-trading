# Docker Compose for MCP Servers

This docker-compose configuration includes all infrastructure services and MCP servers.

## Services

### Infrastructure
- **postgres**: TimescaleDB (port 5432)
- **redis**: Redis cache (port 6379)
- **influxdb**: InfluxDB (port 8086)
- **grafana**: Grafana dashboards (port 3000)

### MCP Servers
- **mcp-market-data**: Market data server (stdio)
- **mcp-technical**: Technical analysis server (stdio)
- **mcp-risk**: Risk management server (stdio)
- **mcp-ibkr**: IBKR trading server (stdio, optional)

## Usage

### Start all services:
```bash
docker-compose up -d
```

### Start specific services:
```bash
# Infrastructure only
docker-compose up -d postgres redis influxdb grafana

# Specific MCP server
docker-compose up -d mcp-market-data
docker-compose up -d mcp-technical
docker-compose up -d mcp-risk

# IBKR (requires IB Gateway running on host)
docker-compose up -d mcp-ibkr
```

### View logs:
```bash
docker-compose logs -f mcp-market-data
docker-compose logs -f mcp-ibkr
```

### Stop services:
```bash
docker-compose down
```

### Rebuild after code changes:
```bash
docker-compose build
docker-compose up -d
```

## IBKR Server Notes

The IBKR server connects to IB Gateway running on your **host machine** (not in Docker).

**Configuration:**
- Use `host.docker.internal` as IBKR_HOST (automatically configured)
- Default port: 4002 (IB Gateway paper trading)
- Make sure IB Gateway is running before starting mcp-ibkr

**Environment Variables:**
```bash
IBKR_HOST=host.docker.internal  # Connects to host machine
IBKR_PORT=4002                  # IB Gateway paper port
IBKR_CLIENT_ID=1
```

## Networking

All MCP servers are on the `trading_network` bridge network, allowing them to communicate with each other and infrastructure services.

## Healthchecks

Infrastructure services have healthchecks configured:
- postgres: `pg_isready`
- redis: `redis-cli ping`
- influxdb: HTTP ping

MCP servers depend on healthy infrastructure services.
