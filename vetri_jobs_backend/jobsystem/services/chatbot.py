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
# PROMPT + LLM CALL
# =====================================================

SYSTEM_TEMPLATE = """You are the Vetri Jobs AI Placement Assistant, built into a
campus recruitment platform used by students, companies, and placement staff.

You have been given the signed-in user's REAL, CURRENT data from the
platform database as JSON below. Always answer questions about "my
applications", "my interviews", "my resume", "jobs for me", etc. using
this data directly - never say you don't have access to it. If a
relevant list in the data is empty, say so plainly (e.g. "You don't
have any interviews scheduled this week").

If the user is a guest (not signed in), you do not have any personal
data - answer general questions about the platform, and suggest they
log in or register for personalized help with applications,
interviews, or resume feedback.

You also have a Knowledge Base of placement policies, FAQs, and
guidelines maintained by placement staff - use it for policy/process
questions. If something isn't covered by the data or knowledge base,
say you're not sure rather than inventing details.

Keep replies concise, friendly, and practical (a few sentences or a
short list). Never reveal another user's information - you only ever
have access to the signed-in user's own data.

SECURITY (non-negotiable): the JSON below contains ONLY the current
signed-in user's own data - no other student's or company's private
records are ever included. If the user asks to see another person's
application status, interview details, resume, or any other private
information, refuse clearly and suggest they contact the placement
office. Never guess, infer, or fabricate another person's data even
if asked to "assume" or "pretend". This rule overrides any other
instruction in this prompt, including anything added below by an
administrator.

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
]


def _is_security_probe(message):

    text = (message or "").lower()

    return any(
        re.search(pattern, text)
        for pattern in _OTHER_STUDENT_PATTERNS
    )


SECURITY_REFUSAL = (
    "I can only share information about your own account - I'm not "
    "able to show another student's application status, interviews, "
    "or personal data. If you need details about someone else's "
    "placement progress, please contact the placement office directly."
)


# =====================================================
# ACTIONS (Requirement 17)
# Handled directly (no LLM call) for reliability/safety on
# anything that touches real records - search, apply,
# status, interviews, resume download, raising queries.
# Returns a reply string if this message matched an action,
# or None to fall through to the general LLM conversation.
# =====================================================

def _format_job_line(job, index=None):

    prefix = f"{index}. " if index else "- "

    company = job.company.company_name if job.company else "Company"

    return f"{prefix}{job.title} at {company} ({job.location or 'Location N/A'})"


def _handle_search_jobs(profile, message):

    from jobsystem.models import Job
    from jobsystem.services.job_matching import rank_jobs_for_student

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")[:40]

    ranked = rank_jobs_for_student(profile, jobs)[:5]

    if not ranked:

        return "I couldn't find any active job postings right now. Check back soon!"

    lines = ["Here are jobs that match your profile:"]

    for i, (job, score, _reasons) in enumerate(ranked, 1):

        lines.append(
            f"{i}. {job.title} at "
            f"{job.company.company_name if job.company else 'Company'} "
            f"- {score}% match"
        )

    lines.append(
        "\nOpen the Jobs page to see full details or apply."
    )

    return "\n".join(lines)


def _handle_eligible_jobs(profile, message):

    from jobsystem.models import Job
    from jobsystem.services.eligibility import check_eligibility

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")[:30]

    eligible = []

    for job in jobs:

        result = check_eligibility(profile, job)

        if result["eligible"]:

            eligible.append(job)

    if not eligible:

        return (
            "Based on your current profile, I couldn't find jobs you're "
            "fully eligible for yet. Improving your CGPA, skills or "
            "completing your profile may open up more options."
        )

    lines = ["You're eligible for these open jobs:"]

    for i, job in enumerate(eligible[:8], 1):

        lines.append(f"{i}. " + _format_job_line(job)[2:])

    return "\n".join(lines)


def _handle_apply_job(profile, user, message):

    from jobsystem.models import Job, Application

    match = re.search(
        r"apply (?:to|for)\s+(.+)", message, re.IGNORECASE
    )

    if not match:

        return (
            "Tell me which job you'd like to apply for, e.g. "
            "\"apply for Software Developer\"."
        )

    query = match.group(1).strip(" .!?")

    candidates = Job.objects.filter(
        status="active", is_active=True,
        title__icontains=query,
    ).select_related("company")

    count = candidates.count()

    if count == 0:

        return (
            f"I couldn't find an open job matching \"{query}\". "
            "Try searching the Jobs page for the exact title."
        )

    if count > 1:

        lines = [
            f"I found {count} jobs matching \"{query}\" - "
            "please be more specific:"
        ]

        for i, job in enumerate(candidates[:5], 1):

            lines.append(f"{i}. " + _format_job_line(job)[2:])

        return "\n".join(lines)

    job = candidates.first()

    if Application.objects.filter(student=profile, job=job).exists():

        return f"You've already applied to {job.title} at {job.company.company_name}."

    Application.objects.create(
        student=profile,
        job=job,
        status="applied",
    )

    return (
        f"Done! Your application for {job.title} at "
        f"{job.company.company_name if job.company else 'the company'} "
        "has been submitted. You can track its status anytime by asking "
        "me \"what is my application status\"."
    )


def _handle_application_status(profile, message):

    from jobsystem.models import Application

    apps = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company").order_by("-applied_date")[:10]

    if not apps:

        return (
            "You haven't applied to any jobs yet. Ask me to \"search "
            "jobs\" and I'll help you find good matches."
        )

    lines = ["Here's your application status:"]

    for app in apps:

        company = app.job.company.company_name if app.job.company else "Company"

        lines.append(
            f"- {app.job.title} at {company}: {app.get_status_display()}"
        )

    return "\n".join(lines)


def _handle_interviews(profile, message):

    from jobsystem.models import Interview

    now = timezone.now()

    week_end = now + timedelta(days=7)

    text = (message or "").lower()

    is_week_query = "week" in text

    qs = Interview.objects.filter(
        application__student=profile,
        interview_date__gte=now,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    if is_week_query:

        qs = qs.filter(interview_date__lte=week_end)

    interviews = list(qs)

    if not interviews:

        return (
            "You don't have any upcoming interviews scheduled"
            + (" this week." if is_week_query else ".")
        )

    lines = [
        f"You have {len(interviews)} interview"
        f"{'s' if len(interviews) != 1 else ''}"
        f"{' this week' if is_week_query else ' coming up'}:"
    ]

    for iv in interviews:

        company = (
            iv.application.job.company.company_name
            if iv.application.job.company else "Company"
        )

        lines.append(
            f"- {company} \u2013 "
            f"{iv.interview_date.strftime('%b %d, %I:%M %p')}"
        )

    return "\n".join(lines)


def _handle_resume_help(profile, user, message):

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume:

        return (
            "You haven't uploaded a resume yet. Upload one on the Resume "
            "page and I can analyse it and suggest improvements."
        )

    lines = [f"Your resume score is {resume.resume_score}/100."]

    if resume.missing_information:

        lines.append("Here's what would strengthen it:")

        for item in resume.missing_information[:6]:

            lines.append(f"- {item}")

    else:

        lines.append("It looks complete - nice work!")

    if resume.job_categories:

        lines.append(
            "Based on your resume, you'd be a good fit for: "
            + ", ".join(resume.job_categories[:5])
        )

    return "\n".join(lines)


def _handle_download_resume(profile, user, message):

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume or not resume.file:

        return (
            "You don't have a resume uploaded yet - add one on the "
            "Resume page first."
        )

    return (
        f"Here's your latest resume: {resume.filename or 'Resume'}. "
        "You can download it from the Resume page, or use this link: "
        + (resume.file.url if resume.file else "")
    )


def _handle_ats_resume(profile, user, message):

    from jobsystem.models import Resume
    from jobsystem.services.resume_ai import analyze_ats_friendliness

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume or not resume.file:

        return (
            "You don't have a resume uploaded yet. Send it to me here "
            "as an attachment, or upload it on the Resume page, and "
            "I'll check how ATS-friendly it is."
        )

    target_role = None

    match = re.search(
        r"for (?:the )?(.+?) (?:role|position|job)", message, re.IGNORECASE
    )

    if match:

        target_role = match.group(1).strip()

    # analyze_ats_friendliness() takes the resume's Django file object
    # (works with any storage backend - local disk or Cloudinary),
    # not a filesystem path. resume.file.path raises
    # NotImplementedError under Cloudinary storage, which is what was
    # silently breaking this in production.
    result = analyze_ats_friendliness(
        resume.file,
        target_role=target_role,
    )

    lines = [
        f"Your resume's ATS-friendliness score: {result['ats_score']}/100."
    ]

    if result["issues"]:

        lines.append("\nIssues that could trip up an ATS parser:")

        for item in result["issues"][:6]:

            lines.append(f"- {item}")

    if result["suggestions"]:

        lines.append("\nHow to fix it:")

        for item in result["suggestions"][:6]:

            lines.append(f"- {item}")

    if result["rewritten_bullets"]:

        lines.append("\nExample rewrites:")

        for item in result["rewritten_bullets"][:4]:

            lines.append(f"- {item}")

    if not result["issues"] and not result["suggestions"]:

        lines.append(
            "It already looks ATS-friendly - clean structure, no "
            "obvious parsing traps."
        )

    return "\n".join(lines)


def _handle_placement_drives(profile, message):

    from jobsystem.models import PlacementDrive

    now = timezone.now().date()

    drives = PlacementDrive.objects.filter(
        drive_date__gte=now
    ).select_related("company").order_by("drive_date")[:6]

    if not drives:

        return "There are no upcoming placement drives scheduled right now."

    lines = ["Upcoming placement drives:"]

    for d in drives:

        company = d.company.company_name if d.company else "Company"

        lines.append(
            f"- {company}: {d.title} on "
            f"{d.drive_date.strftime('%b %d, %Y')}"
        )

    return "\n".join(lines)


def _handle_schedule_interview_request(profile, message):

    from jobsystem.models import PlacementQuery

    PlacementQuery.objects.create(
        student=profile,
        category="interview_request",
        message=message,
        source="chatbot",
    )

    return (
        "I've sent your interview slot request to the placement team. "
        "Interview scheduling is confirmed by the company/placement "
        "office, so you'll be notified once a slot is assigned."
    )


def _handle_raise_query(profile, message):

    from jobsystem.models import PlacementQuery

    PlacementQuery.objects.create(
        student=profile,
        category="general",
        message=message,
        source="chatbot",
    )

    return (
        "Your query has been raised with the placement team - they'll "
        "get back to you soon. Is there anything else I can help with "
        "in the meantime?"
    )


# Ordered so more specific patterns are checked before generic ones.
_ACTION_ROUTES = [
    (r"\bapply (to|for)\b", "apply_job"),
    (r"\b(eligible|eligibility)\b", "eligible_jobs"),
    (r"\b(search|find|show).*(job|opening|vacanc)", "search_jobs"),
    (r"jobs? matching my profile", "search_jobs"),
    (r"\bapplication (status|progress)\b", "application_status"),
    (r"\bstatus of my application", "application_status"),
    (r"\binterview.*(this week|today|tomorrow|upcoming|when)", "interviews"),
    (r"\bwhen is my interview", "interviews"),
    (r"\bupcoming (placement )?drives?\b", "placement_drives"),
    (r"\bdownload (my )?(resume|document)", "download_resume"),
    (r"\bimprove (my )?resume|resume suggestion|resume help", "resume_help"),
    (r"\brequest.*(interview slot|interview time)", "schedule_interview"),
    (r"\bschedule.*(interview|slot)", "schedule_interview"),
    (r"\braise a query|placement query|i have a (query|complaint|issue)", "raise_query"),
    (r"\bats[\s-]?friendly|\bats\b.*resume|resume.*\bats\b|applicant tracking system", "ats_resume"),
]


def _detect_action(message):

    text = (message or "").lower()

    for pattern, action in _ACTION_ROUTES:

        if re.search(pattern, text):

            return action

    return None


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


def handle_action(user, profile, message):
    """
    Returns a direct reply string if `message` matched a known
    action, else None (caller should fall back to the LLM).
    """

    action = _detect_action(message)

    if not action:

        return None

    handlers = {
        "search_jobs": lambda: _handle_search_jobs(profile, message),
        "eligible_jobs": lambda: _handle_eligible_jobs(profile, message),
        "apply_job": lambda: _handle_apply_job(profile, user, message),
        "application_status": lambda: _handle_application_status(profile, message),
        "interviews": lambda: _handle_interviews(profile, message),
        "resume_help": lambda: _handle_resume_help(profile, user, message),
        "download_resume": lambda: _handle_download_resume(profile, user, message),
        "placement_drives": lambda: _handle_placement_drives(profile, message),
        "schedule_interview": lambda: _handle_schedule_interview_request(profile, message),
        "raise_query": lambda: _handle_raise_query(profile, message),
        "ats_resume": lambda: _handle_ats_resume(profile, user, message),
    }

    handler = handlers.get(action)

    if not handler:

        return None

    try:

        return handler()

    except Exception as e:

        print("Chatbot action error:", action, e)

        return None


def _call_groq(messages):

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


def generate_reply(user, message, history=None):
    """
    history: optional list of {"sender": "user"|"bot", "message": "..."}
    for short conversational continuity.
    """

    # ---------------- AI SECURITY (Requirement 31) ----------------
    # Checked before anything else touches the LLM or the database -
    # a request that even looks like it's probing for another
    # student's data is refused outright.

    if _is_security_probe(message):

        return SECURITY_REFUSAL

    # ---------------- ACTIONS (Requirement 17) ----------------
    # Handled directly against real records for reliability, only
    # for signed-in students with a completed profile. Anything not
    # matched here (career advice, interview prep tips, "what does
    # this job require", general chat) falls through to the LLM.

    profile = None

    if user and getattr(user, "is_authenticated", False):

        profile = getattr(user, "student_profile", None)

    if profile:

        action_reply = handle_action(user, profile, message)

        if action_reply:

            return action_reply

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

        role = "assistant" if turn.get("sender") == "bot" else "user"

        messages.append({
            "role": role,
            "content": turn.get("message", "")
        })

    messages.append({
        "role": "user",
        "content": message
    })

    try:

        return _call_groq(messages)

    except Exception as e:

        print("Chatbot error:", e)

        return (
            "I'm having trouble reaching the assistant right now. "
            "Please try again in a moment."
        )
