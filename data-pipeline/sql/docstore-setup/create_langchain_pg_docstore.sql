CREATE TABLE public.langchain_pg_docstore (
  id character varying NOT NULL,      -- ID của Parent Document (UUID)
  document jsonb NOT NULL,            -- Chứa nội dung text và metadata của Parent
  CONSTRAINT langchain_pg_docstore_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;