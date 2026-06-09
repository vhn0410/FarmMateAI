-- 1. Thêm cột tsvector có tên là 'fts_vector'. 
-- GENERATED ALWAYS AS nghĩa là nó sẽ tự động lấy dữ liệu từ cột 'document' để băm ra.
ALTER TABLE langchain_pg_embedding 
ADD COLUMN fts_vector tsvector 
GENERATED ALWAYS AS (to_tsvector('simple', document)) STORED;

-- 2. Đánh Index (GIN) cho cột này. ĐÂY LÀ BÍ QUYẾT ĐỂ TÌM KIẾM TỐC ĐỘ BÀN THỜ.
CREATE INDEX idx_fts_search ON langchain_pg_embedding USING GIN (fts_vector);