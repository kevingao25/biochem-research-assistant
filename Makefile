.PHONY: start stop restart logs status health build

# Build and start all services in the background (-d = detached)
start:
	docker compose up --build -d

# Stop all services (keeps volumes — your data is safe)
stop:
	docker compose down

# Stop and start again (useful after config changes)
restart:
	docker compose restart

# Stream logs from all services (Ctrl+C to exit)
logs:
	docker compose logs -f

# Show the current status of each container
status:
	docker compose ps

# Quick health check — prints a clean status summary
health:
	@printf "%-12s %s\n" "Service" "Status"
	@printf "%-12s %s\n" "-------" "------"
	@curl -sf http://localhost:8000/health > /dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "API" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "API"
	@curl -sf http://localhost:6333/healthz > /dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Qdrant" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Qdrant"
	@curl -sf http://localhost:8080/api/v2/monitor/health > /dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Airflow" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Airflow"
	@curl -sf http://localhost:11434/api/version > /dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Ollama" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Ollama"
	@docker exec biochem-research-assistant-redis-1 redis-cli ping > /dev/null 2>&1 \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Redis" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Redis"
	@curl -sf http://localhost:5432 > /dev/null 2>&1; \
		docker exec biochem-research-assistant-postgres-1 pg_isready -q 2>/dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Postgres" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Postgres"

# Build images without starting containers
build:
	docker compose build
