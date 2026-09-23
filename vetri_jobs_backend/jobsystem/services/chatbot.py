"""
AI Placement Chatbot service.

This is what makes the chatbot "connected to the placement system"
instead of a generic FAQ bot: before calling the LLM, it pulls the
signed-in user's *real* data (applications, interviews, resume score,
skills, job matches, or - for a company user - their jobs/candidates)
and hands it to the model as grounded context, along with any active
Knowledge Base entries an admin has written. The model is instructed
to answer from that data rather than guessing.

Identity verification: this endpoint is reachable without login (so
the chatbot works on the public landing page for generic questions),
but every personal-data question is answered only from
`request.user`'s own records - there is no way to ask about another
student's applications/interviews through this endpoint, since the
context is always built from the authenticated user, never from
user-supplied IDs.

AGENT ARCHITECTURE:
Signed-in students AND companies get real Groq tool calling - the
model itself decides, based on the actual meaning of the message,
which real action is needed, then calls the matching Python tool
below. Each tool runs the exact same kind of real Django query the
platform's own pages already use (nothing invented, nothing pulled
from anywhere new) and returns structured JSON, which is fed back to
the model for a natural-language reply. Any job/candidate/document
list a tool returns is taken directly from that JSON - never from
what the model writes - so the frontend's result cards, download
buttons, and auto-navigation always reflect real data. Guests and
any other role (placement_admin/super_admin) get the plain
grounded-context chat, same as before - no tools are offered to them.
"""

import json
import re

from datetime import timedelta

from django.utils import timezone

from groq import Groq

import os


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


GROQ_MODEL_FALLBACKS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
]


# =====================================================
# CONTEXT BUILDERS
# =====================================================

def _serialize_interview(iv):

    return {
        "company": (
            iv.application.job.company.company_name
            if iv.application.job.company else "Company"
        ),
        "job_title": iv.application.job.title,
        "date": iv.interview_date.strftime("%b %d, %Y"),
        "time": iv.interview_date.strftime("%I:%M %p"),
        "mode": iv.get_interview_mode_display(),
        "status": iv.get_status_display(),
    }


