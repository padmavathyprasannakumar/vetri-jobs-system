from services.resume_ai import analyse_resume_with_ai


text="""

Python developer with Django experience.
Bachelor Computer Science.
AWS certification.

"""


print(
    analyse_resume_with_ai(text)
)