# 🚀 Production AI Agent

Production-ready AI agent với đầy đủ security, rate limiting, cost guard, và stateless design.

## ✨ Features

- ✅ **API Key Authentication** - Bảo vệ endpoint
- ✅ **Rate Limiting** - 10 requests/minute per user (Redis-based)
- ✅ **Cost Guard** - Budget tracking để tránh bill bất ngờ
- ✅ **Stateless Design** - Conversation history trong Redis
- ✅ **Health Checks** - Liveness & readiness probes
- ✅ **Graceful Shutdown** - Xử lý SIGTERM signal
- ✅ **Structured Logging** - JSON format
- ✅ **Docker Support** - Multi-stage build
- ✅ **Load Balancing** - Nginx reverse proxy
- ✅ **Scalable** - Chạy nhiều instances

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

## 📁 Project Structure

```
my-production-agent/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration management
│   ├── auth.py          # API key authentication
│   ├── rate_limiter.py  # Redis-based rate limiting
│   └── cost_guard.py    # Budget tracking
├── Dockerfile           # Multi-stage Docker build
├── docker-compose.yml   # Orchestration (agent + Redis + Nginx)
├── nginx.conf           # Load balancer config
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── .dockerignore        # Docker build optimization
└── SETUP_GUIDE.md       # Detailed setup instructions
```

## 🚀 Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Start Redis:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

3. **Copy environment variables:**
```bash
cp .env.example .env
```

4. **Run application:**
```bash
uvicorn app.main:app --reload
```

5. **Test:**
```bash
curl -H "X-API-Key: secret-key-123" http://localhost:8000/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"Hello","user_id":"test"}'
```

### Docker Compose (Recommended)

1. **Start all services:**
```bash
docker compose up
```

2. **Scale to 3 instances:**
```bash
docker compose up --scale agent=3
```

3. **Test:**
```bash
curl http://localhost/health
curl -H "X-API-Key: secret-key-123" http://localhost/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"Hello from Docker!","user_id":"test"}'
```

## 📡 API Endpoints

### `GET /`
Root endpoint với app info.

### `GET /health`
Liveness probe - kiểm tra container còn sống không.

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 123.4,
  "version": "1.0.0",
  "timestamp": "2026-04-17T10:30:00Z"
}
```

### `GET /ready`
Readiness probe - kiểm tra app sẵn sàng nhận traffic không.

**Response:**
```json
{
  "ready": true,
  "redis": "connected"
}
```

### `POST /ask`
Main agent endpoint - xử lý câu hỏi.

**Headers:**
- `X-API-Key`: API key (required)
- `Content-Type`: application/json

**Request:**
```json
{
  "question": "What is Docker?",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "question": "What is Docker?",
  "answer": "Docker is...",
  "user_id": "user_1234",
  "timestamp": "2026-04-17T10:30:00Z"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing API key
- `429 Too Many Requests` - Rate limit exceeded
- `402 Payment Required` - Daily budget exceeded
- `503 Service Unavailable` - Redis connection failed or global budget exceeded

## 🔒 Security Features

### Authentication
API key authentication via `X-API-Key` header.

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/ask
```

### Rate Limiting
- **Algorithm**: Sliding Window Counter (Redis-based)
- **Limit**: 10 requests/minute per user (configurable)
- **Response**: 429 with `Retry-After` header

### Cost Guard
- **Daily budget**: $1.00 per user (configurable)
- **Global budget**: $10.00 per day (configurable)
- **Warning**: Alert at 80% usage
- **Block**: 402 when budget exceeded

## ⚙️ Configuration

All configuration via environment variables (`.env` file):

```bash
# Server
HOST=0.0.0.0
PORT=8000

# Redis
REDIS_URL=redis://redis:6379

# Security
AGENT_API_KEY=secret-key-123

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10

# Cost Guard
DAILY_BUDGET_USD=1.0
MONTHLY_BUDGET_USD=10.0

# Logging
LOG_LEVEL=INFO
```

## 🐳 Docker

### Build Image
```bash
docker build -t my-agent:latest .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  -e AGENT_API_KEY=secret-key-123 \
  my-agent:latest
```

### Multi-stage Build Benefits
- **Stage 1 (builder)**: Install dependencies
- **Stage 2 (runtime)**: Copy only necessary files
- **Result**: Smaller image size (~150MB vs ~500MB)

## 📊 Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Redis Stats
```bash
docker compose exec redis redis-cli

# Check keys
KEYS *

# Check rate limit
ZRANGE ratelimit:user_1234 0 -1 WITHSCORES

# Check budget
GET budget:user_1234:2026-04-17

# Check conversation history
LRANGE history:user_1234 0 -1
```

### Logs
```bash
# All services
docker compose logs -f

# Agent only
docker compose logs -f agent

# Nginx only
docker compose logs -f nginx
```

## 🚢 Deployment

### Railway
```bash
railway login
railway init
railway add redis
railway variables set AGENT_API_KEY=your-secret-key
railway up
railway domain
```

### Render
1. Push code to GitHub
2. Create `render.yaml` (see SETUP_GUIDE.md)
3. Connect repo on render.com
4. Auto-deploy from blueprint

### GCP Cloud Run
```bash
gcloud builds submit --config cloudbuild.yaml
gcloud run deploy --image gcr.io/PROJECT/agent
```

## 🧪 Testing

### Test Authentication
```bash
# Without key (should fail)
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# With key (should succeed)
curl -H "X-API-Key: secret-key-123" http://localhost:8000/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"Hello","user_id":"test"}'
```

### Test Rate Limiting
```bash
# Send 15 requests (limit is 10)
for i in {1..15}; do
  curl -H "X-API-Key: secret-key-123" http://localhost:8000/ask \
    -X POST -H "Content-Type: application/json" \
    -d '{"question":"Test '$i'","user_id":"test"}'
  echo ""
done
```

### Test Stateless Design
```bash
# Request 1
curl -H "X-API-Key: secret-key-123" http://localhost:8000/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"My name is Alice","user_id":"alice"}'

# Request 2 (history should persist in Redis)
curl -H "X-API-Key: secret-key-123" http://localhost:8000/ask \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"What is my name?","user_id":"alice"}'
```

## 🐛 Troubleshooting

### Redis Connection Failed
```bash
# Check Redis is running
docker compose ps redis

# Test connection
docker compose exec redis redis-cli ping
```

### Rate Limit Not Working
```bash
# Check Redis keys
docker compose exec redis redis-cli KEYS "ratelimit:*"
```

### 502 Bad Gateway
```bash
# Check agent is running
docker compose ps agent

# Check agent logs
docker compose logs agent
```

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [12-Factor App](https://12factor.net/)

## 📝 License

MIT

## 👨‍💻 Author

VinUniversity AICB-P1 2026