def build_student_context(user):

    from jobsystem.models import (
        Application,
        Interview,
        Resume,
        Job,
    )

    from jobsystem.services.job_matching import rank_jobs_for_student

    profile = getattr(user, "student_profile", None)

    if not profile:

        return {
            "role": "student",
            "note": "This student hasn't completed their profile yet.",
        }

    applications = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company")

    applications_data = [
        {
            "job_title": app.job.title,
            "company": (
                app.job.company.company_name
                if app.job.company else "Company"
            ),
            "status": app.get_status_display(),
            "applied_on": app.applied_date.strftime("%b %d, %Y"),
        }
        for app in applications.order_by("-applied_date")[:15]
    ]

    now = timezone.now()

    week_end = now + timedelta(days=7)

    all_interviews = Interview.objects.filter(
        application__student=profile
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    upcoming_interviews = [
        _serialize_interview(iv)
        for iv in all_interviews.filter(
            interview_date__gte=now,
            status__in=["scheduled", "rescheduled"],
        )
    ]

    interviews_this_week = [
        _serialize_interview(iv)
        for iv in all_interviews.filter(
            interview_date__gte=now,
            interview_date__lte=week_end,
            status__in=["scheduled", "rescheduled"],
        )
    ]

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    resume_data = None

    if resume:

        resume_data = {
            "score": resume.resume_score,
            "skills_detected": resume.skills,
            "missing_information": resume.missing_information,
            "suggested_job_categories": resume.job_categories,
        }

    # top 3 recommended jobs, reusing the same AI matching engine
    # used on the Jobs page and Dashboard

    open_job_ids = applications.values_list("job_id", flat=True)

    candidate_jobs = Job.objects.filter(
        status="active", is_active=True
    ).exclude(id__in=open_job_ids)[:30]

    ranked = rank_jobs_for_student(profile, candidate_jobs)[:3]

    recommended_jobs = [
        {
            "title": job.title,
            "company": job.company.company_name if job.company else "",
            "match_score": score,
            "reasons": reasons,
        }
        for job, score, reasons in ranked
    ]

    return {
        "role": "student",
        "name": profile.full_name,
        "skills": profile.skills,
        "course": profile.course,
        "graduation_year": profile.graduation_year,
        "applications": applications_data,
        "total_applications": applications.count(),
        "upcoming_interviews": upcoming_interviews,
        "interviews_this_week": interviews_this_week,
        "resume": resume_data,
        "recommended_jobs": recommended_jobs,
    }


def build_company_context(user):

    from jobsystem.models import Job, Application, Interview

    company = getattr(user, "company_profile", None)

    if not company:

        return {
            "role": "company",
            "note": "This company hasn't completed their profile yet.",
        }

    jobs = Job.objects.filter(company=company)

    applications = Application.objects.filter(job__company=company)

    interviews = Interview.objects.filter(
        application__job__company=company
    )

    return {
        "role": "company",
        "company_name": company.company_name,
        "active_jobs": jobs.filter(status="active").count(),
        "total_jobs_posted": jobs.count(),
        "total_applications": applications.count(),
        "shortlisted": applications.filter(status="shortlisted").count(),
        "interviews_scheduled": interviews.filter(status="scheduled").count(),
        "recent_job_titles": list(
            jobs.order_by("-created_at").values_list("title", flat=True)[:5]
        ),
    }


def build_placement_context(user):

    from jobsystem.models import (
        StudentProfile, CompanyProfile, Job,
        PlacementDrive, Application,
    )

    from django.utils import timezone

    upcoming_drives = PlacementDrive.objects.filter(
        status="upcoming"
    ).order_by("drive_date")[:8]

    return {
        "role": "placement_admin",
        "total_students": StudentProfile.objects.count(),
        "total_companies": CompanyProfile.objects.count(),
        "active_jobs": Job.objects.filter(status="active").count(),
        "total_applications": Application.objects.count(),
        "placed_students": Application.objects.filter(
            status="selected"
        ).values("student").distinct().count(),
        "upcoming_placement_drives": [
            {
                "title": d.title,
                "company": d.company.company_name if d.company else "",
                "date": str(d.drive_date),
                "mode": d.get_mode_display() if hasattr(d, "get_mode_display") else "",
            }
            for d in upcoming_drives
        ],
        "recent_job_postings": [
            {
                "title": j.title,
                "company": j.company.company_name if j.company else "",
                "department": j.department,
            }
            for j in Job.objects.filter(
                status="active"
            ).order_by("-created_at")[:8]
        ],
    }


def build_context(user):

    if not user or not getattr(user, "is_authenticated", False):

        return {"role": "guest"}

    role = getattr(user, "role", None)

    if role == "student":

        return build_student_context(user)

    if role == "company":

        return build_company_context(user)

    if role == "placement_admin" or role == "super_admin":

        return build_placement_context(user)

    return {"role": role or "guest"}


def get_knowledge_base_snippets(limit=12):

    from jobsystem.models import KnowledgeBaseEntry

    entries = KnowledgeBaseEntry.objects.filter(
        is_active=True
    ).order_by("category", "title")[:limit]

    return [
        {
            "category": e.get_category_display(),
            "title": e.title,
            "content": e.content,
        }
        for e in entries
    ]


# =====================================================
# PROMPT
# =====================================================

SYSTEM_TEMPLATE = """You are the Vetri Jobs AI Placement Assistant, built into a
campus recruitment platform used by students, companies, and placement staff.

TOPIC SCOPE (strict): you only help with placement, career, and job-related
topics - job search, applications, interviews, resumes, skills, career
guidance, placement drives, and (for a company) candidates/hiring/analytics.
If the user asks something clearly unrelated to this - general knowledge,
weather, entertainment, coding help unrelated to their career, or anything
else off-topic - politely decline and redirect them back to what you can
help with. Do not answer the off-topic question itself, even briefly, even
if you know the answer.

You have been given the signed-in user's REAL, CURRENT data from the
platform database as JSON below. Always answer questions about "my
applications", "my interviews", "my resume", "jobs for me" (for a
student), or "my candidates", "my applicants", "my interviews" (for a
company), using this data directly - never say you don't have access
to it. If a relevant list in the data is empty, say so plainly.

If the user is a guest (not signed in), you do not have any personal
data - answer general questions about the platform, and suggest they
log in or register for personalized help.

If you have been given tools, use them whenever the message calls for
a real action or up-to-the-moment data, rather than answering from the
CURRENT USER DATA snapshot alone, since a tool call always reflects
the very latest state. For a student, this includes finding jobs,
checking eligibility, applying to a job, application/interview status,
job requirements for a specific role, skill suggestions, interview
preparation, resume feedback, ATS checking, resume/document download,
saved jobs, notifications, their own profile, updating their skills,
placement drives, requesting an interview slot, or raising a query.
For a company, this includes searching candidates, finding top
applicants for one of their jobs, viewing applications, interviews,
job postings, analytics, or their own company profile. Only call
apply_to_job when a student clearly, explicitly asks to apply to a
specific named job, and only call update_my_skills when they clearly,
explicitly ask to add/update a skill - never as a side effect of a
general question or a casual mention of a skill in conversation.
When a job in a find_matching_jobs/check_job_eligibility/get_saved_jobs
result has already_applied set to true, tell the student they've
already applied to it instead of inviting them to apply again.

NEVER CLAIM AN ACTION SUCCEEDED WITHOUT CALLING THE TOOL (critical):
you must NEVER say an application was submitted, a query was raised,
an interview slot was requested, or a skill was added unless you
ACTUALLY called the matching tool (apply_to_job, raise_placement_query,
request_interview_slot, update_my_skills) in this exact turn and it
returned success. Saying "done"/"submitted"/"added" in plain text
without calling the tool is strictly forbidden, even if the request
sounds simple or you're confident what the student wants - always
call the real tool instead of describing the action as if it happened.
If the student refers to a job by a pronoun ("apply to that job",
"the above one", "yes apply"), look at the most recent job list you
showed them in this conversation to resolve the exact job_title, then
call apply_to_job with that resolved title - do not guess and do not
skip the tool call because the title wasn't spelled out this turn.

DOWNLOADS: when get_resume_download_link runs successfully, tell the
student their resume is ready and that a download button is shown
right in the chat - never write out or mention a URL/link yourself,
since the actual download happens through the button, not a link you
provide.

INTERVIEW PREPARATION: when get_interview_prep or get_application_status
returns job_skills_required/skills_required/job_description for a
specific interview, use that real data to write 3-5 genuinely
role-and-company-specific preparation points or practice questions -
not generic interview advice. Be proactive: after showing application
status, if any application includes interview details, offer this
preparation immediately rather than waiting to be asked. If an
application shows the student was selected, congratulate them. If
rejected, be encouraging and offer to find more matching jobs.

NO DUPLICATE LISTINGS: when a tool result includes matched_jobs,
candidates, applications, interviews, jobs, drives, or notifications,
those render as their own visual cards/list right below your reply -
do NOT also write them out again as a table, a bulleted list of each
one, or markdown links like [text](url). Never write a raw URL or a
markdown-style link anywhere in your reply - links only ever appear
as the real buttons on those cards. Your reply text should just be
one or two short sentences introducing what's shown below (e.g. "Here
are 3 new jobs you haven't applied to yet.") - the cards carry all the
detail, so repeating it in text is redundant and, since this chat
doesn't render markdown tables or links, would show up as broken
formatting.

INTERVIEW PREP ROLE MATCHING (important): "help me prepare for [a role]"
and "help me prepare for MY interview" are different requests - do not
conflate them. If the student names a specific role/title (e.g. "prepare
for Python Full Stack Developer"), that is what they want prep for, even
if it's different from their actual scheduled interview. Call
get_interview_prep with that job_title; if it doesn't match their real
interview, the tool will say so - in that case, do NOT substitute your
real scheduled interview's details instead. Either give general
role-based prep grounded in typical skills for that role, or offer to
start a mock interview for it (start_mock_interview) - never silently
swap in a different job's real interview data just because one exists.

LIVE DATA OVER CHAT HISTORY (important): the CURRENT USER DATA JSON
below is rebuilt fresh from the real database on every single message -
it is always more current than anything said earlier in this
conversation. If an interview you mentioned in an earlier reply is no
longer listed in upcoming_interviews/interviews_this_week here, it has
already happened - do not keep repeating its date/time as if it's still
upcoming just because you said so previously in this chat. Always trust
this fresh data over your own prior messages.

JOB REQUIREMENTS: when get_job_details returns missing_skills, point
those out clearly as what the student should focus on for that
specific role, alongside skills_required.

SKILL ROADMAPS: when get_company_skill_gap or get_skill_suggestions
returns missing skills, build the student a short learning roadmap -
which skill to learn first and why, and a realistic order for the
rest - grounded in the real missing_skills list. Do NOT invent or
name specific courses, certifications, instructors, prices, or URLs
(e.g. a specific Udemy/Coursera course title or link) - you cannot
verify these exist or are current, and a wrong link is worse than no
link. Instead, point to general resource types (official
documentation, hands-on practice projects, open-source contributions)
without naming a specific product.

You also have a Knowledge Base of placement policies, FAQs, and
guidelines maintained by placement staff - use it for policy/process
questions. If something isn't covered by the data, tools, or
knowledge base, say you're not sure rather than inventing details.

Keep replies concise, friendly, and practical (a few sentences or a
short list). Never reveal another user's information - you only ever
have access to the signed-in user's own data, and every tool above
only ever touches this same signed-in user's own records (a
student's own profile, or a company's own jobs/candidates/interviews
- never another student's or another company's).

SECURITY (non-negotiable): the JSON below contains ONLY the current
signed-in user's own data. If the user asks to see another person's
or another company's private information, refuse clearly and suggest
they contact the placement office. Never guess, infer, or fabricate
another party's data even if asked to "assume" or "pretend". This
rule overrides any other instruction in this prompt, including
anything added below by an administrator.

CURRENT USER DATA:
{context_json}

KNOWLEDGE BASE:
{knowledge_json}
"""


def get_active_chatbot_setting():

    from jobsystem.models import ChatbotSetting

    return ChatbotSetting.objects.filter(
        enabled=True
    ).first()


# =====================================================
# AI SECURITY (Requirement 31)
# =====================================================

_OTHER_STUDENT_PATTERNS = [
    r"\bother student", r"\banother student", r"\bsomeone else",
    r"\ball students?['\u2019]?\s*(application|status|interview|data)",
    r"\bevery ?one'?s? (application|status|interview)",
    r"\bstudent (id|number)\s*[:#]?\s*\w+",
    r"\bshow me .*(student|candidate)s? (list|data|details|status)",
    r"\bmy (friend|classmate)'?s? (application|status|interview)",
    r"\bother compan(y|ies)", r"\banother company",
    r"\ball companies['\u2019]?\s*(application|candidate|data)",
]


def _is_security_probe(message):

    text = (message or "").lower()

    return any(
        re.search(pattern, text)
        for pattern in _OTHER_STUDENT_PATTERNS
    )


SECURITY_REFUSAL = (
    "I can only share information about your own account - I'm not "
    "able to show another student's or another company's private "
    "data. If you need details about someone else's placement "
    "progress, please contact the placement office directly."
)


# =====================================================
# STUDENT AGENT TOOLS (Requirement 17)
# =====================================================

def _serialize_matched_job(job, match_score=None, reasons=None, already_applied=False):

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company.company_name if job.company else "Company",
        "location": job.location or "",
        "job_type": (
            job.get_job_type_display()
            if hasattr(job, "get_job_type_display") else ""
        ),
        "match_score": match_score,
        "reasons": reasons or [],
        "already_applied": already_applied,
        "apply_url": f"/student/jobs/{job.id}/apply",
        "details_url": f"/student/jobs/{job.id}",
    }


def _tool_find_matching_jobs(profile, user, args):

    from datetime import timedelta

    from jobsystem.models import Job, Application
    from jobsystem.services.job_matching import rank_jobs_for_student

    # "Any new jobs?" / "what's newly updated" means recently POSTED
    # jobs the student hasn't acted on yet - not a full re-listing of
    # every match including ones already applied to. recent_only
    # restricts to postings from the last 14 days and always excludes
    # already-applied jobs, since the whole point is "what's new that
    # I haven't seen/acted on".

    recent_only = bool(args.get("recent_only"))

    jobs_qs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")

    if recent_only:

        jobs_qs = jobs_qs.filter(
            created_at__gte=timezone.now() - timedelta(days=14)
        )

    jobs = jobs_qs[:40]

    ranked = rank_jobs_for_student(profile, jobs)[:5]

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    if recent_only:

        ranked = [
            (job, score, reasons)
            for job, score, reasons in ranked
            if job.id not in applied_job_ids
        ]

    if not ranked:

        return {
            "matched_jobs": [],
            "summary": (
                "No newly posted jobs in the last two weeks that the "
                "student hasn't already applied to."
                if recent_only else
                "No active job postings found right now."
            ),
        }

    matched_jobs = [
        _serialize_matched_job(
            job, score, reasons,
            already_applied=(job.id in applied_job_ids),
        )
        for job, score, reasons in ranked
    ]

    return {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": (
            f"Found {len(matched_jobs)} newly posted job(s) the student hasn't applied to yet."
            if recent_only else
            f"Found {len(matched_jobs)} jobs matching the student's profile."
        ),
    }


