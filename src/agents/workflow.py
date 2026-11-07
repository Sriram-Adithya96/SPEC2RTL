
from src.agents.description import describe_component
from src.agents.code import generate_code
from src.agents.verification import verify_code
from src.agents.reflection import reflect_on_verification

MAX_RETRIES = 3


def run_reflection_workflow(component, source_chunks) -> dict:
    description = describe_component(component)

    generated_code = generate_code(description)

    for attempt in range(MAX_RETRIES + 1):

        print(f"\nVerification attempt {attempt + 1}")

        verification = verify_code(
            source_chunks,
            generated_code
        )

        if verification.valid:
            print("Verification successful!")

            return {
                "success": True,
                "description": description,
                "code": generated_code,
                "verification": verification
            }

        if attempt == MAX_RETRIES:
            print("Maximum retries reached.")

            return {
                "success": False,
                "description": description,
                "code": generated_code,
                "verification": verification
            }

        reflection = reflect_on_verification(
            source_chunks,
            generated_code,
            verification
        )

        print("Reflection feedback:", reflection.feedback)

        if not reflection.needs_revision:
            print("No supported revision available.")

            return {
                "success": False,
                "description": description,
                "code": generated_code,
                "verification": verification,
                "reflection": reflection
            }

        generated_code = generate_code(
            description,
            feedback=reflection.feedback,
            previous_code=generated_code
        )
    raise RuntimeError("Workflow exited unexpectedly.")