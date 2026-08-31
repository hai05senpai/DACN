import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

try:
    # Dùng model gemini-1.5-flash chuẩn 
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key
    )
    res = llm.invoke("Ping!")
    print("\n✅ XÁC NHẬN: API Key & Gemini Model hoạt động 100%!")
    print(f"Phản hồi từ Gemini: {res.content}")
except Exception as e:
    print(f"\n❌ KẾT NỐI THẤT BẠI: {e}")