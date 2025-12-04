# Autonomous Agents - Phase 3

This directory contains the autonomous trading agent system.

## Architecture

The agent system follows a distributed, event-driven architecture using Redis pub/sub for inter-agent communication.

### Components

1. **Base Infrastructure**
   - `schemas.py` - Pydantic models for all message types
   - `messaging.py` - Redis pub/sub MessageBus
   - `base.py` - Abstract BaseAgent class
   - `config.py` - Configuration loading utilities

2. **Specialized Agents** (to be implemented)
   - `technical.py` - Technical Analyst Agent
   - `risk_manager.py` - Risk Manager Agent
   - `orchestrator.py` - Orchestrator Agent

### Communication Channels

| Channel | Publisher | Subscribers | Purpose |
|---------|-----------|-------------|---------|
| `signals` | Technical Analyst | Orchestrator | Trading signals |
| `risk:requests` | Orchestrator | Risk Manager | Validation requests |
| `risk:responses` | Risk Manager | Orchestrator | Approval/rejection |
| `decisions` | Orchestrator | Logger, Execution | Final decisions |
| `alerts` | Any | Logger, Telegram | Critical alerts |

### Message Flow

```
Technical Analyst
       ↓ (signals)
   Orchestrator ────→ Risk Manager (risk:requests)
       ↓                    ↓
   (waits)           (risk:responses)
       ↓
   Decision (decisions channel)
```

## Development

### Running Tests

```bash
# All agent tests
pytest tests/agents/ -v

# Specific test file
pytest tests/agents/test_schemas.py -v

# With coverage
pytest tests/agents/ --cov=src/agents
```

### Configuration

Edit `config/agents.yaml` to configure agents. Environment variables can be used with `${VAR_NAME}` syntax.

### Creating a New Agent

1. Inherit from `BaseAgent`
2. Implement `async setup()` - subscribe to channels
3. Implement `async process()` - main logic loop
4. Register in startup script

Example:
```python
from src.agents import BaseAgent, MessageBus

class MyAgent(BaseAgent):
    async def setup(self):
        self.bus.subscribe("my_channel", self.handle_message)
    
    async def process(self):
        # Do work
        await asyncio.sleep(10)
    
    async def handle_message(self, msg):
        print(f"Received: {msg}")
```

## Safety Features

- **Kill Switch**: Automatic shutdown if drawdown > 15%
- **Hardcoded Limits**: Risk limits cannot be modified at runtime
- **Health Checks**: All agents report status every 60s
- **Audit Log**: All decisions logged to Redis
- **Error Handling**: Automatic restart with exponential backoff

## Next Steps

1. Implement Technical Analyst Agent
2. Implement Risk Manager Agent
3. Implement Orchestrator Agent
4. Create integration tests
5. Create startup script
