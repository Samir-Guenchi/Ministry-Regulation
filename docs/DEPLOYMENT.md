# Deployment Guide

## Prerequisites

- Docker & Docker Compose
- OpenAI API Key
- 4GB+ RAM
- 10GB+ disk space

## Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

Required variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `NEO4J_PASSWORD`: Set a secure password for Neo4j

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### 3. Build Vector Store

```bash
# Build vector store from existing data
docker-compose exec api python scripts/build_vector_store.py

# Build knowledge graph
docker-compose exec api python scripts/build_graph.py
```

### 4. Test API

```bash
# Health check
curl http://localhost:8000/health

# Test query (Arabic)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "ما هي شروط التوظيف في الوزارة؟"}'

# Test query (English)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the employment requirements?"}'
```

## Manual Installation (Without Docker)

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Neo4j
# Download from: https://neo4j.com/download/

# Install Redis
# Ubuntu/Debian:
sudo apt-get install redis-server

# macOS:
brew install redis
```

### 2. Start Services

```bash
# Start Neo4j
neo4j start

# Start Redis
redis-server

# Start API
python -m uvicorn graphrag.api:app --reload
```

### 3. Build Indexes

```bash
# Build vector store
python scripts/build_vector_store.py

# Build knowledge graph
python scripts/build_graph.py
```

## Production Deployment

### Using Docker Compose (Recommended)

1. **Update docker-compose.yml**:
   - Set production passwords
   - Configure resource limits
   - Add SSL certificates

2. **Deploy**:
```bash
docker-compose -f docker-compose.yml up -d
```

### Using Kubernetes

See `k8s/` directory for Kubernetes manifests (to be created).

### Cloud Deployment

#### AWS
- Use ECS/EKS for containers
- ElastiCache for Redis
- Managed Neo4j on AWS Marketplace

#### Azure
- Use AKS for containers
- Azure Cache for Redis
- Neo4j on Azure Marketplace

#### GCP
- Use GKE for containers
- Memorystore for Redis
- Neo4j on GCP Marketplace

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Cache stats
curl http://localhost:8000/cache/stats
```

### Logs

```bash
# API logs
docker-compose logs -f api

# Neo4j logs
docker-compose logs -f neo4j

# Redis logs
docker-compose logs -f redis
```

### Metrics

Add Prometheus/Grafana for production monitoring:
- Request latency
- Cache hit rate
- Error rates
- Resource usage

## Backup & Recovery

### Neo4j Backup

```bash
# Backup
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j-backup.dump

# Restore
docker-compose exec neo4j neo4j-admin load --from=/backups/neo4j-backup.dump --database=neo4j --force
```

### Redis Backup

```bash
# Backup (RDB snapshot)
docker-compose exec redis redis-cli SAVE

# Copy backup
docker cp ministry-redis:/data/dump.rdb ./backups/
```

### Vector Store Backup

```bash
# Simply copy the directory
cp -r vector_store/ backups/vector_store-$(date +%Y%m%d)/
```

## Scaling

### Horizontal Scaling

1. **API**: Run multiple API instances behind load balancer
2. **Redis**: Use Redis Cluster for distributed caching
3. **Neo4j**: Use Neo4j Causal Cluster for HA

### Vertical Scaling

Adjust resource limits in docker-compose.yml:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## Troubleshooting

### API won't start
- Check .env file exists and has valid API keys
- Verify Neo4j and Redis are running
- Check logs: `docker-compose logs api`

### Slow queries
- Check cache hit rate: `curl http://localhost:8000/cache/stats`
- Verify vector store is built
- Check Neo4j indexes

### Out of memory
- Increase Docker memory limits
- Reduce batch sizes in scripts
- Enable Redis eviction policy

## Security Checklist

- [ ] Change default Neo4j password
- [ ] Set Redis password
- [ ] Use HTTPS in production
- [ ] Enable API rate limiting
- [ ] Restrict network access
- [ ] Regular security updates
- [ ] Monitor for suspicious queries
- [ ] Backup encryption

## Maintenance

### Regular Tasks

- **Daily**: Check logs for errors
- **Weekly**: Review cache hit rates
- **Monthly**: Update dependencies
- **Quarterly**: Security audit

### Updates

```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d
```
