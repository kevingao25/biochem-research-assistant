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
	@echo "Checking service health..."
	@curl -s http://localhost:8000/api/v1/health | python3 -m json.tool || echo "API not responding"
	@curl -s http://localhost:6333/healthz || echo "Qdrant not responding"
	@curl -s http://localhost:8080/api/v2/monitor/health || echo "Airflow not responding"
	@curl -s http://localhost:11434/api/version | python3 -m json.tool || echo "Ollama not responding"

setup: ## Install Python dependencies
	uv pip install -r api/requirements.txt -r requirements-dev.txt

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
