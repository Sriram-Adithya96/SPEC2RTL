import tempfile
from pathlib import Path

from src.agents.pseudocode_to_python import convert_pseudocode

fixture_path = Path(__file__).parent / "fixtures" / "legacy_apu_simulation.pseudo"
pseudocode = fixture_path.read_text(encoding="utf-8").splitlines()

print("Pseudocode lines:", len(pseudocode))

with tempfile.TemporaryDirectory() as output_dir:
    try:
        python_code = convert_pseudocode(pseudocode)

        generated_path = Path(output_dir) / "generated_python.py"
        generated_path.write_text(python_code, encoding="utf-8")

        print("Conversion successful!")
        print(f"Saved to {generated_path}")

    except Exception as e:
        print("Conversion failed:", type(e).__name__)
        print(e)