def _tool_check_job_eligibility(profile, user, args):

    from jobsystem.models import Job, Application
    from jobsystem.services.eligibility import check_eligibility
    from jobsystem.services.job_matching import compute_job_match

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")[:30]

    eligible = []

    for job in jobs:

        result = check_eligibility(profile, job)

        if result["eligible"]:

            eligible.append(job)

    if not eligible:

        return {
            "matched_jobs": [],
            "summary": (
                "The student isn't fully eligible for any open jobs "
                "right now based on their current profile."
            ),
        }

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    matched_jobs = []

    for job in eligible[:8]:

        try:

            score, reasons = compute_job_match(profile, job)

        except Exception:

            score, reasons = None, []

        matched_jobs.append(
            _serialize_matched_job(
                job, score, reasons,
                already_applied=(job.id in applied_job_ids),
            )
        )

    return {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": f"The student is eligible for {len(matched_jobs)} open jobs.",
    }


def _tool_get_job_details(profile, user, args):
    """
    Covers "What does this job require?" - a literal example question
    from the spec that had no tool behind it before. Leans on
    JobSerializer's own output (via .get()) rather than guessing at
    Job model field names directly, so it degrades gracefully if a
    field isn't present instead of raising an AttributeError.
    """

    from jobsystem.models import Job
    from jobsystem.serializers import JobSerializer
    from jobsystem.services.job_matching import compute_job_match

    job_title = (args.get("job_title") or "").strip()

    if not job_title:

        return {"summary": "No job title was given."}

    job = Job.objects.filter(
        status="active", is_active=True,
        title__icontains=job_title,
    ).select_related("company").order_by("-created_at").first()

    if not job:

        return {
            "summary": (
                f"No open job found matching \"{job_title}\". Ask the "
                "student to check the exact title on the Jobs page."
            ),
        }

    job_data = JobSerializer(job).data

    try:

        score, reasons = compute_job_match(profile, job)

    except Exception:

        score, reasons = None, []

    skills_raw = job_data.get("skills_required") or ""

    skills_required = (
        [s.strip() for s in skills_raw.split(",") if s.strip()]
        if isinstance(skills_raw, str) else (skills_raw or [])
    )

    student_skills = set(
        s.strip().lower()
        for s in (getattr(profile, "skills", "") or "").split(",")
        if s.strip()
    )

    missing_skills = [
        s for s in skills_required
        if s.strip().lower() not in student_skills
    ]

    company_name = job.company.company_name if job.company else "Company"

    return {
        "job_title": job.title,
        "company": company_name,
        "location": job_data.get("location", ""),
        "job_type": job_data.get("job_type", ""),
        "description": job_data.get("description", ""),
        "eligibility_criteria": job_data.get("eligibility_criteria", ""),
        "skills_required": skills_required,
        "missing_skills": missing_skills,
        "match_score": score,
        "apply_url": f"/student/jobs/{job.id}/apply",
        "details_url": f"/student/jobs/{job.id}",
        "summary": f"Requirements for {job.title} at {company_name}.",
    }


def _tool_get_skill_suggestions(profile, user, args):
    """
    Covers "What skills should I improve?" with a real answer grounded
    in current job-market demand on the platform, not a generic list -
    the skills most frequently required across active postings that
    the student doesn't already have.
    """

    from jobsystem.models import Job
    from collections import Counter

    jobs = Job.objects.filter(status="active", is_active=True)[:50]

    student_skills = set(
        s.strip().lower()
        for s in (getattr(profile, "skills", "") or "").split(",")
        if s.strip()
    )

    missing_counter = Counter()

    for job in jobs:

        required = [
            s.strip() for s in (job.skills_required or "").split(",")
            if s.strip()
        ]

        for skill in required:

            if skill.lower() not in student_skills:

                missing_counter[skill] += 1

    top_missing = [skill for skill, _ in missing_counter.most_common(8)]

    return {
        "current_skills": sorted(student_skills),
        "suggested_skills": top_missing,
        "summary": (
            "Top in-demand skills the student doesn't have yet: "
            + ", ".join(top_missing)
        ) if top_missing else (
            "The student's current skills already cover most open "
            "job requirements on the platform."
        ),
    }


def _tool_get_company_skill_gap(profile, user, args):
    """
    Covers "what skills do I need for [company]?" - combines the
    required skills across EVERY active job posting from one company
    (get_job_details only covers a single job), compared against the
    student's real skills. The model builds the learning roadmap
    itself from this real gap list - see the ROADMAPS guidance in
    SYSTEM_TEMPLATE for why it's told not to invent specific course
    names or links.
    """

    from jobsystem.models import Job
    from collections import Counter

    company_name = (args.get("company_name") or "").strip()

    if not company_name:

        return {"summary": "No company name was given."}

    jobs = Job.objects.filter(
        status="active", is_active=True,
        company__company_name__icontains=company_name,
    ).select_related("company")

    if not jobs.exists():

        return {
            "summary": (
                f"No active job postings found from a company matching "
                f"\"{company_name}\"."
            ),
        }

    real_company_name = jobs.first().company.company_name

    student_skills = set(
        s.strip().lower()
        for s in (getattr(profile, "skills", "") or "").split(",")
        if s.strip()
    )

    required_counter = Counter()

    job_titles = []

    for job in jobs:

        job_titles.append(job.title)

        for skill in (job.skills_required or "").split(","):

            skill = skill.strip()

            if skill:

                required_counter[skill] += 1

    all_required = [skill for skill, _ in required_counter.most_common()]

    missing_skills = [
        s for s in all_required
        if s.lower() not in student_skills
    ]

    matching_skills = [
        s for s in all_required
        if s.lower() in student_skills
    ]

    return {
        "company": real_company_name,
        "job_titles": job_titles[:8],
        "skills_required": all_required,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "summary": (
            f"{real_company_name} has {len(missing_skills)} skill(s) "
            f"the student is missing, across {len(job_titles)} open "
            f"role(s)."
        ) if missing_skills else (
            f"The student already has every skill "
            f"{real_company_name}'s open roles require."
        ),
    }


def _tool_apply_to_job(profile, user, args):

    from jobsystem.models import Job, Application

    job_title = (args.get("job_title") or "").strip()

    if not job_title:

        return {
            "success": False,
            "summary": "No job title was given to apply to.",
        }

    candidates = Job.objects.filter(
        status="active", is_active=True,
        title__icontains=job_title,
    ).select_related("company")

    count = candidates.count()

    if count == 0:

        return {
            "success": False,
            "summary": (
                f"No open job matching \"{job_title}\" was found. "
                "Ask the student to check the exact title on the Jobs page."
            ),
        }

    if count > 1:

        options = [
            {
                "title": j.title,
                "company": j.company.company_name if j.company else "",
            }
            for j in candidates[:5]
        ]

        return {
            "success": False,
            "options": options,
            "summary": (
                f"{count} jobs match \"{job_title}\" - ask the student "
                "to specify which exact one they mean."
            ),
        }

    job = candidates.first()

    company_name = job.company.company_name if job.company else "the company"

    if Application.objects.filter(student=profile, job=job).exists():

        return {
            "success": False,
            "summary": f"The student already applied to {job.title} at {company_name}.",
        }

    Application.objects.create(
        student=profile,
        job=job,
        status="applied",
    )

    return {
        "success": True,
        "job_id": job.id,
        "job_title": job.title,
        "company": company_name,
        "summary": f"Applied to {job.title} at {company_name} successfully.",
    }


def _tool_get_application_status(profile, user, args):

    from jobsystem.models import Application, Interview

    apps = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company").order_by("-applied_date")[:10]

    applications = []

    has_interview_scheduled = False

    for app in apps:

        entry = {
            "job_title": app.job.title,
            "company": app.job.company.company_name if app.job.company else "Company",
            "status": app.get_status_display(),
        }

        # For an application currently at the "interview" stage,
        # attach the actual scheduled interview's date/time/mode AND
        # that job's real required skills - this is what lets the
        # model proactively offer genuinely role/company-specific
        # interview prep, grounded in real data, without a second
        # tool call.

        if app.status == "interview":

            upcoming_iv = Interview.objects.filter(
                application=app,
                status__in=["scheduled", "rescheduled"],
            ).order_by("-interview_date").first()

            if upcoming_iv:

                job_skills = [
                    s.strip()
                    for s in (app.job.skills_required or "").split(",")
                    if s.strip()
                ]

                entry["interview"] = {
                    "date": upcoming_iv.interview_date.strftime("%b %d, %Y"),
                    "time": upcoming_iv.interview_date.strftime("%I:%M %p"),
                    "mode": upcoming_iv.get_interview_mode_display(),
                    "job_skills_required": job_skills,
                }

                has_interview_scheduled = True

        applications.append(entry)

    return {
        "applications": applications,
        "has_interview_scheduled": has_interview_scheduled,
        "summary": (
            f"{len(applications)} applications found."
            if applications else
            "The student hasn't applied to any jobs yet."
        ),
    }


