import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI


import os 
import dotenv 

load_dotenv()

"""def get_llm():
    llm =  ChatOpenAI(
      model="openrouter/free", 
         #api_key=os.getenv("SPEC2RTL_OPENROUTER_KEY") ,   
        base_url="https://openrouter.ai/api/v1",
        temperature=0 
    )
    

    return llm"""

def get_llm():
    llm =ChatGroq(
        model = "openai/gpt-oss-120b",
        temperature=0,
        

    )
    return llm


def reasoning_llm():
    llm = ChatGoogleGenerativeAI(
        model = "gemini-3.8-flash", 
        thinking_level= "high" , 
        api_key = os.getenv("GEMINI_API_KEY")
    )
    return llm

 