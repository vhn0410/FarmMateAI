import pandas as pd
import os

csv_path = r"c:\My_Data\University-courses\thesis\source\farm-mate-ai\backend\rag_evaluation_results.csv"
md_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\d646230d-5e97-4a15-a69e-acd93566e48c\evaluation_report.md"

df = pd.read_csv(csv_path)

md_content = "# Báo cáo Đánh giá Naive RAG vs Graph RAG\n\n"
md_content += "Dưới đây là kết quả của bài kiểm tra A/B Testing giữa hai luồng truy xuất dữ liệu. Điểm số được chấm bởi giám khảo AI (LLM-as-a-judge) với thang điểm tuyệt đối là 30.\n\n"

for index, row in df.iterrows():
    md_content += f"## Câu hỏi {row['ID']}: {row['Question']}\n"
    md_content += f"**Loại câu hỏi:** {row['Type']}\n\n"
    
    md_content += "| Tiêu chí | Naive RAG | Graph RAG |\n"
    md_content += "| :--- | :---: | :---: |\n"
    md_content += f"| **Trung thực (Faithfulness)** | {row['Naive_Faithfulness']}/10 | {row['Graph_Faithfulness']}/10 |\n"
    md_content += f"| **Đầy đủ (Comprehensiveness)** | {row['Naive_Comprehensiveness']}/10 | {row['Graph_Comprehensiveness']}/10 |\n"
    md_content += f"| **Logic đa bước (Reasoning)** | {row['Naive_Reasoning']}/10 | {row['Graph_Reasoning']}/10 |\n"
    md_content += f"| **TỔNG ĐIỂM** | **{row['Naive_Total']}/30** | **{row['Graph_Total']}/30** |\n\n"
    
    md_content += "### Lời nhận xét của Giám khảo AI\n"
    md_content += f"> **Naive RAG:** {row['Judge_Explanation_Naive']}\n>\n"
    md_content += f"> **Graph RAG:** {row['Judge_Explanation_Graph']}\n\n"
    md_content += "---\n\n"

with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)

# Update artifact metadata (will be done manually via tool call next)
