.PHONY: dev prod down logs build-dev build-prod

# Chạy môi trường Development (Hot-reload)
dev:
	docker-compose -f docker-compose.dev.yml up -d

# Build lại môi trường Development (Khi có thay đổi về package)
build-dev:
	docker-compose -f docker-compose.dev.yml up -d --build

# Chạy môi trường Production
prod:
	docker-compose up -d

# Build lại môi trường Production
build-prod:
	docker-compose up -d --build

# Dọn dẹp tắt tất cả các container
down:
	docker-compose -f docker-compose.dev.yml down
	docker-compose down

# Xem log của hệ thống
logs:
	docker-compose -f docker-compose.dev.yml logs -f || docker-compose logs -f
