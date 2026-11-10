import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openrouter import ChatOpenRouter

import os 
import dotenv 

load_dotenv()

def get_llm():
   llm =ChatOpenRouter(
     model="deepseek/deepseek-v4-flash",
     api_key=os.getenv("SPEC2RTL_OPENROUTER_KEY") # type: ignore
   )
   return llm 



"""
def get_llm():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0
    )
    return llm

def reasoning_llm():
    llm = ChatGoogleGenerativeAI(
        model = "gemini-3.8-flash", 
        thinking_level= "high" , 
        api_key = os.getenv("GEMINI_API_KEY")
    )
    return llm

"""