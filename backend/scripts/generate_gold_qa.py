import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

def generate_gold_qa(text: str, num_questions: int = 10) -> List[Dict]:
    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        api_key=settings.openai_api_key, 
        base_url=settings.openai_api_base,
        temperature=0.2
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Bạn là một chuyên gia đánh giá AI và nông nghiệp. Dựa vào văn bản cung cấp, hãy tạo ra {num_questions} cặp Câu hỏi (question) và Câu trả lời tham chiếu (answer) đạt chất lượng cao (Gold Standard). Đảm bảo các câu hỏi phân bổ đủ 3 loại: Hỏi ý chính (Factoid), Hỏi tổng hợp (Reasoning), Hỏi suy luận (Complex).\nTrả về JSON chuẩn có cấu trúc: [ {{\"question\": \"...\", \"answer\": \"...\"}} ]\nChỉ trả về mảng JSON, không giải thích gì thêm."),
        ("user", "Văn bản:\n{text}")
    ])
    
    chain = prompt | llm
    print(f"Đang sinh {num_questions} câu hỏi Gold QA từ {len(text)} ký tự đầu tiên...")
    
    # Pass the entire document (gpt-4o-mini supports 128k context, this is ~40k tokens)
    response = chain.invoke({"text": text, "num_questions": num_questions})
    content = response.content.strip()
    
    if content.startswith("```json"): content = content[7:-3]
    elif content.startswith("```"): content = content[3:-3]
    
    return json.loads(content)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Tên file markdown trong thư mục data/knowledge_base/processed/")
    parser.add_argument("--num", type=int, default=10, help="Số lượng câu hỏi cần sinh")
    args = parser.parse_args()
    
    base_dir = Path("data/knowledge_base/processed")
    file_path = base_dir / args.file
    
    if not file_path.exists():
        if (base_dir / f"{args.file}.md").exists():
            file_path = base_dir / f"{args.file}.md"
        else:
            print(f"Lỗi: Không tìm thấy file {file_path}")
            sys.exit(1)
            
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    qa_list = generate_gold_qa(text, args.num)
    
    output_dir = Path("evaluate/gold_qa")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{Path(args.file).stem}_gold_qa.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(qa_list, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Đã tạo thành công {len(qa_list)} câu hỏi. Lưu tại: {output_file.resolve()}")
    print("Vui lòng mở file JSON này ra và rà soát/tinh chỉnh lại bằng tay trước khi chạy Benchmark!")

if __name__ == "__main__":
    main()
