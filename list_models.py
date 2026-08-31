import os
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Chưa cấu hình GEMINI_API_KEY trong file .env!")
else:
    try:
        client = genai.Client(api_key=api_key)
        
        print("🔍 Đang truy vấn danh sách model khả dụng...\n")
        models = client.models.list()
        
        print("TÊN MODEL (BẠN CHỌN 1 TÊN ĐỂ DÙNG TRONG CODE):")
        print("-" * 55)
        
        for m in models:
            # Lấy tên model chuẩn (loại bỏ tiền tố models/)
            name = m.name.replace("models/", "") if hasattr(m, 'name') else str(m)
            # Chỉ lọc ra các model thuộc dòng gemini
            if "gemini" in name.lower():
                print(f"👉 {name}")
                
    except Exception as e:
        print(f"❌ Lỗi truy vấn API: {e}")