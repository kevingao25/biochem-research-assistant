.PHONY: help start stop restart status logs health setup format lint test test-cov clean

help:
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

start: ## Build and start all services
	docker compose up --build -d

stop: ## Stop all services
	docker compose down

restart: ## Restart services without rebuild
	docker compose restart

status: ## Show container status
	docker compose ps

logs: ## Stream logs from all services
	docker compose logs -f

health: ## Check all service health endpoints
	@printf "%-12s %s\n" "Service" "Status"
	@printf "%-12s %s\n" "-------" "------"
	@curl -sf http://localhost:8000/api/v1/health > /dev/null \
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
	@docker exec biochem-research-assistant-postgres-1 pg_isready -q 2>/dev/null \
		&& printf "%-12s \033[32m✓ healthy\033[0m\n" "Postgres" \
		|| printf "%-12s \033[31m✗ not responding\033[0m\n" "Postgres"

setup: ## Install Python dependencies
	uv sync

format: ## Format code with ruff
	uv run ruff format src/ tests/ api/

lint: ## Lint and type check
	uv run ruff check --fix src/ tests/ api/
	uv run mypy src/

test: ## Run all tests
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage report
	uv run pytest tests/ --cov=src --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

clean: ## Stop services and remove volumes
	docker compose down -v
	docker system prune -f
