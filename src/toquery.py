from src.schemas import Understanding 

"""Convert Pydantic req into Text """



def convert(request: Understanding) -> str:
    return f"""
System Purpose:
{request.system_purpose}

Major Components:
{", ".join(request.major_components)}

Inputs:
{", ".join(request.inputs)}

Outputs:
{", ".join(request.outputs)}

Functional Requirements:
{", ".join(request.functional_requirements)}

Constraints:
{", ".join(request.constraints)}

Ambiguities:
{", ".join(request.ambiguities)}
""".strip()