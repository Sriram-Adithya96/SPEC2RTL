from dotenv import load_dotenv
from PIL.ImagePalette import load
from langchain_openai import ChatOpenAI
import os 
import dotenv 

load_dotenv()

def get_llm():
    return ChatOpenAI(
        model= "openai/gpt-oss-120b" , 
        api_key=os.getenv("SPEC2RTL_OPENROUTER_KEY") ,   
        base_url="https://openrouter.ai/api/v1",
        temperature=0 
    )