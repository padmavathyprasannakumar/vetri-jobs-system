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
which real action is needed (find jobs / find candidates, check
status, apply, check interviews, etc), then calls the matching
Python tool below. Each tool runs the exact same kind of real Django
query the platform's own pages already use (nothing invented,
nothing pulled from anywhere new) and returns structured JSON, which
is fed back to the model for a natural-language reply. Any
job/candidate list a tool returns (job id/title/apply link/score, or
candidate name/match score) is taken directly from that JSON - never
from what the model writes - so the frontend's result cards and
auto-navigation always reflect real data. Guests and any other role
(placement_admin/super_admin) get the plain grounded-context chat,
same as before - no tools are offered to them.
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
checking eligibility, applying to a job, application status,
interviews, resume feedback, ATS checking, placement drives,
requesting an interview slot, or raising a query. For a company, this
includes searching candidates, finding top applicants for one of
their jobs, viewing applications, interviews, or active job postings.
Only call apply_to_job when a student clearly, explicitly asks to
apply to a specific named job - never as a side effect of a general
question.

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
#
# Each tool below is a plain Python function that runs a real query
# against real records, returning structured JSON the LLM's final
# reply is grounded in. A tool's "matched_jobs"/"navigate_to" keys
# (only ever present for job search/eligibility) are forwarded to
# the frontend as-is - the model never gets a chance to alter that
# structured part.
# =====================================================

def _serialize_matched_job(job, match_score=None, reasons=None):

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
        "apply_url": f"/student/jobs/{job.id}/apply",
        "details_url": f"/student/jobs/{job.id}",
    }


def _tool_find_matching_jobs(profile, user, args):

    from jobsystem.models import Job
    from jobsystem.services.job_matching import rank_jobs_for_student

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")[:40]

    ranked = rank_jobs_for_student(profile, jobs)[:5]

    if not ranked:

        return {
            "matched_jobs": [],
            "summary": "No active job postings found right now.",
        }

    matched_jobs = [
        _serialize_matched_job(job, score, reasons)
        for job, score, reasons in ranked
    ]

    return {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": f"Found {len(matched_jobs)} jobs matching the student's profile.",
    }


def _tool_check_job_eligibility(profile, user, args):

    from jobsystem.models import Job
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

    matched_jobs = []

    for job in eligible[:8]:

        try:

            score, reasons = compute_job_match(profile, job)

        except Exception:

            score, reasons = None, []

        matched_jobs.append(_serialize_matched_job(job, score, reasons))

    return {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": f"The student is eligible for {len(matched_jobs)} open jobs.",
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

    from jobsystem.models import Application

    apps = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company").order_by("-applied_date")[:10]

    applications = [
        {
            "job_title": app.job.title,
            "company": app.job.company.company_name if app.job.company else "Company",
            "status": app.get_status_display(),
        }
        for app in apps
    ]

    return {
        "applications": applications,
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
        "filename": resume.filename or "Resume",
        "download_url": f"/student/resume/{resume.id}/download/",
        "summary": f"Resume available for download: {resume.filename or 'Resume'}.",
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
                "suitable/recommended jobs for themselves."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
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
                "jobs they're eligible for."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
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
            "description": "Get the student's current job applications and their statuses.",
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
    {
        "type": "function",
        "function": {
            "name": "get_resume_download_link",
            "description": "Get a download link for the student's current active resume.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


TOOL_EXECUTORS = {
    "find_matching_jobs": _tool_find_matching_jobs,
    "check_job_eligibility": _tool_check_job_eligibility,
    "apply_to_job": _tool_apply_to_job,
    "get_application_status": _tool_get_application_status,
    "get_upcoming_interviews": _tool_get_upcoming_interviews,
    "get_resume_feedback": _tool_get_resume_feedback,
    "check_ats_friendliness": _tool_check_ats_friendliness,
    "get_upcoming_drives": _tool_get_upcoming_drives,
    "request_interview_slot": _tool_request_interview_slot,
    "raise_placement_query": _tool_raise_placement_query,
    "get_resume_download_link": _tool_get_resume_download_link,
}


# =====================================================
# COMPANY AGENT TOOLS
#
# Same shape/spirit as the student tools above, scoped to the
# signed-in company's own jobs/candidates/interviews only - a
# company can never search or see another company's applicants,
# applications, or interviews through these.
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
]


COMPANY_TOOL_EXECUTORS = {
    "search_candidates": _tool_search_candidates,
    "get_top_candidates_for_job": _tool_get_top_candidates_for_job,
    "get_company_applications": _tool_get_company_applications,
    "get_company_interviews": _tool_get_company_interviews,
    "get_active_job_postings": _tool_get_active_job_postings,
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

def generate_reply(user, message, history=None):
    """
    history: optional list of {"sender": "user"|"bot", "message": "..."}
    for short conversational continuity.

    Returns either a plain string (guests, placement_admin/super_admin,
    or any tool-less reply) or a dict {"reply": ..., plus extra keys
    like "matched_jobs"/"candidates"/"navigate_to"} when a tool ran -
    see the module docstring and the two _serialize_*/tool functions
    above for the exact shapes.
    """

    # ---------------- AI SECURITY (Requirement 31) ----------------
    # Checked before anything else touches the LLM or the database -
    # a request that even looks like it's probing for another
    # student's/company's data is refused outright, regardless of
    # tools.

    if _is_security_probe(message):

        return SECURITY_REFUSAL

    # ---------------- PICK THE RIGHT ACTOR + TOOL SET ----------------
    # A student gets the student tools against their own
    # StudentProfile; a company gets the company tools against their
    # own CompanyProfile. Anyone else (guest, placement_admin,
    # super_admin, or a student/company with no profile yet) gets no
    # tools at all - just the plain grounded-context conversation,
    # same as before this agent rebuild.

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

    context = build_context(user)

    knowledge = get_knowledge_base_snippets()

    system_prompt = SYSTEM_TEMPLATE.format(
        context_json=json.dumps(context, default=str),
        knowledge_json=json.dumps(knowledge, default=str),
    )

    # Admin-configured extra instructions (Requirement 28 -
    # "AI prompts/configuration"), layered on top of the grounding
    # rules above rather than replacing them, so the security and
    # data-grounding behaviour always stays intact.

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

    # Only the first requested tool call is executed - keeps this
    # predictable and avoids silently chaining multiple
    # side-effecting actions (like applying to a job) from one
    # ambiguous message.

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

    # Feed the tool's real result back to Groq for a natural-language
    # reply, grounded in this exact data.

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

    # Structured, agent-style data (job/candidate cards, navigation)
    # always comes straight from the tool's own return value above -
    # never from anything the model wrote - so the frontend shows
    # real data, not a hallucinated summary of it.

    result_payload = {"reply": final_text}

    for key in ("matched_jobs", "candidates", "applications", "interviews", "jobs", "drives"):

        if key in tool_result:

            result_payload[key] = tool_result[key]

    if tool_result.get("navigate_to"):

        result_payload["navigate_to"] = tool_result["navigate_to"]

    return result_payload
