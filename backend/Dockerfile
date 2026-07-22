FROM python:3.14-slim

# Cài đặt uv từ image chính thức
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết (cho psycopg2 và scikit-network C++ extensions)
RUN apt-get update && apt-get install -y libpq-dev gcc g++ python3-dev && rm -rf /var/lib/apt/lists/*

# Copy các file quản lý thư viện trước để tận dụng Docker cache
COPY pyproject.toml uv.lock ./

# Khởi tạo môi trường ảo và cài đặt thư viện production-only (frozen để chính xác theo uv.lock)
# uv sẽ tự động tạo thư mục .venv
RUN uv sync --frozen --no-dev

# Copy toàn bộ mã nguồn
COPY . .

# Thiết lập biến môi trường
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Expose port 8000
EXPOSE 8000

# Chạy FastAPI thông qua uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