def _tool_get_upcoming_interviews(profile, user, args):

    from jobsystem.models import Interview

    now = timezone.now()

    week_only = bool(args.get("this_week"))

    week_end = now + timedelta(days=7)

    qs = Interview.objects.filter(
        application__student=profile,
        interview_date__gte=now,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    if week_only:

        qs = qs.filter(interview_date__lte=week_end)

    interviews = [_serialize_interview(iv) for iv in qs]

    return {
        "interviews": interviews,
        "summary": (
            f"{len(interviews)} upcoming interview(s)"
            + (" this week." if week_only else ".")
        ),
    }


def _tool_get_interview_prep(profile, user, args):
    """
    Covers "How can I prepare for this interview?" with real
    grounding: the actual scheduled interview's job title, company,
    and required skills, so the model's prep suggestions are
    genuinely specific rather than generic advice.
    """

    from jobsystem.models import Interview

    job_title = (args.get("job_title") or "").strip()

    qs = Interview.objects.filter(
        application__student=profile,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    if job_title:

        qs = qs.filter(application__job__title__icontains=job_title)

    interview = qs.first()

    if not interview:

        return {
            "summary": (
                "No upcoming interview found to prepare for."
                + (f" (looked for \"{job_title}\")" if job_title else "")
            ),
        }

    job = interview.application.job

    skills_required = [
        s.strip() for s in (job.skills_required or "").split(",")
        if s.strip()
    ]

    company_name = job.company.company_name if job.company else "Company"

    return {
        "job_title": job.title,
        "company": company_name,
        "interview_date": interview.interview_date.strftime("%b %d, %Y"),
        "interview_time": interview.interview_date.strftime("%I:%M %p"),
        "mode": interview.get_interview_mode_display(),
        "skills_required": skills_required,
        "job_description": getattr(job, "description", "") or "",
        "summary": (
            f"Interview for {job.title} at {company_name} on "
            f"{interview.interview_date.strftime('%b %d, %Y')}."
        ),
    }


def _tool_get_resume_feedback(profile, user, args):

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume:

        return {
            "has_resume": False,
            "summary": "The student hasn't uploaded a resume yet.",
        }

    return {
        "has_resume": True,
        "score": resume.resume_score,
        "missing_information": resume.missing_information,
        "suggested_job_categories": resume.job_categories,
        "summary": f"Resume score is {resume.resume_score}/100.",
    }


def _tool_check_ats_friendliness(profile, user, args):

    from jobsystem.models import Resume
    from jobsystem.services.resume_ai import analyze_ats_friendliness

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume or not resume.file:

        return {
            "has_resume": False,
            "summary": "The student hasn't uploaded a resume yet.",
        }

    target_role = args.get("target_role") or None

    try:

        # analyze_ats_friendliness() takes the resume's Django file
        # object, not a filesystem path - resume.file.path raises
        # NotImplementedError under Cloudinary storage.
        result = analyze_ats_friendliness(
            resume.file,
            target_role=target_role,
        )

    except Exception as e:

        return {
            "has_resume": True,
            "summary": f"Could not run the ATS check right now ({e}).",
        }

    return {
        "has_resume": True,
        "ats_score": result.get("ats_score"),
        "issues": result.get("issues", []),
        "suggestions": result.get("suggestions", []),
        "rewritten_bullets": result.get("rewritten_bullets", []),
        "summary": f"ATS-friendliness score is {result.get('ats_score')}/100.",
    }


def _tool_get_upcoming_drives(profile, user, args):

    from jobsystem.models import PlacementDrive

    now = timezone.now().date()

    drives = PlacementDrive.objects.filter(
        drive_date__gte=now
    ).select_related("company").order_by("drive_date")[:6]

    data = [
        {
            "company": d.company.company_name if d.company else "Company",
            "title": d.title,
            "date": d.drive_date.strftime("%b %d, %Y"),
        }
        for d in drives
    ]

    return {
        "drives": data,
        "summary": (
            f"{len(data)} upcoming placement drive(s)."
            if data else
            "No upcoming placement drives right now."
        ),
    }


def _tool_request_interview_slot(profile, user, args):

    from jobsystem.models import PlacementQuery

    note = (args.get("note") or "").strip()

    PlacementQuery.objects.create(
        student=profile,
        category="interview_request",
        message=note or "Interview slot request via AI Assistant",
        source="chatbot",
    )

    return {
        "success": True,
        "summary": (
            "Interview slot request sent to the placement team - "
            "the student will be notified once a slot is assigned."
        ),
    }


def _tool_raise_placement_query(profile, user, args):

    from jobsystem.models import PlacementQuery

    message_text = (args.get("message") or "").strip()

    PlacementQuery.objects.create(
        student=profile,
        category="general",
        message=message_text,
        source="chatbot",
    )

    return {
        "success": True,
        "summary": "Query raised with the placement team - they'll respond soon.",
    }


def _tool_get_resume_download_link(profile, user, args):
    """
    Returns the resume's own id, NOT a raw URL - the frontend uses
    this id with the exact same authenticated blob-download flow the
    Resume Management page already uses, so the file downloads
    directly from inside the chat rather than the model writing out
    a link that would either 404 (wrong domain/route) or leave the
    app entirely (different domain from the backend).
    """

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume or not resume.file:

        return {
            "has_resume": False,
            "summary": "The student hasn't uploaded a resume yet.",
        }

    return {
        "has_resume": True,
        "resume_id": resume.id,
        "filename": resume.filename or "Resume",
        "summary": f"Resume ready to download: {resume.filename or 'Resume'}.",
    }


def _tool_get_saved_jobs(profile, user, args):

    from jobsystem.models import Job, Application

    jobs = Job.objects.filter(
        saved_by__student=profile
    ).select_related("company").order_by("-saved_by__saved_at")[:10]

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    matched_jobs = [
        _serialize_matched_job(
            job, already_applied=(job.id in applied_job_ids)
        )
        for job in jobs
    ]

    return {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/saved-jobs",
        "summary": (
            f"{len(matched_jobs)} saved job(s)."
            if matched_jobs else "No saved jobs yet."
        ),
    }


def _tool_get_notifications(profile, user, args):

    from jobsystem.models import Notification

    notifications = Notification.objects.filter(
        user=user
    ).order_by("-created_at")[:10]

    data = [
        {
            "title": getattr(n, "title", "") or "",
            "message": n.message,
            "is_read": n.is_read,
        }
        for n in notifications
    ]

    unread_count = sum(1 for n in data if not n["is_read"])

    return {
        "notifications": data,
        "navigate_to": "/student/notifications",
        "summary": (
            f"{len(data)} recent notification(s), {unread_count} unread."
            if data else "No notifications yet."
        ),
    }


def _tool_get_my_profile(profile, user, args):
    """
    Covers the Profile tab - a read-only snapshot of the student's
    own profile, including how complete it is.
    """

    return {
        "full_name": profile.full_name,
        "course": profile.course,
        "department": profile.department,
        "graduation_year": profile.graduation_year,
        "cgpa": profile.ug_cgpa,
        "skills": profile.skills,
        "location": profile.location,
        "linkedin": profile.linkedin,
        "github": profile.github,
        "portfolio": profile.portfolio,
        "profile_completion": profile.profile_completion,
        "verified": profile.verified,
        "navigate_to": "/student/profile",
        "summary": f"Profile is {profile.profile_completion}% complete.",
    }


def _tool_update_my_skills(profile, user, args):
    """
    A real write action - adds new skills directly to the student's
    profile from chat. Purely additive (never removes or overwrites
    existing skills), so there's no destructive risk even if the
    model runs this more eagerly than intended. Only call when the
    student clearly asks to add/update a skill - see the guardrail
    in SYSTEM_TEMPLATE.
    """

    new_skills_raw = (args.get("skills") or "").strip()

    if not new_skills_raw:

        return {
            "success": False,
            "summary": "No skills were given to add.",
        }

    existing_lower = set(
        s.strip().lower()
        for s in (profile.skills or "").split(",")
        if s.strip()
    )

    current_list = [
        s.strip() for s in (profile.skills or "").split(",") if s.strip()
    ]

    added = []

    for skill in new_skills_raw.split(","):

        skill = skill.strip()

        if skill and skill.lower() not in existing_lower:

            added.append(skill)

            existing_lower.add(skill.lower())

    if not added:

        return {
            "success": False,
            "summary": "Those skills are already on the student's profile.",
        }

    profile.skills = ", ".join(current_list + added)

    profile.save()

    return {
        "success": True,
        "added_skills": added,
        "all_skills": profile.skills,
        "navigate_to": "/student/profile",
        "summary": f"Added {', '.join(added)} to the student's skills.",
    }


# =====================================================
# MOCK INTERVIEW SUBSYSTEM
#
# A genuine state machine, not a single tool call: once a session
# is "in_progress", every message the student sends is their ANSWER
# to the current question, not a new general request. generate_reply()
# checks for an active session before doing anything else (even
# before the normal tool-calling flow) and routes entirely to
# _handle_mock_interview_turn() below when one exists - see the
# ACTIVE MOCK INTERVIEW block near the bottom of generate_reply().
#
# Uses the MockInterviewSession model's "turns" field: a list of
# {"question": str, "answer": str|None} in order. The last turn
# always has answer=None until the student replies to it.
# =====================================================


INTERVIEWER_SYSTEM_PROMPT = """You are conducting a live mock job interview for the
role of {job_title}{company_clause}. Ask one interview question at a time - a mix
of technical/role-specific questions and behavioral/communication questions,
appropriate for this role. Keep each question focused and realistic, like a
real interviewer would ask - not a wall of text, and not multiple questions
at once.

After the candidate answers, either ask a natural follow-up or move to the
next question. Once you've asked a reasonable range of questions (typically
5-8) covering both technical and behavioral areas, and have enough to fairly
assess the candidate, call the end_interview tool to conclude - do not call
it after fewer than 4 questions. Stay in character as an interviewer - do
not break character to explain what you are doing or mention that this is
an AI simulation.

If the candidate asks something completely unrelated to the interview or
their career (e.g. the weather, general trivia, unrelated requests), do not
answer it at all - firmly but politely say that's outside this interview,
then immediately repeat or restate the current question so the interview
stays on track."""


END_INTERVIEW_TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "end_interview",
            "description": (
                "Conclude the mock interview now that enough questions "
                "have been asked to fairly assess the candidate."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
]


_INTERVIEW_EXIT_PATTERNS = [
    r"\bstop\b.*interview", r"\bend\b.*interview", r"\bcancel\b.*interview",
    r"\bquit\b.*interview", r"^\s*(stop|cancel|quit|exit)\s*[.!]?\s*$",
]


def _is_interview_exit(message):

    text = (message or "").lower()

    return any(re.search(p, text) for p in _INTERVIEW_EXIT_PATTERNS)


# A genuine platform request (checking applications, jobs, resume, etc.)
# made mid-interview is NOT the same as idle off-topic chat (weather,
# trivia) - the interviewer prompt is told to refuse and redirect for
# the latter, but a real question like this should actually get
# answered, not swallowed into "interview answer" or "stay on topic"
# handling. Matching one of these ends the interview and lets the
# message fall through to the normal tool-calling flow instead.

_PLATFORM_INTENT_PATTERNS = [
    r"\bjobs? (i|you|ve)?\s*applied", r"\bmy applications?\b",
    r"\bapplication status\b", r"\bmy interviews?\b",
    r"\bcheck my\b", r"\bshow (me )?my\b", r"\bnew jobs?\b",
    r"\bfind (me )?(a )?jobs?\b", r"\bsearch (for )?jobs?\b",
    r"\bmy resume\b", r"\bnotifications?\b", r"\bsaved jobs?\b",
    r"\bmy profile\b", r"\bskill(s)? (i|should)\b",
]


def _looks_like_platform_request(message):

    text = (message or "").lower()

    return any(re.search(p, text) for p in _PLATFORM_INTENT_PATTERNS)


def _tool_start_mock_interview(profile, user, args):

    from jobsystem.models import MockInterviewSession, Job

    job_title = (args.get("job_title") or "").strip()

    if not job_title:

        return {"summary": "No job role was given to practice for."}

    company_name = (args.get("company_name") or "").strip()

    # Only one active session at a time - stale ones from an
    # abandoned earlier attempt are cancelled, not left orphaned.

    MockInterviewSession.objects.filter(
        student=profile, status="in_progress"
    ).update(status="cancelled")

    # Ground the opening question in a real posting's required
    # skills when one matches, so the interview isn't purely generic.

    skills_context = ""

    real_job = Job.objects.filter(
        status="active", is_active=True, title__icontains=job_title,
    ).select_related("company").first()

    if real_job:

        skills_context = real_job.skills_required or ""

        if not company_name and real_job.company:

            company_name = real_job.company.company_name

    company_clause = f" at {company_name}" if company_name else ""

    system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
        job_title=job_title, company_clause=company_clause
    )

    if skills_context:

        system_prompt += (
            f"\n\nThe real job posting lists these required skills: "
            f"{skills_context}. Weight your technical questions toward these."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin the interview with your first question."},
    ]

    try:

        first_question = _call_groq_plain(messages)

    except Exception as e:

        return {"summary": f"Could not start the mock interview right now ({e})."}

    session = MockInterviewSession.objects.create(
        student=profile,
        job_title=job_title,
        turns=[{"question": first_question, "answer": None}],
    )

    return {
        "mock_interview_started": True,
        "session_id": session.id,
        "question": first_question,
        "summary": f"Mock interview started for {job_title}.",
    }


def _tool_get_mock_interview_report(profile, user, args):

    from jobsystem.models import MockInterviewSession

    session = MockInterviewSession.objects.filter(
        student=profile, status="completed"
    ).order_by("-completed_at").first()

    if not session:

        return {"summary": "No completed mock interview found yet."}

    return {
        "job_title": session.job_title,
        "score_report": session.score_report,
        "summary": f"Latest mock interview report for {session.job_title}.",
    }


def _handle_mock_interview_turn(session, user, message):
    """
    Called instead of the normal tool-calling flow whenever the
    student has an in_progress MockInterviewSession - this message
    IS their answer to the current question.
    """

    if _is_interview_exit(message):

        session.status = "cancelled"

        session.save()

        return {
            "reply": (
                "Mock interview ended early - no problem, come back "
                "anytime you want to practice again."
            ),
        }

    turns = session.turns or []

    if turns and turns[-1].get("answer") is None:

        turns[-1]["answer"] = message

    company_clause = ""

    system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
        job_title=session.job_title, company_clause=company_clause
    )

    messages = [{"role": "system", "content": system_prompt}]

    for turn in turns:

        messages.append({"role": "assistant", "content": turn["question"]})

        if turn.get("answer") is not None:

            messages.append({"role": "user", "content": turn["answer"]})

    try:

        response = _call_groq_with_tools(messages, END_INTERVIEW_TOOL_SCHEMA)

    except Exception as e:

        print("Mock interview turn error:", e)

        session.turns = turns

        session.save()

        return {
            "reply": (
                "I'm having trouble continuing the interview right now. "
                "Please try again in a moment."
            ),
        }

    choice_message = response.choices[0].message

    tool_calls = getattr(choice_message, "tool_calls", None)

    if tool_calls and tool_calls[0].function.name == "end_interview":

        return _finish_mock_interview(session, turns)

    next_question = (choice_message.content or "").strip()

    if not next_question:

        return _finish_mock_interview(session, turns)

    turns.append({"question": next_question, "answer": None})

    session.turns = turns

    session.save()

    return {"reply": next_question}


