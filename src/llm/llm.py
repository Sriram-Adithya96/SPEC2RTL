from dotenv import load_dotenv

from langchain_openai import ChatOpenAI


import os 
import dotenv 

load_dotenv()

def get_llm():
    llm =  ChatOpenAI(
      model="openrouter/free", 
        api_key=os.getenv("SPEC2RTL_OPENROUTER_KEY") ,   
        base_url="https://openrouter.ai/api/v1",
        temperature=0 
    )
    

    return llm
