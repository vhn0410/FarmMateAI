## Project structure
```
farm-mate-ai/
├── frontend/                  # Code Frontend (Next.js/React/Vue)
└── backend/
    ├── .env                   # Chứa các biến môi trường (DATABASE_URL, API_KEY...)
    ├── requirements.txt       # Quản lý thư viện (hoặc pyproject.toml)
    ├── main.py                # Entrypoint của FastAPI (Nằm GỌN trong backend)
    ├── scripts/               # Các task chạy ngầm / offline
    │   └── cron_ingest_drive.py 
    │   └── cron_evaluate_rag.py
    ├── evaluations/ 
    │   └── dataset
    │   └── 01_run_experiments.py
    │   └── 02_ragas_evaluator.py
    │
    ├── tests/                # THƯ MỤC TEST MỚI
    ├── __init__.py
    ├── conftest.py       # Nơi chứa các cấu hình dùng chung (Fixtures)
    ├── unit/             # Test từng hàm nhỏ (Rất nhanh)
    │   ├── test_vector_db.py
    │   └── test_weather_skill.py
    └── integration/      # Test API Endpoints (Gắn kết các thành phần)
    │   └── test_chat_api.py
    └── app/
        ├── api/               # 1. PRESENTATION LAYER (FastAPI Controllers)
        │   └── v1/
        │       ├── endpoints/
        │       │   ├── chat.py      # Xử lý HTTP Request/Response cho chat
        │       │   └── documents.py # API trigger update dữ liệu
        │       └── router.py
        │
        ├── application/       # 2. USE CASES LAYER (Logic luồng công việc)
        │   ├── chat/
        │   │   └── use_case.py      # Điều phối: Lấy history -> Gọi Agent -> Lưu DB
        │   │   └── response_enhancer.py      # Điều phối: Lấy history -> Gọi Agent -> Lưu DB

        │   └── documents/
        │       └── use_case.py      # Luồng xử lý update tài liệu
        │
        ├── domain/            # 3. CORE LAYER (Thực thể & Giao diện cốt lõi - KHÔNG phụ thuộc lib ngoài)
        │   ├── entities/            
        │   │   ├── message.py       # Object tin nhắn
        │   │   └── conversation.py  # Object phiên chat
        │   └── interfaces/          
        │       ├── llm.py           # Interface cho LLM
        │       ├── vector_db.py     # Interface cho VectorDB (Retriever)
        │       ├── document_provider.py     
        │       └── repository.py    # Interface lưu trữ Database
        │
        ├── infrastructure/    # 4. IMPLEMENTATION LAYER (Code thực thi giao tiếp ra ngoài)
        │   ├── db/
        │   │   └── postgres_repo.py # Thực thi giao tiếp PostgreSQL (implement repository.py)
        │   ├── vector_store/
        │   │   └── pgvector_db.py   # Khởi tạo và kết nối PGVector (implement vector_db.py)
        │   ├── llm/
        │   │   └── openai_client.py # Kết nối API OpenAI (implement llm.py)
        │   └── external/
        │       └── google_drive.py  # Hàm tải dữ liệu từ Google Drive
        │
        ├── agents/            # 5. ORCHESTRATION & SKILLS (Trái tim AI)
        │   ├── orchestrator.py      # Xây dựng luồng tác vụ cho agent (vd: sử dụng LangGraph làm supervisor)
        │   ├── memory.py            # Quản lý ngữ cảnh hội thoại cho Bot
        │   └── skills/              # Nơi chứa các công cụ mở rộng (Plug-and-play)
        │       ├── base.py          # Interface chung (BaseSkill)
        │       ├── rag_agriculture/ 
        │       │   └── tool.py      # RAG skill tích hợp retriever
        │       ├── iot_crawler/
        │       │   └── tool.py      # Skill gọi API quan trắc
        │       └── cv_service/
        │           └── tool.py      # Skill gọi API phân tích ảnh
        │
        ├── schemas/           # DATA TRANSFER OBJECTS (DTOs / Pydantic Models)
        │   ├── chat_dto.py          # Schema validate request/response ở API
        │   └── document_dto.py
        │
        └── core/              # CROSS-CUTTING (Các cấu hình hệ thống dùng chung)
            ├── config.py            # Load biến môi trường từ .env bằng pydantic-settings
            ├── security.py          # Phân quyền, JWT
            └── exceptions.py        # Xử lý lỗi tập trung
```