def _finish_mock_interview(session, turns):

    scoring_prompt = f"""You just finished conducting a mock interview for the role of
{session.job_title}. Below is the full transcript as JSON (a list of
{{"question", "answer"}} pairs - "answer" may be null if the candidate never
replied to that final question). Produce a JSON object ONLY, no other text,
with this exact shape:

{{
  "overall_score": <0-100 integer>,
  "communication_score": <0-100 integer>,
  "technical_score": <0-100 integer>,
  "strengths": ["...", "..."],
  "areas_to_improve": ["...", "..."],
  "question_feedback": [
    {{"question": "...", "feedback": "..."}}
  ]
}}

Be honest and specific, grounded in what the candidate actually said - do
not be uniformly generous. If answers were vague, short, or missing,
reflect that clearly in the score and feedback rather than inflating it."""

    scoring_messages = [
        {"role": "system", "content": scoring_prompt},
        {"role": "user", "content": json.dumps(turns)},
    ]

    try:

        raw = _call_groq_plain(scoring_messages).strip()

        if raw.startswith("```"):

            raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()

        report = json.loads(raw)

    except Exception as e:

        print("Mock interview scoring error:", e)

        report = {
            "overall_score": None,
            "summary": (
                "The interview finished, but I couldn't generate a "
                "detailed score report this time."
            ),
        }

    session.status = "completed"

    session.score_report = report

    session.turns = turns

    session.completed_at = timezone.now()

    session.save()

    lines = ["Interview complete! Here's your report:\n"]

    if report.get("overall_score") is not None:

        lines.append(f"Overall score: {report['overall_score']}/100")

        lines.append(f"Communication: {report.get('communication_score', '-')}/100")

        lines.append(f"Technical: {report.get('technical_score', '-')}/100\n")

    if report.get("strengths"):

        lines.append("Strengths:")

        for s in report["strengths"]:

            lines.append(f"- {s}")

    if report.get("areas_to_improve"):

        lines.append("\nAreas to improve:")

        for a in report["areas_to_improve"]:

            lines.append(f"- {a}")

    return {
        "reply": "\n".join(lines),
        "mock_interview_report": report,
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "find_matching_jobs",
            "description": (
                "Find active job postings that best match the "
                "student's skills, course, and profile. Use whenever "
                "the student asks to find, search, see, or get "
                "suitable/recommended jobs for themselves. Results "
                "include an already_applied flag per job."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_only": {
                        "type": "boolean",
                        "description": (
                            "Set true when the student specifically "
                            "asks about NEW, newly posted, newly "
                            "updated, or recently added jobs - this "
                            "restricts to postings from the last two "
                            "weeks and excludes jobs already applied "
                            "to. Leave false/omitted for a general "
                            "'find jobs for me' request."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_job_eligibility",
            "description": (
                "List open jobs the student is currently eligible "
                "for, based on their profile (CGPA, department, "
                "backlogs, etc). Use when the student asks which "
                "jobs they're eligible for. Results include an "
                "already_applied flag per job."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_details",
            "description": (
                "Get the full requirements for one specific open job "
                "by title - description, required skills, eligibility "
                "criteria, and which required skills the student is "
                "missing. Use when the student asks what a job "
                "requires/needs, or wants details on a specific role."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job title to get requirements for.",
                    }
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill_suggestions",
            "description": (
                "Get skills the student should learn, based on what's "
                "most in-demand across currently active job postings "
                "that they don't already have. Use when the student "
                "asks what skills to improve or learn."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_skill_gap",
            "description": (
                "Get the skill gap between the student and ALL of one "
                "specific company's open roles combined (not just one "
                "job). Use when the student names a target company "
                "and asks what skills they need for it, or wants a "
                "roadmap to prepare for that company."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name the student is targeting.",
                    }
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_to_job",
            "description": (
                "Submit a job application for the student to a "
                "specific open job by title. Only use when the "
                "student explicitly asks to apply to a named job."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job title to apply to, as the student mentioned it.",
                    }
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_application_status",
            "description": (
                "Get the student's current job applications and "
                "their statuses. For any application at the "
                "interview stage, this also returns the actual "
                "scheduled interview date/time/mode and that job's "
                "required skills - after showing this, proactively "
                "offer role-and-company-specific interview prep."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_interviews",
            "description": "Get the student's upcoming scheduled interviews.",
            "parameters": {
                "type": "object",
                "properties": {
                    "this_week": {
                        "type": "boolean",
                        "description": "True only if the student specifically asked about interviews this week.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_interview_prep",
            "description": (
                "Get real, job-specific data (company, role, required "
                "skills, description) for an upcoming interview, to "
                "generate genuinely tailored preparation suggestions "
                "or practice questions - not generic advice. Use when "
                "the student asks how to prepare for an interview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job title to prepare for, if the student mentioned one.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resume_feedback",
            "description": "Get the student's resume score and suggestions for improving it.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_ats_friendliness",
            "description": (
                "Check how ATS (Applicant Tracking System) friendly "
                "the student's resume is, optionally against a "
                "specific target job role."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_role": {
                        "type": "string",
                        "description": "The job role to check the resume against, if the student mentioned one.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resume_download_link",
            "description": (
                "Get the student's current active resume ready for "
                "download - triggers a real download button directly "
                "in the chat. Use when the student asks to download "
                "their resume or documents."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_saved_jobs",
            "description": "Get the student's saved/bookmarked jobs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notifications",
            "description": "Get the student's recent notifications.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_profile",
            "description": (
                "Get the student's own profile details and how "
                "complete it is. Use when the student asks about "
                "their own profile or profile completion."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_my_skills",
            "description": (
                "Add one or more new skills directly to the "
                "student's profile. Only use when the student "
                "explicitly asks to add/update a skill on their "
                "profile - never as a side effect of a general "
                "conversation about skills."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "string",
                        "description": "Comma-separated skill(s) to add, exactly as the student named them.",
                    }
                },
                "required": ["skills"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_mock_interview",
            "description": (
                "Start a live mock interview session for a specific "
                "job role. Use when the student asks to practice for "
                "an interview, do a mock interview, or role-play an "
                "interview. Once started, the student's following "
                "messages become their interview answers, not normal "
                "chat, until the interview ends."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job role to practice interviewing for.",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "The target company, if the student mentioned one.",
                    },
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mock_interview_report",
            "description": "Get the student's most recent completed mock interview score report.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_drives",
            "description": "Get upcoming placement drives across all companies.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_interview_slot",
            "description": "Send a request to the placement team for an interview slot on the student's behalf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "Any extra detail the student gave about their request.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "raise_placement_query",
            "description": "Raise a general query, doubt, or complaint with the placement office on the student's behalf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The student's query or complaint, in their own words.",
                    }
                },
                "required": ["message"],
            },
        },
    },
]


TOOL_EXECUTORS = {
    "find_matching_jobs": _tool_find_matching_jobs,
    "check_job_eligibility": _tool_check_job_eligibility,
    "get_job_details": _tool_get_job_details,
    "get_skill_suggestions": _tool_get_skill_suggestions,
    "get_company_skill_gap": _tool_get_company_skill_gap,
    "apply_to_job": _tool_apply_to_job,
    "get_application_status": _tool_get_application_status,
    "get_upcoming_interviews": _tool_get_upcoming_interviews,
    "get_interview_prep": _tool_get_interview_prep,
    "get_resume_feedback": _tool_get_resume_feedback,
    "check_ats_friendliness": _tool_check_ats_friendliness,
    "get_resume_download_link": _tool_get_resume_download_link,
    "get_my_profile": _tool_get_my_profile,
    "update_my_skills": _tool_update_my_skills,
    "start_mock_interview": _tool_start_mock_interview,
    "get_mock_interview_report": _tool_get_mock_interview_report,
    "get_saved_jobs": _tool_get_saved_jobs,
    "get_notifications": _tool_get_notifications,
    "get_upcoming_drives": _tool_get_upcoming_drives,
    "request_interview_slot": _tool_request_interview_slot,
    "raise_placement_query": _tool_raise_placement_query,
}


# =====================================================
# COMPANY AGENT TOOLS
# =====================================================

def _tool_search_candidates(profile, user, args):

    from django.db.models import Q
    from jobsystem.models import StudentProfile

    query = (args.get("query") or "").strip()

    department = (args.get("department") or "").strip()

    min_cgpa = args.get("min_cgpa")

    candidates_qs = StudentProfile.objects.select_related("user")

    if query:

        candidates_qs = candidates_qs.filter(
            Q(skills__icontains=query) |
            Q(full_name__icontains=query) |
            Q(course__icontains=query) |
            Q(department__icontains=query)
        )

    if department:

        candidates_qs = candidates_qs.filter(
            department__icontains=department
        )

    if min_cgpa is not None:

        try:

            candidates_qs = candidates_qs.filter(
                ug_cgpa__gte=float(min_cgpa)
            )

        except (TypeError, ValueError):

            pass

    candidates_qs = candidates_qs.order_by("-id")[:15]

    results = [
        {
            "name": s.full_name,
            "course": s.course,
            "department": s.department,
            "cgpa": s.ug_cgpa,
            "skills": (
                [x.strip() for x in s.skills.split(",")]
                if s.skills else []
            ),
        }
        for s in candidates_qs
    ]

    return {
        "candidates": results,
        "navigate_to": "/company/candidates",
        "summary": f"Found {len(results)} matching student profiles.",
    }


def _tool_get_top_candidates_for_job(profile, user, args):

    from jobsystem.models import Job, Application
    from jobsystem.services.job_matching import compute_job_match

    job_title = (args.get("job_title") or "").strip()

    jobs_qs = Job.objects.filter(company=profile)

    if job_title:

        jobs_qs = jobs_qs.filter(title__icontains=job_title)

    job = jobs_qs.order_by("-created_at").first()

    if not job:

        return {
            "candidates": [],
            "summary": (
                f"No job found matching \"{job_title}\"."
                if job_title else
                "This company hasn't posted any jobs yet."
            ),
        }

    apps = Application.objects.filter(
        job=job
    ).select_related("student")[:30]

    scored = []

    for app in apps:

        try:

            score, reasons = compute_job_match(app.student, job)

        except Exception:

            score, reasons = 0, []

        scored.append({
            "name": app.student.full_name,
            "match_score": score,
            "status": app.get_status_display(),
        })

    scored.sort(key=lambda c: c["match_score"], reverse=True)

    return {
        "candidates": scored[:10],
        "job_title": job.title,
        "navigate_to": "/company/candidates",
        "summary": f"Top applicants for {job.title}.",
    }


def _tool_get_company_applications(profile, user, args):

    from jobsystem.models import Application

    apps = Application.objects.filter(
        job__company=profile
    ).select_related("student", "job").order_by("-applied_date")[:15]

    data = [
        {
            "candidate": app.student.full_name,
            "job_title": app.job.title,
            "status": app.get_status_display(),
        }
        for app in apps
    ]

    return {
        "applications": data,
        "navigate_to": "/company/candidates",
        "summary": (
            f"{len(data)} recent application(s)."
            if data else
            "No applications received yet."
        ),
    }


def _tool_get_company_interviews(profile, user, args):

    from jobsystem.models import Interview

    now = timezone.now()

    interviews = Interview.objects.filter(
        application__job__company=profile,
        interview_date__gte=now,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__student", "application__job"
    ).order_by("interview_date")[:10]

    data = [
        {
            "candidate": iv.application.student.full_name,
            "job_title": iv.application.job.title,
            "date": iv.interview_date.strftime("%b %d, %Y"),
            "time": iv.interview_date.strftime("%I:%M %p"),
        }
        for iv in interviews
    ]

    return {
        "interviews": data,
        "navigate_to": "/company/interviews",
        "summary": (
            f"{len(data)} upcoming interview(s)."
            if data else
            "No upcoming interviews scheduled."
        ),
    }


def _tool_get_active_job_postings(profile, user, args):

    from jobsystem.models import Job

    jobs = Job.objects.filter(
        company=profile, status="active"
    ).order_by("-created_at")[:10]

    data = [
        {
            "title": j.title,
            "applications": j.applications.count(),
        }
        for j in jobs
    ]

    return {
        "jobs": data,
        "navigate_to": "/company/jobs",
        "summary": (
            f"{len(data)} active job posting(s)."
            if data else
            "No active job postings right now."
        ),
    }


def _tool_list_all_job_postings(profile, user, args):
    """
    Full Manage Jobs tab coverage - every status, not just active,
    so "show my job postings" covers closed/draft ones too.
    """

    from jobsystem.models import Job

    jobs = Job.objects.filter(
        company=profile
    ).order_by("-created_at")[:15]

    data = [
        {
            "title": j.title,
            "status": (
                j.get_status_display()
                if hasattr(j, "get_status_display") else j.status
            ),
            "applications": j.applications.count(),
        }
        for j in jobs
    ]

    return {
        "jobs": data,
        "navigate_to": "/company/jobs",
        "summary": (
            f"{len(data)} job posting(s) total."
            if data else "No jobs posted yet."
        ),
    }


def _tool_get_company_analytics_summary(profile, user, args):

    from jobsystem.models import Job, Application, Interview

    jobs_qs = Job.objects.filter(company=profile)

    applications_qs = Application.objects.filter(job__company=profile)

    interviews_qs = Interview.objects.filter(
        application__job__company=profile
    )

    return {
        "total_jobs_posted": jobs_qs.count(),
        "active_jobs": jobs_qs.filter(status="active").count(),
        "total_applications": applications_qs.count(),
        "interviews_scheduled": interviews_qs.filter(
            status="scheduled"
        ).count(),
        "hired_candidates": applications_qs.filter(
            status="selected"
        ).count(),
        "navigate_to": "/company/analytics",
        "summary": "Company analytics summary.",
    }


def _tool_get_company_profile_info(profile, user, args):
    """
    Covers the Company Profile tab - a read-only snapshot of the
    company's own profile.
    """

    return {
        "company_name": profile.company_name,
        "industry": profile.industry,
        "website": profile.website,
        "description": profile.description,
        "company_size": profile.company_size,
        "verified": profile.verified,
        "approval_status": profile.approval_status,
        "navigate_to": "/company/profile",
        "summary": f"{profile.company_name}'s profile information.",
    }


COMPANY_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_candidates",
            "description": (
                "Search all student profiles on the platform (not "
                "just people who applied) by skill, name, course, or "
                "department, with an optional minimum CGPA. Use when "
                "the recruiter asks to find or search "
                "candidates/students matching some criteria."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A skill, name, or course keyword to search for.",
                    },
                    "department": {
                        "type": "string",
                        "description": "Department to filter by, if mentioned.",
                    },
                    "min_cgpa": {
                        "type": "number",
                        "description": "Minimum CGPA filter, if mentioned.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_candidates_for_job",
            "description": (
                "Get the best-matching applicants for one of the "
                "company's own job postings, ranked by AI match "
                "score. Use when the recruiter asks who the best/top "
                "candidates are for a specific role."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job title to check applicants for.",
                    }
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_applications",
            "description": "Get the company's recent job applications and their statuses.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_interviews",
            "description": "Get the company's upcoming scheduled interviews.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_job_postings",
            "description": "Get the company's currently active job postings and how many applications each has.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_job_postings",
            "description": (
                "Get every job posting the company has made, in any "
                "status (active, closed, draft), not just active "
                "ones. Use for 'show all my job postings' style "
                "questions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_analytics_summary",
            "description": (
                "Get a summary of the company's hiring analytics: "
                "jobs posted, active jobs, total applications, "
                "interviews scheduled, and candidates hired."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_profile_info",
            "description": (
                "Get the company's own profile details. Use when "
                "the recruiter asks about their own company profile."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


COMPANY_TOOL_EXECUTORS = {
    "search_candidates": _tool_search_candidates,
    "get_top_candidates_for_job": _tool_get_top_candidates_for_job,
    "get_company_applications": _tool_get_company_applications,
    "get_company_interviews": _tool_get_company_interviews,
    "get_active_job_postings": _tool_get_active_job_postings,
    "list_all_job_postings": _tool_list_all_job_postings,
    "get_company_analytics_summary": _tool_get_company_analytics_summary,
    "get_company_profile_info": _tool_get_company_profile_info,
}


# =====================================================
# RESUME ATTACHMENT (unchanged - separate from the tool-
# calling agent loop below, since a file attachment is
# handled directly, not routed through the LLM at all)
# =====================================================

def handle_resume_attachment(user, profile, uploaded_file, caption=""):
    """
    Called when the chat message includes a file attachment.
    Saves it as the student's active resume (same behaviour as the
    Resume page's upload), runs the standard AI analysis, and
    replies with a summary - including an offer to run the
    dedicated ATS check next.
    """

    from jobsystem.models import Resume
    from jobsystem.services.resume_ai import analyze_resume

    allowed_extensions = (".pdf", ".doc", ".docx")

    filename = getattr(uploaded_file, "name", "") or ""

    if not filename.lower().endswith(allowed_extensions):

        return (
            "I can only read resumes as PDF, DOC, or DOCX files - "
            "please resend it in one of those formats."
        )

    Resume.objects.filter(
        student=user, is_active=True
    ).update(is_active=False)

    resume = Resume.objects.create(

        student=user,

        file=uploaded_file,

        filename=filename,

        is_active=True,

    )

    try:

        # analyze_resume() takes the resume's Django file object
        # (works with any storage backend - local disk or
        # Cloudinary), not a filesystem path. resume.file.path
        # raises NotImplementedError under Cloudinary storage.
        result = analyze_resume(resume.file)

        resume.resume_score = result.get("resume_score", 0)

        resume.skills = result.get("skills", [])

        resume.experience = result.get("experience", [])

        resume.education = result.get("education", [])

        resume.certifications = result.get("certifications", [])

        resume.projects = result.get("projects", [])

        resume.missing_information = result.get(
            "missing_information", []
        )

        resume.job_categories = result.get("job_categories", [])

        resume.extracted_text = result.get("text", "")

        resume.save()

    except Exception as e:

        print("Chatbot resume analysis error:", e)

        return (
            f"Got your resume ({filename}) and saved it, but I "
            "couldn't finish analysing it just now. Try asking me "
            "\"improve my resume\" again in a moment."
        )

    lines = [
        f"Got it - I've saved \"{filename}\" as your active resume."
    ]

    lines.append(f"Resume score: {resume.resume_score}/100.")

    if resume.missing_information:

        lines.append("A few things to improve:")

        for item in resume.missing_information[:5]:

            lines.append(f"- {item}")

    lines.append(
        "\nWant me to check how ATS-friendly it is too? Just ask "
        "\"is my resume ATS friendly\"."
    )

    return "\n".join(lines)


# =====================================================
# GROQ CALLS
# =====================================================

def _call_groq_plain(messages):
    """
    No tools offered - used for guests and roles with no tool set
    (placement_admin/super_admin, or a student/company with no
    profile yet), same plain grounded-chat behaviour as before.
    """

    last_error = None

    for model_name in GROQ_MODEL_FALLBACKS:

        try:

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.4,
                max_tokens=500,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:

            last_error = e

            continue

    raise last_error or Exception("Chatbot: all models failed")


def _call_groq_with_tools(messages, tools):

    last_error = None

    for model_name in GROQ_MODEL_FALLBACKS:

        try:

            return client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=600,
            )

        except Exception as e:

            last_error = e

            continue

    raise last_error or Exception("Chatbot: all models failed")


# =====================================================
# MAIN ENTRY POINT
# =====================================================

# Keys that, when present in a tool's result, are forwarded to the
# frontend as-is (never rewritten by the model) so it can render
# real cards/lists/buttons instead of plain text.

_FORWARDED_LIST_KEYS = (
    "matched_jobs", "candidates", "applications",
    "interviews", "jobs", "drives", "notifications",
)


def generate_reply(user, message, history=None):
    """
    history: optional list of {"sender": "user"|"bot", "message": "..."}
    for short conversational continuity.

    Returns either a plain string (guests, placement_admin/super_admin,
    or any tool-less reply) or a dict {"reply": ..., plus extra keys
    like "matched_jobs"/"candidates"/"resume_download"/"navigate_to"}
    when a tool ran.
    """

    # ---------------- AI SECURITY (Requirement 31) ----------------

    if _is_security_probe(message):

        return SECURITY_REFUSAL

    # ---------------- PICK THE RIGHT ACTOR + TOOL SET ----------------

    role = (
        getattr(user, "role", None)
        if user and getattr(user, "is_authenticated", False)
        else None
    )

    actor_profile = None

    tool_schemas = None

    tool_executors = None

    if role == "student":

        actor_profile = getattr(user, "student_profile", None)

        if actor_profile:

            tool_schemas = TOOL_SCHEMAS

            tool_executors = TOOL_EXECUTORS

    elif role == "company":

        actor_profile = getattr(user, "company_profile", None)

        if actor_profile:

            tool_schemas = COMPANY_TOOL_SCHEMAS

            tool_executors = COMPANY_TOOL_EXECUTORS

    # ---------------- ACTIVE MOCK INTERVIEW ----------------
    # If the student has a mock interview in progress, THIS message
    # is their answer to the current question - route entirely to
    # the dedicated interview handler instead of the normal
    # tool-calling flow below, since a normal LLM turn would treat
    # their answer as a fresh, unrelated request.

    if role == "student" and actor_profile:

        from jobsystem.models import MockInterviewSession

        active_session = MockInterviewSession.objects.filter(
            student=actor_profile, status="in_progress"
        ).order_by("-created_at").first()

        if active_session:

            if _looks_like_platform_request(message):

                # A real question about jobs/applications/resume/etc -
                # not idle chat, and not an interview answer. End the
                # session cleanly and let this message continue into
                # the normal tool-calling flow below so it actually
                # gets answered, instead of being swallowed into
                # "interview answer" or "stay on topic" handling.

                active_session.status = "cancelled"

                active_session.save()

            else:

                return _handle_mock_interview_turn(active_session, user, message)

    context = build_context(user)

    knowledge = get_knowledge_base_snippets()

    system_prompt = SYSTEM_TEMPLATE.format(
        context_json=json.dumps(context, default=str),
        knowledge_json=json.dumps(knowledge, default=str),
    )

    setting = get_active_chatbot_setting()

    if setting and setting.system_prompt:

        system_prompt += (
            "\n\nADDITIONAL INSTRUCTIONS FROM PLACEMENT ADMIN:\n"
            + setting.system_prompt
        )

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    for turn in (history or [])[-6:]:

        role_for_turn = "assistant" if turn.get("sender") == "bot" else "user"

        messages.append({
            "role": role_for_turn,
            "content": turn.get("message", "")
        })

    messages.append({
        "role": "user",
        "content": message
    })

    if not tool_schemas:

        try:

            return _call_groq_plain(messages)

        except Exception as e:

            print("Chatbot error:", e)

            return (
                "I'm having trouble reaching the assistant right now. "
                "Please try again in a moment."
            )

    try:

        response = _call_groq_with_tools(messages, tool_schemas)

    except Exception as e:

        print("Chatbot error:", e)

        return (
            "I'm having trouble reaching the assistant right now. "
            "Please try again in a moment."
        )

    choice_message = response.choices[0].message

    tool_calls = getattr(choice_message, "tool_calls", None)

    if not tool_calls:

        return (choice_message.content or "").strip()

    tool_call = tool_calls[0]

    tool_name = tool_call.function.name

    try:

        tool_args = json.loads(tool_call.function.arguments or "{}")

    except Exception:

        tool_args = {}

    executor = tool_executors.get(tool_name)

    if not executor:

        return "I'm not able to do that yet - try asking in a different way."

    try:

        tool_result = executor(actor_profile, user, tool_args)

    except Exception as e:

        print("Chatbot tool execution error:", tool_name, e)

        return (
            "I ran into an issue while doing that. Please try again "
            "in a moment, or ask me in a different way."
        )

    messages.append({
        "role": "assistant",
        "content": choice_message.content or "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": tool_call.function.arguments,
                },
            }
        ],
    })

    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(tool_result, default=str),
    })

    # Write-action tools (they create/modify a real database record) -
    # their own "summary" is used directly as the reply, bypassing the
    # second Groq pass entirely. This guarantees the confirmation text
    # shown to the user always matches exactly what the database write
    # actually did (success or failure) - never a model-generated
    # paraphrase that could drift from what really happened, which is
    # what let the model previously claim "application submitted"
    # without ever having called apply_to_job at all.

    _WRITE_ACTION_TOOLS = {
        "apply_to_job", "request_interview_slot",
        "raise_placement_query", "update_my_skills",
    }

    if tool_name == "start_mock_interview" and tool_result.get("question"):

        # The interviewer question is already exactly what should be
        # shown - skipping the second Groq pass here means it's never
        # paraphrased, shortened, or mixed with commentary before the
        # student sees the actual question they need to answer.

        final_text = tool_result["question"]

    elif tool_name in _WRITE_ACTION_TOOLS:

        final_text = tool_result.get("summary", "Done.")

    else:

        try:

            final_response = _call_groq_with_tools(messages, tool_schemas)

            final_text = (final_response.choices[0].message.content or "").strip()

        except Exception as e:

            print("Chatbot follow-up error:", e)

            final_text = tool_result.get(
                "summary", "Here's what I found."
            )

        if not final_text:

            final_text = tool_result.get("summary", "Here's what I found.")

    # Structured, agent-style data always comes straight from the
    # tool's own return value above - never from anything the model
    # wrote - so the frontend shows real data, not a hallucinated
    # summary of it.

    result_payload = {"reply": final_text}

    for key in _FORWARDED_LIST_KEYS:

        if key in tool_result:

            result_payload[key] = tool_result[key]

    # Resume/document download - forwarded as its own small object
    # (not a URL) so the frontend triggers a real authenticated
    # blob download button, rather than a link the model could get
    # wrong or that would navigate away from the app entirely.

    if tool_result.get("resume_id"):

        result_payload["resume_download"] = {
            "resume_id": tool_result["resume_id"],
            "filename": tool_result.get("filename", "Resume"),
        }

    # Mock interview score report - only ever present via the
    # get_mock_interview_report tool path (the live session's own
    # completion already returns "mock_interview_report" directly
    # from _finish_mock_interview, bypassing this shared tail).

    if tool_result.get("score_report"):

        result_payload["mock_interview_report"] = tool_result["score_report"]

    if tool_result.get("navigate_to"):

        result_payload["navigate_to"] = tool_result["navigate_to"]

    return result_payload
