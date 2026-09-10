"""
Eligibility Engine (Requirement 10).

Given a StudentProfile and a Job, works out whether the student is
Eligible or Not Eligible to apply, checking every condition the job
has configured:

- Minimum CGPA
- Minimum percentage (10th/12th)
- Department
- Graduation year
- Backlog restrictions
- Required skills
- Experience
- Age restrictions
- Location requirements

Every field on the Job model used here is optional - a blank/null
value means "no restriction" for that condition, so a job with
nothing configured is eligible to everyone.

Returns a dict with an overall "eligible" boolean plus a per-condition
breakdown, so the UI can show exactly which conditions passed/failed
and why - not just a single Yes/No.
"""

import re


def _clean_list(text):

    if not text:

        return []

    return [
        part.strip()
        for part in re.split(r"[,\n/]", text)
        if part.strip()
    ]


def check_eligibility(student, job):

    conditions = []

    eligible = True


    def add(label, passed, detail):

        nonlocal eligible

        if passed is None:

            # condition not applicable / no data to check - informational only
            conditions.append({
                "label": label,
                "status": "info",
                "detail": detail,
            })

            return

        if not passed:

            eligible = False

        conditions.append({
            "label": label,
            "status": "pass" if passed else "fail",
            "detail": detail,
        })


    # ---------------- CGPA ----------------

    if job.min_cgpa:

        if student.ug_cgpa:

            passed = student.ug_cgpa >= job.min_cgpa

            add(
                "Minimum CGPA",
                passed,
                f"Requires {job.min_cgpa}+ CGPA - you have {student.ug_cgpa}"
                if not passed else
                f"CGPA requirement met ({student.ug_cgpa} \u2265 {job.min_cgpa})"
            )

        else:

            add(
                "Minimum CGPA",
                False,
                f"Requires {job.min_cgpa}+ CGPA - add your CGPA to your profile"
            )


    # ---------------- PERCENTAGE ----------------

    if job.min_percentage:

        scores = [
            s for s in [student.tenth_percentage, student.twelfth_percentage]
            if s is not None
        ]

        if scores:

            lowest = min(scores)

            passed = lowest >= job.min_percentage

            add(
                "Minimum Percentage",
                passed,
                f"Requires {job.min_percentage}%+ (10th/12th) - your lowest is {lowest}%"
                if not passed else
                f"Percentage requirement met (lowest: {lowest}%)"
            )

        else:

            add(
                "Minimum Percentage",
                False,
                f"Requires {job.min_percentage}%+ - add your 10th/12th marks to your profile"
            )


    # ---------------- DEPARTMENT ----------------

    if job.eligible_departments:

        allowed = [d.lower() for d in _clean_list(job.eligible_departments)]

        student_dept = (student.department or "").lower()

        passed = student_dept in allowed

        add(
            "Department",
            passed,
            f"Open to: {job.eligible_departments}"
            if not passed else
            f"Your department ({student.department}) is eligible"
        )


    # ---------------- GRADUATION YEAR ----------------

    if job.eligible_graduation_years:

        allowed_years = _clean_list(job.eligible_graduation_years)

        passed = str(student.graduation_year) in allowed_years

        add(
            "Graduation Year",
            passed,
            f"Open to graduation years: {job.eligible_graduation_years}"
            if not passed else
            f"Your graduation year ({student.graduation_year}) is eligible"
        )


    # ---------------- BACKLOGS ----------------

    if job.max_backlogs is not None:

        backlog_count = student.backlog_count or 0

        passed = backlog_count <= job.max_backlogs

        add(
            "Backlogs",
            passed,
            f"Maximum {job.max_backlogs} active backlog(s) allowed - you have {backlog_count}"
            if not passed else
            f"Backlog requirement met ({backlog_count} \u2264 {job.max_backlogs})"
        )


    # ---------------- AGE ----------------

    if job.min_age or job.max_age:

        if student.age:

            ok = True

            detail_parts = []

            if job.min_age and student.age < job.min_age:

                ok = False

            if job.max_age and student.age > job.max_age:

                ok = False

            range_text = (
                f"{job.min_age or 0}"
                f"{'-' + str(job.max_age) if job.max_age else '+'}"
            )

            add(
                "Age",
                ok,
                f"Requires age {range_text} - you are {student.age}"
                if not ok else
                f"Age requirement met ({student.age})"
            )

        else:

            add(
                "Age",
                False,
                "Age restriction applies - add your age to your profile"
            )


    # ---------------- SKILLS (soft check - informational) ----------------

    job_skills = set(s.lower() for s in _clean_list(job.skills_required))

    if job_skills:

        student_skill_names = set()

        try:

            student_skill_names.update(
                s.lower()
                for s in student.skills_list.values_list("name", flat=True)
            )

        except Exception:

            pass

        student_skill_names.update(
            s.lower() for s in _clean_list(student.skills)
        )

        matched = job_skills & student_skill_names

        missing = job_skills - student_skill_names

        if missing:

            conditions.append({
                "label": "Skills",
                "status": "info",
                "detail":
                    f"You're missing: {', '.join(sorted(missing))}. "
                    "This won't block your application, but improving these "
                    "will strengthen it.",
            })

        else:

            conditions.append({
                "label": "Skills",
                "status": "pass",
                "detail": "You have all the required skills",
            })


    # ---------------- EXPERIENCE (soft check - informational) ----------------

    if job.experience_required:

        conditions.append({
            "label": "Experience",
            "status": "info",
            "detail": f"Job expects: {job.experience_required}",
        })


    # ---------------- LOCATION (soft check - informational) ----------------

    if job.location and student.preferred_location:

        matches = (
            student.preferred_location.strip().lower()
            in job.location.lower()
            or job.location.lower()
            in student.preferred_location.strip().lower()
        )

        conditions.append({
            "label": "Location",
            "status": "pass" if matches else "info",
            "detail":
                f"Job location ({job.location}) matches your preference"
                if matches else
                f"Job is in {job.location}; your preference is {student.preferred_location}",
        })


    if not conditions:

        conditions.append({
            "label": "General",
            "status": "pass",
            "detail": "This job has no specific eligibility restrictions",
        })


    return {
        "eligible": eligible,
        "conditions": conditions,
        "summary": (
            "You are eligible to apply for this job."
            if eligible else
            "You do not meet all the eligibility requirements for this job."
        ),
    }
