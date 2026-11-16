import contextlib
import io

from src.ingestion import ingest_spec
from src.agents.understanding import understand_specification


SPEC_PATH = r"C:\Users\srira\OneDrive\Desktop\ps spec2rtl\fake_spec2rtl_spec (1).docx"

documents, _, _ = ingest_spec(SPEC_PATH)
with contextlib.redirect_stdout(io.StringIO()):
    result = understand_specification(documents)
print(result.major_components)
