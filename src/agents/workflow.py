from src.agents.description import describe_component
from src.agents.verification import verify_description
from src.agents.reflection import reflect_on_verification

MAX_RETRIES = 3


def run_reflection_workflow(component, source_chunks):

    description = describe_component(component)

    for attempt in range(MAX_RETRIES + 1):

        print(f"\nVerification attempt {attempt + 1}")

        verification = verify_description(
            source_chunks,
            description
        )

        if verification.valid:
            print("Verification successful!")

            return {
                "success": True,
                "description": description,
                "verification": verification
            }

        if attempt == MAX_RETRIES:
            print("Maximum retries reached.")

            return {
                "success": False,
                "description": description,
                "verification": verification
            }

        reflection = reflect_on_verification(
            source_chunks,
            description,
            verification
        )

        print("Reflection feedback:", reflection.feedback)

        if not reflection.needs_revision:
            print("No supported revision available.")

            return {
                "success": False,
                "description": description,
                "verification": verification,
                "reflection": reflection
            }

        description = describe_component(
            component,
            feedback=reflection.feedback,
            previous_description=description
        )