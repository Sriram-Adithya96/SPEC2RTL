from pydantic import BaseModel 
from typing import List, Optional, Dict 



class Understanding(BaseModel):
    system_purpose: str
    major_components: List[str]
    inputs: List[str]
    outputs: List[str]
    functional_requirements: List[str]
    constraints: List[str]
    ambiguities: List[str]


