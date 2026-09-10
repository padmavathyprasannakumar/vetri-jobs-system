"""
AI Job Matching engine.

Scores how well a job fits a student by comparing:
- Skills (student's structured Skill list + free-text skills field
  vs job.skills_required)
- Education (student.course/department vs job.qualification_required)
- Experience (student.experience vs job.experience_required)
- Preferred location (student.preferred_location vs job.location)
- Expected salary (student.expected_salary vs job.salary, best-effort)
- Career interest (student.career_interest vs job.title/description)

Returns (score: int 0-100, reasons: list[str]) so callers can show
both a "Match Score: 91%" style badge and a reasons list like:
"Java - Match", "B.Tech - Match", "Fresher - Match".
"""

import re


WEIGHTS = {
    "skills": 40,
    "education": 15,
    "experience": 15,
    "location": 15,
    "salary": 10,
    "career_interest": 5,
}


def _clean_list(text):

    if not text:

        return []

    return [
        part.strip()
        for part in re.split(r"[,\n/]", text)
        if part.strip()
    ]


def _get_student_skills(student):

    names = set()

    try:

        names.update(

            s.lower()
            for s in student.skills_list.values_list(
                "name", flat=True
            )
        )

    except Exception:

        pass

    names.update(

        s.lower()
        for s in _clean_list(getattr(student, "skills", ""))
    )

    return names


def _numbers_in(text):

    if not text:

        return []

    return [int(n) for n in re.findall(r"\d+", text)]


def compute_job_match(student, job):

    if not student or not job:

        return 0, []

    score = 0

    reasons = []


    # ---------------- SKILLS ----------------

    student_skills = _get_student_skills(student)

    job_skills = set(

        s.lower()
        for s in _clean_list(job.skills_required)
    )

    if job_skills:

        matched = student_skills & job_skills

        skill_ratio = len(matched) / len(job_skills)

        score += WEIGHTS["skills"] * skill_ratio

        for skill in sorted(matched):

            reasons.append(f"{skill.title()} \u2013 Match")

    else:

        # no skills specified on the job - don't penalise
        score += WEIGHTS["skills"] * 0.5


    # ---------------- EDUCATION ----------------

    qualification = (job.qualification_required or "").lower()

    student_edu_fields = " ".join(filter(None, [
        getattr(student, "course", "") or "",
        getattr(student, "department", "") or "",
    ])).lower()

    if qualification and student_edu_fields:

        qual_words = set(
            w for w in re.split(r"[\s,/]+", qualification)
            if len(w) > 1
        )

        edu_words = set(
            w for w in re.split(r"[\s,/]+", student_edu_fields)
            if len(w) > 1
        )

        if qual_words & edu_words or qualification in student_edu_fields:

            score += WEIGHTS["education"]

            reasons.append(
                f"{(getattr(student,'course','') or qualification).strip()} \u2013 Match"
            )

    elif not qualification:

        score += WEIGHTS["education"] * 0.5


    # ---------------- EXPERIENCE ----------------

    job_exp = (job.experience_required or "").lower()

    student_exp_text = (getattr(student, "experience", "") or "").strip()

    is_fresher_job = (
        "fresher" in job_exp
        or job_exp.strip() in ("0", "0-1", "0-0")
        or job_exp.strip().startswith("0")
    )

    has_experience = bool(student_exp_text)

    if is_fresher_job and not has_experience:

        score += WEIGHTS["experience"]

        reasons.append("Fresher \u2013 Match")

    elif has_experience and job_exp:

        job_exp_numbers = _numbers_in(job_exp)

        # best-effort: if the student listed any experience and
        # the job isn't explicitly fresher-only, give partial credit
        if job_exp_numbers:

            score += WEIGHTS["experience"] * 0.6

            reasons.append("Experience \u2013 Match")

        else:

            score += WEIGHTS["experience"] * 0.4

    elif not job_exp:

        score += WEIGHTS["experience"] * 0.5


    # ---------------- LOCATION ----------------

    preferred_location = (
        getattr(student, "preferred_location", "") or ""
    ).strip().lower()

    job_location = (job.location or "").strip().lower()

    job_work_mode = (getattr(job, "work_mode", "") or "").lower()

    if "remote" in job_work_mode:

        score += WEIGHTS["location"]

        reasons.append("Remote \u2013 Match")

    elif preferred_location and job_location:

        if (
            preferred_location in job_location
            or job_location in preferred_location
        ):

            score += WEIGHTS["location"]

            reasons.append(f"{job.location} \u2013 Match")

    elif not preferred_location:

        score += WEIGHTS["location"] * 0.5


    # ---------------- SALARY ----------------

    expected_salary = getattr(student, "expected_salary", "") or ""

    job_salary = job.salary or ""

    expected_numbers = _numbers_in(expected_salary)

    job_numbers = _numbers_in(job_salary)

    if expected_numbers and job_numbers:

        if max(job_numbers) >= min(expected_numbers):

            score += WEIGHTS["salary"]

            reasons.append("Salary \u2013 Match")

        else:

            score += WEIGHTS["salary"] * 0.3

    else:

        score += WEIGHTS["salary"] * 0.5


    # ---------------- CAREER INTEREST ----------------

    career_interest = (
        getattr(student, "career_interest", "") or ""
    ).lower()

    job_text = f"{job.title} {job.description or ''}".lower()

    if career_interest:

        interest_words = [
            w for w in _clean_list(career_interest)
            if len(w) > 2
        ]

        if any(word.lower() in job_text for word in interest_words):

            score += WEIGHTS["career_interest"]

            reasons.append("Career Interest \u2013 Match")

    else:

        score += WEIGHTS["career_interest"] * 0.5


    return min(100, round(score)), reasons


def rank_jobs_for_student(student, jobs):
    """
    Takes an iterable of Job objects and returns a list of
    (job, score, reasons) tuples sorted by score descending.
    """

    scored = []

    for job in jobs:

        score, reasons = compute_job_match(student, job)

        scored.append((job, score, reasons))

    scored.sort(key=lambda item: item[1], reverse=True)

    return scored
