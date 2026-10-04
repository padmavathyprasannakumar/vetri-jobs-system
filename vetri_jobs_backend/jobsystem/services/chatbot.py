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

RESUME SCORE (single source of truth):
The resume is scored by AI exactly once per upload/"Analyse Resume"
click (services/resume_ai.py), and that resume_score is saved on the
Resume record. Every chatbot path (context, get_resume_feedback,
check_ats_friendliness, get_career_plan) reads that SAME saved score
and never asks the AI to produce a new one, so the chatbot and the
Resume page always show the identical number.
"""

import json
import re
import threading
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from datetime import timedelta

from django.utils import timezone


# Django's timezone.now() always returns raw UTC when timezone-aware
# (USE_TZ=True) - it does NOT automatically convert to settings.TIME_ZONE.
# A real report found the chatbot's own "good morning/afternoon/evening"
# greeting judgment, and any "today" date math, was silently using raw
# UTC the whole time - not even the server's configured Asia/Kuala_Lumpur
# zone, let alone India time, which this platform's actual users are in.
#
# India Standard Time is a fixed UTC+5:30 offset with no daylight saving
# ever observed, so a plain timedelta is used here rather than the
# zoneinfo/pytz database - avoiding a new import dependency entirely for
# a timezone that, unlike most others, never actually changes. Every
# date/time-sensitive piece of the chatbot (the prompt's CURRENT DATE
# AND TIME, and any "is this happening today" filter) goes through this
# one helper, so there is exactly one place controlling what "now"
# means platform-wide.

INDIA_OFFSET = timedelta(hours=5, minutes=30)


def _india_now():

    return timezone.now() + INDIA_OFFSET


def _to_india_time(stored_dt):
    """Converts a stored UTC-aware datetime (e.g. Interview.interview_date)
    to its India Standard Time equivalent, purely for DISPLAY - every
    place that formats an interview's date/time for the student goes
    through this now, instead of calling .strftime() directly on the
    raw UTC value (which a real report found happening in seven
    separate places - every interview time shown anywhere in the
    chatbot was silently off by the UTC/IST difference)."""

    return stored_dt + INDIA_OFFSET


def _india_today_utc_bounds():
    """(start_utc, end_utc): the true UTC instants marking the start and
    end of "today" in India time - used to filter UTC-stored datetimes
    (like Interview.interview_date) for an India-local "today" without
    needing to shift every row individually. Subtracting INDIA_OFFSET
    from the shifted midnight values converts them back to genuine UTC
    instants, undoing the earlier shift correctly."""

    india_midnight_today = _india_now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    start_utc = india_midnight_today - INDIA_OFFSET

    end_utc = start_utc + timedelta(days=1)

    return start_utc, end_utc

from groq import Groq

import os


# Speed / reliability settings (all overridable from Render's environment
# variables without touching code).
#
# The Groq SDK's defaults are a 60-second timeout AND 2 automatic retries
# per request - and this file also falls back through several models. One
# slow or rate-limited response could therefore burn the browser's whole
# 60-second window (the "timeout of 60000ms exceeded" error) with no reply.
# Instead: each attempt gets a short timeout, retries are handled by our
# own model fallback below (max_retries=0), and one overall time budget
# per chat message stops us trying more models once it's nearly used up,
# so the student always gets an answer or a clear message well before
# the browser gives up.

GROQ_ATTEMPT_TIMEOUT = float(os.getenv("GROQ_ATTEMPT_TIMEOUT", "12"))

GROQ_REQUEST_BUDGET = float(os.getenv("GROQ_REQUEST_BUDGET", "28"))

GROQ_MIN_ATTEMPT_WINDOW = 8.0   # don't start a new attempt with less than this left

# What "new jobs" means, everywhere: the "new jobs" alert AND the "Show me new
# jobs" search must agree (the alert used to look back 3 days while the search
# looked back 14, so a student could get "no new jobs" from the assistant and
# then a list from the button).

RECENT_JOB_DAYS = 14


try:

    client = Groq(
        api_key=os.getenv("GROQ_API_KEY"),
        timeout=GROQ_ATTEMPT_TIMEOUT,
        max_retries=0,
    )

except TypeError:

    # An older SDK that doesn't accept these options - keep working with
    # its defaults rather than failing at import time.

    client = Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )


# One clock per chat message (per thread), started in generate_reply().

_request_clock = threading.local()


def _start_request_clock():

    _request_clock.started = time.monotonic()


def _stop_request_clock():

    _request_clock.started = None


def _time_left():
    """Seconds left in this message's AI budget, or None if no clock."""

    started = getattr(_request_clock, "started", None)

    if started is None:

        return None

    return GROQ_REQUEST_BUDGET - (time.monotonic() - started)


GROQ_MODEL_FALLBACKS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    # llama-3.3-70b-versatile removed: Groq has deprecated it (confirmed
    # via Render logs - every call 404s instantly with "model_not_found"),
    # so it was silently wasting the last fallback attempt on a guaranteed
    # failure. Add a real, currently-available third model here if wanted -
    # check https://console.groq.com/docs/models for the current list.
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
        "date": _to_india_time(iv.interview_date).strftime("%b %d, %Y"),
        "time": _to_india_time(iv.interview_date).strftime("%I:%M %p"),
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
            "score_note": (
                "Official AI resume score - identical to the Resume "
                "page. Always quote this exact number."
            ),
            "skills_detected": resume.skills,
            "missing_information": resume.missing_information,
            "suggested_job_categories": resume.job_categories,
        }

    # NOTE: the per-message AI job ranking ("recommended_jobs") was
    # removed from this context - it ran the matching engine on every
    # single chat message (slow/costly). The find_matching_jobs tool
    # does the same ranking on demand, only when it's actually needed.

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


# =====================================================
# PROACTIVE ALERTS (chatbot speaks first, no AI call)
# =====================================================

def _build_student_proactive_alerts(user):
    """Things the student should hear about without having to ask."""

    from jobsystem.models import (
        Interview, Notification, Resume, Job, Application,
    )

    profile = getattr(user, "student_profile", None)

    if not profile:
        return []

    now = timezone.now()

    alerts = []

    # 1) Interview within the next 24 hours
    # Interviews auto-created as a placeholder (recruiter picked
    # "Interview Scheduled" from the status dropdown without a real
    # date) are skipped, so students never get a reminder for a
    # made-up "tomorrow" interview.

    soon = Interview.objects.filter(
        application__student=profile,
        interview_date__gte=now,
        interview_date__lte=now + timedelta(hours=24),
        status__in=["scheduled", "rescheduled"],
    ).exclude(
        remarks__icontains="this date/time is a placeholder"
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date").first()

    if soon:

        hours = max(int((soon.interview_date - now).total_seconds() // 3600), 0)

        when = (
            "in less than an hour" if hours == 0
            else f"in about {hours} hour(s)"
        )

        alerts.append({
            "key": f"interview:{soon.id}:{soon.interview_date:%Y%m%d%H%M}",
            "type": "interview_soon",
            "text": (
                f"Reminder: your interview for {soon.application.job.title} "
                f"is {when} ({soon.interview_date:%I:%M %p}). "
                "Want prep tips or a quick mock interview?"
            ),
            "actions": [
                "Help me prepare for my interview",
                "Start a mock interview",
            ],
        })

    # 2) Unread notifications
    unread = Notification.objects.filter(user=user, is_read=False).count()

    if unread:

        alerts.append({
            "key": f"notif:{unread}",
            "type": "notifications",
            "text": f"You have {unread} unread notification(s).",
            "actions": ["Show my notifications"],
        })

    # 3) No active resume
    if not Resume.objects.filter(student=user, is_active=True).exists():

        alerts.append({
            "key": "resume:missing",
            "type": "resume",
            "text": (
                "You haven't uploaded a resume yet. "
                "Attach one here and I'll score it."
            ),
            "actions": [],
        })

    # 4) New jobs (posted within RECENT_JOB_DAYS - the same window the
    # "Show me new jobs" search uses) that the student hasn't applied to
    applied_ids = Application.objects.filter(
        student=profile
    ).values_list("job_id", flat=True)

    new_jobs = Job.objects.filter(
        status="active", is_active=True,
        created_at__gte=now - timedelta(days=RECENT_JOB_DAYS),
    ).exclude(id__in=applied_ids).count()

    if new_jobs:

        alerts.append({
            "key": f"newjobs:{new_jobs}:{now:%Y%m%d}",
            "type": "new_jobs",
            "text": (
                f"{new_jobs} new job(s) were posted in the last "
                f"{RECENT_JOB_DAYS} days that you haven't applied to."
            ),
            "actions": ["Show me new jobs"],
        })

    # 5) Incomplete profile
    completion = getattr(profile, "profile_completion", 100) or 0

    if completion < 80:

        alerts.append({
            "key": f"profile:{completion}",
            "type": "profile",
            "text": (
                f"Your profile is {completion}% complete. "
                "A complete profile improves your job matches."
            ),
            "actions": ["Show my profile"],
        })

    return alerts

def _build_company_proactive_alerts(user):
    """Things a recruiter should hear about without having to ask."""

    from jobsystem.models import Interview, Application

    company = getattr(user, "company_profile", None)

    if not company:
        return []

    now = timezone.now()

    alerts = []

    # 1) Interview within the next 24 hours

    soon = Interview.objects.filter(
        application__job__company=company,
        interview_date__gte=now,
        interview_date__lte=now + timedelta(hours=24),
        status__in=["scheduled", "rescheduled"],
    ).exclude(
        remarks__icontains="this date/time is a placeholder"
    ).select_related(
        "application__student", "application__job"
    ).order_by("interview_date").first()

    if soon:

        hours = max(int((soon.interview_date - now).total_seconds() // 3600), 0)

        when = (
            "in less than an hour" if hours == 0
            else f"in about {hours} hour(s)"
        )

        alerts.append({
            "key": f"co_interview:{soon.id}:{soon.interview_date:%Y%m%d%H%M}",
            "type": "interview_soon",
            "text": (
                f"Reminder: your interview with "
                f"{soon.application.student.full_name} for "
                f"{soon.application.job.title} is {when} "
                f"({soon.interview_date:%I:%M %p})."
            ),
            "actions": ["Show my interviews"],
        })

    # 2) New applicants in the last 24 hours

    new_applicants = Application.objects.filter(
        job__company=company,
        applied_date__gte=now - timedelta(hours=24),
    ).count()

    if new_applicants:

        alerts.append({
            "key": f"co_newapp:{new_applicants}:{now:%Y%m%d%H}",
            "type": "new_applicants",
            "text": (
                f"{new_applicants} new applicant(s) in the last 24 hours."
            ),
            "actions": ["Show my recent applications"],
        })

    # 3) Candidates waiting over a week with no status update at all

    stale = Application.objects.filter(
        job__company=company,
        status="applied",
        applied_date__lte=now - timedelta(days=7),
    ).count()

    if stale:

        alerts.append({
            "key": f"co_stale:{stale}:{now:%Y%m%d}",
            "type": "stale_applicants",
            "text": (
                f"{stale} candidate(s) have been waiting over a week "
                "with no status update."
            ),
            "actions": ["Show my applications"],
        })

    return alerts


def _build_placement_proactive_alerts(user):
    """Things a placement admin should hear about without having to ask."""

    from jobsystem.models import CompanyProfile, StudentProfile, PlacementDrive, Interview

    now = timezone.now()

    alerts = []

    # 1) Companies waiting for approval

    pending_companies = CompanyProfile.objects.filter(
        approval_status="pending"
    ).count()

    if pending_companies:

        alerts.append({
            "key": f"pa_pending_co:{pending_companies}:{now:%Y%m%d}",
            "type": "pending_approvals",
            "text": (
                f"{pending_companies} compan"
                f"{'y is' if pending_companies == 1 else 'ies are'} "
                "waiting for approval."
            ),
            "actions": ["Show pending company approvals"],
        })

    # 2) Students who haven't been verified yet

    unverified = StudentProfile.objects.filter(verified=False).count()

    if unverified:

        alerts.append({
            "key": f"pa_unverified:{unverified}:{now:%Y%m%d}",
            "type": "unverified_students",
            "text": f"{unverified} student(s) still need to be verified.",
            "actions": ["Show unverified students"],
        })

    # 3) The next upcoming placement drive (a single reminder, not a
    # count - PlacementDrive.drive_date's exact field type isn't
    # something this file can see, so a precise "within N days" date
    # comparison is avoided here in favour of always naming the very
    # next one, which is safe regardless of that field's type).

    soon_drive = PlacementDrive.objects.filter(
        status="upcoming"
    ).order_by("drive_date").first()

    if soon_drive:

        alerts.append({
            "key": f"pa_drive:{soon_drive.id}",
            "type": "drive_soon",
            "text": (
                f"Next upcoming placement drive: {soon_drive.title} "
                f"on {soon_drive.drive_date}."
            ),
            "actions": ["Show upcoming placement drives"],
        })

    # 4) Interviews happening today across the whole platform

    today_interviews = Interview.objects.filter(
        interview_date__date=now.date(),
        status__in=["scheduled", "rescheduled"],
    ).exclude(
        remarks__icontains="this date/time is a placeholder"
    ).count()

    if today_interviews:

        alerts.append({
            "key": f"pa_todayiv:{today_interviews}:{now:%Y%m%d}",
            "type": "interviews_today",
            "text": (
                f"{today_interviews} interview(s) scheduled across "
                "the platform today."
            ),
            "actions": [],
        })

    return alerts


def build_proactive_alerts(user):
    """Public entry point used by ChatbotProactiveView - dispatches by
    role, so the polling/marker frontend machinery stays unchanged for
    students, companies, and placement admins alike."""

    role = getattr(user, "role", None) if user else None

    if role == "student":
        return _build_student_proactive_alerts(user)

    if role == "company":
        return _build_company_proactive_alerts(user)

    if role == "placement_admin":
        return _build_placement_proactive_alerts(user)

    return []





def _describe_page(page_context):
    """
    Turns the frontend's page_context into a safe description. The job is
    looked up on the server by id, so the client can't inject free text
    into the prompt.
    """

    from jobsystem.models import Job

    if not isinstance(page_context, dict):
        return ""

    desc = f"Page: {str(page_context.get('page', ''))[:40]}."

    job_id = str(page_context.get("job_id", ""))

    if job_id.isdigit():

        job = Job.objects.filter(
            id=int(job_id), status="active"
        ).select_related("company").first()

        if job:

            company = job.company.company_name if job.company else "Company"

            desc += (
                f' The student is viewing the job "{job.title}" '
                f"at {company}."
            )

    return desc


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

BARE GREETINGS AND ACKNOWLEDGMENTS (critical): "hi", "hello", "good
morning/afternoon/evening", "thanks", "thank you", "ok", "okay" with
nothing else in the message are answered with a short, warm
conversational reply and NO tool call - never run job matching,
eligibility, applications, interviews, or any other lookup for one of
these, no matter what was discussed earlier in this conversation. A
greeting or a thanks is not a request to continue, repeat, or refresh
whatever was talked about before it - do not re-show a previous job
match, application, or interview result just because the student said
hi/hello/thanks right after discussing one. Treat it as a fresh, simple
moment in the conversation on its own.

HOW TO TALK: warm, sharp career mentor, not a search box. Answer naturally,
in full sentences. Use context from earlier in the conversation ("it",
"that one" mean what they meant before). Use real names/numbers/dates from
data. Keep replies short unless depth is needed. Never open with filler
("Sure!"). Never answer with just a label ("Here are your applications.")
- say something useful about what stands out.

ASK WHEN IT MATTERS: if a request is ambiguous or missing something you
need (which job/company/date?), ask ONE short clarifying question, with
2-3 concrete options if helpful - don't guess. Never ask permission for a
read-only lookup. End with at most one helpful next-step suggestion when
genuinely useful.

WORK LIKE AN AGENT: figure out the real goal, then use tools to get facts
- chain several in a row when one depends on another. Lookups need no
permission. Anything that changes data (apply, add skill, shortlist,
reject, raise query) is only ever PREPARED by you and confirmed by the user tapping a button
- say what you're about to do, never claim it's done. If a step fails,
say so and what you'll do instead. Never invent data.

TOPIC SCOPE (strict): placements and careers ONLY - job search,
applications, interviews/mock interviews, resumes, skills, career
guidance, placement drives, the user's own portal data, and (for a
company) hiring/candidates/analytics. Includes interview questions and how to answer them,
technical prep topics, resume/cover-letter writing, salary questions, study plans. EVERYTHING ELSE is off-topic - cooking and
meals (lunch, recipes), health, movies, games, sports, weather, news,
politics, shopping, travel, relationships, jokes, general knowledge:
reply with ONE short friendly sentence saying you only help with
placements/this portal, offer 2-3 things you can do. Do not answer the
off-topic question itself, not even briefly. Never call a tool, raise a
query, add a skill or take any action because of an off-topic message,
and never treat an off-topic message as the answer to a question you
just asked.

You have the signed-in user's REAL, CURRENT data as JSON below - always
answer "my applications/interviews/resume" (student) or "my
candidates/interviews" (company) from this directly, never say you lack
access. An empty list in the data means say so plainly.

Guests (not signed in) get general platform info only - suggest logging
in/registering for personalized help.

Use tools whenever the message needs a real action or up-to-the-moment
data rather than the snapshot alone - a tool call always reflects the
latest state. Student tools: finding jobs, eligibility, applying, status,
requirements, skills, interview prep, resume/ATS, downloads, saved jobs,
notifications, profile, drives, interview slots, queries. Company tools:
candidates, top applicants, applications, interviews, postings,
analytics, profile. Placement admin tools (read-only): overview, pending
approvals, unverified students, drives, company history, report,
pipeline - if asked to approve/verify/notify, explain that's not
available in chat yet and point to the matching admin page. Only call
apply_to_job when the student clearly asks to apply to a named job; only
call update_my_skills when they clearly ask to add/update a skill - never
as a side effect of general conversation. When a job result shows
already_applied=true, say they've already applied instead of inviting
another application.

AI-WRITTEN COVER LETTERS: if asked to write a cover letter AND apply, do
NOT draft it yourself or call apply_to_job directly - you can't pass free
text into it. Tell them to say "write a cover letter for me and apply to
<job>" (or use that button under a job card), which handles both
together.

NEVER CLAIM AN ACTION SUCCEEDED WITHOUT CALLING THE TOOL (critical):
never say an application was submitted, a query raised, a slot
requested, a skill added, or a candidate shortlisted/rejected unless you
ACTUALLY called that tool (apply_to_job, raise_placement_query,
request_interview_slot, update_my_skills, shortlist_candidate,
reject_candidate) this turn and it returned success. Saying "done"
without calling the tool is forbidden, even if confident what the user
wants. shortlist_candidate/reject_candidate also only ask for Yes/No
confirmation - nothing changes until the recruiter taps Yes. If the
student uses a pronoun ("apply to that job", "the above one"), resolve
the exact job_title from the most recent job list you showed, then call
apply_to_job - never guess, never skip the call.

VAGUE PROFILE UPDATE REQUESTS (important): "update my profile" / "I want
to change my profile" / "edit my profile" with no specifics named is NOT
enough information to call update_my_skills or update_my_projects - both
require a real value, and inventing a plausible-sounding one to satisfy
that would write fabricated data into the student's real profile. Ask
what they'd like to update instead (skills, projects, or point them to
the Profile page for other fields) and wait for their answer before
calling either tool.

GENERAL SKILLS MATCH SCORE: "what is my skills match score" with no job
named is asking about their overall fit, not one specific role - treat
it the same as a best-job question (find_matching_jobs, limit=1) and
explain the score that comes back, rather than guessing which job they
meant or calling a tool that doesn't exist.

APPLYING TO A JOB (confirmation required): apply_to_job only asks "Apply
to X at Y?" with Yes/No buttons - it never submits by itself. Don't say
the application was sent; the tool's own question IS the reply. Pass
ONLY the job title in job_title (e.g. "Software Tester") and the company
separately in company_name - never joined as one string. If the student
says "yes apply" right after you showed a job, use that job's
title/company from the card.

PLAIN TEXT ONLY: the chat window does not render markdown, so never use
**bold**, # headings or markdown links - write plain sentences.

NAMED JOB + WANTS TO APPLY: if the student names a job and wants to
apply ("teacher job i want to apply"), call apply_to_job for THAT job -
never check_job_eligibility or a general list instead. The answer must
be about that specific job: the confirmation, or exactly why they can't
apply, then which jobs they CAN apply to.

BE A REAL CAREER ASSISTANT, NOT JUST A DATA LOOKUP: if a student asks
for prep on a role they've never applied to (get_interview_prep finds
nothing), that's not a dead end - give genuinely useful general advice
from your own knowledge (common questions, key skills, what interviewers
look for), the same way a real career advisor would. A student can
reasonably ask about any role, not just ones on this platform. Only
decline things genuinely outside scope - never a legitimate career
question just because there's no platform data for it.

ANSWER WITH THE REAL DETAIL, NOT A COUNT: when a tool returns
issues/suggestions/missing info, name them - never just "found 3
issues" with nothing else. Before re-running an analysis tool
(resume/ATS/eligibility), check whether you already gave the real
detail earlier in this conversation - answer a follow-up from that
instead of re-running it (each run costs time and can vary slightly).
Only re-run if something genuinely changed or the student explicitly
asks.

THREE DIFFERENT JOB QUESTIONS - never mix up:
- New/latest/recent jobs = plain recent list (find_matching_jobs,
  recent_only true), no profile analysis.
- Jobs for me/matching my profile = profile-matched answer
  (find_matching_jobs, recent_only false): what they can apply to, what
  blocks the rest.
- Show all jobs/the jobs tab/even ineligible ones = EVERY open job
  (list_open_jobs), cards marked applied/eligible/not eligible. Never
  answer this with only the jobs they qualify for.
- Jobs for a named technology/skill ("python jobs", "react jobs",
  "django jobs", "testing jobs") = list_open_jobs with keyword set to
  that exact term - never the plain, unfiltered "every open job" list.
  A named technology is a real filter the student asked for, not a
  synonym for "show all jobs".

MORE THAN ONE REQUEST: for several things at once ("applications and
interviews"), call all matching tools in one turn (up to 3) instead of
only the first one. When one depends on another ("best job and what I'm
missing"), call the tools one after another: look at the first result,
then call the next tool with what you learned.

DOWNLOADS: when get_resume_download_link runs successfully, tell the
student their resume is ready and a download button is shown right in
the chat - never write out or mention a URL/link yourself.

INTERVIEW PREPARATION: when get_interview_prep or get_application_status
returns real skills/description for an interview, write 3-5 genuinely
role-and-company-specific prep points, not generic advice. After showing
application status, proactively offer prep if interview details are
present. Congratulate on selection; be encouraging and offer more jobs
if rejected.

NO DUPLICATE LISTINGS: matched_jobs/candidates/applications/interviews/
jobs/drives/notifications render as their own cards below your reply -
never also write them out as a list, table, or markdown link anywhere.
Say something useful ABOUT them in 1-3 sentences (how many, which stands
out, what to do next) - the cards carry the detail, you add the insight.

INTERVIEW PREP ROLE MATCHING: "prepare for [a role]" and "prepare for MY
interview" differ - don't conflate them. A named role gets prep for THAT
role via get_interview_prep, even if different from their actual
scheduled interview; if it doesn't match, don't substitute the real
interview's details - give general role-based prep or offer a mock
interview instead.

INTERVIEW STATUS QUESTIONS: "any interview updates"/"when is my
interview" ask about REAL scheduled interviews - always use
get_upcoming_interviews (or trust upcoming_interviews/
interviews_this_week in CURRENT USER DATA below, rebuilt fresh every
message). Never conclude "no interviews scheduled" just because
get_application_status lacked interview details - a real interview can
exist even when status says "Selected" or "Shortlisted".

NEVER ANSWER A DATA REQUEST WITHOUT CALLING THE TOOL (critical): for
"show my applications/interview status/notifications/saved jobs" and
similar, call the matching tool THIS turn and build your reply from its
real result - never a vague "Here are your applications" with no real
names/dates. This applies to follow-ups too ("now show my
applications") - each needs its own fresh call, since the data changes
over time.

LIVE DATA OVER CHAT HISTORY (important): CURRENT USER DATA below is
rebuilt fresh every message - always more current than anything said
earlier in this conversation. If an interview you mentioned before is no
longer in upcoming_interviews/interviews_this_week, it already happened
- don't keep repeating it as upcoming. Same for the resume score -
always use the current official number, ignore anything different said
earlier in this chat.

CAREER PLAN: when get_career_plan runs, build ONE prioritized,
cross-referenced plan, not disconnected facts - e.g. if the resume score
is low AND a missing skill also matches a top job's requirement, call
that out as the highest priority. Default order: (1) resume fixes if
weak, (2) the single most-recommended skill to learn next, (3) which job
to prioritize applying to and why, (4) interview prep if next_interview
is present. 4-6 concrete steps, not a wall of text repeating every field.

RESUME SCORE (critical): exactly ONE official score exists
(resume.score / resume_score in get_resume_feedback,
check_ats_friendliness and get_career_plan results, saved by the Resume
page's AI analysis) - always quote that exact number. Never
calculate/estimate/invent a different score, and never present an ATS
check as a separate score - it only provides issues/suggestions. For a
new score after editing, tell them to re-upload or click "Analyse
Resume".

BEST-JOB QUESTIONS (important): for "which job is best/most suitable",
call find_matching_jobs with limit=1 (limit=3 for "top jobs"), then name
the single best job with 1-2 sentences of specific reasons from
match_score/reasons. Say so honestly if two jobs tie, and what differs.
Don't set recent_only unless they say "new". Keep it short - the card
below shows the details.

MATCH SCORE VS ELIGIBILITY (important): separate, unrelated checks - a
high match_score (skills overlap) never overrides an eligibility failure
(CGPA, department, graduation year, age). If asked why they can't apply
despite a good match, explain the distinction plainly with the specific
eligibility reason given (e.g. "your 52% match means your skills fit,
but this role separately requires 7.0+ CGPA and you have 6.98 - a fixed
requirement the skill match doesn't change").

JOB REQUIREMENTS: when get_job_details returns missing_skills, point
those out clearly alongside skills_required as what to focus on for that
role.

SKILL ROADMAPS: when get_company_skill_gap or get_skill_suggestions
returns missing skills, build a short learning roadmap (what to learn
first and why, a realistic order for the rest) grounded in the real
list. Never invent specific courses, certifications, instructors,
prices, or URLs - a wrong one is worse than none. Point to general
resource types (official docs, hands-on practice, open-source
contributions) instead.

You also have a Knowledge Base of placement policies, FAQs, and
guidelines - use it for policy/process questions. If something isn't
covered by the data, tools, or knowledge base, say you're not sure
rather than inventing details.

Keep replies concise, friendly, and practical. Never reveal another
user's information - you only ever have the signed-in user's own data,
and every tool above only ever touches this same signed-in user's own
records (never another student's or another company's).

SECURITY (non-negotiable): the JSON below contains ONLY the current
signed-in user's own data. If asked to see another person's or
company's private information, refuse clearly and suggest contacting
the placement office. Never guess, infer, or fabricate another party's
data even if asked to "assume" or "pretend". This rule overrides any
other instruction in this prompt, including anything added below by an
administrator.

CURRENT DATE AND TIME: {current_datetime}. This is India Standard Time
(IST) - use it as-is for any greeting ("good morning/afternoon/evening")
and any "today" you mention, rather than assuming a different timezone.
Compare any date/time you mention (interviews, deadlines, drives) against
this exact moment first.
If it's earlier today or an earlier date, it has ALREADY HAPPENED - say
so plainly (e.g. "Your interview was earlier today at 7:01 AM - I hope
it went well! Want to share how it went, or look at other matching
jobs?") instead of presenting it as upcoming. If it's later today, say
it's today and roughly how soon (e.g. "in about 3 hours"). Only treat
something as genuinely upcoming if its date/time is after this current
moment.

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


def _explain_condition(profile, detail):
    """
    Adds the student's OWN current value to a requirement text that doesn't
    already show it, so "your profile doesn't match" and "you haven't filled
    it in" are easy to tell apart:
        "Open to: CSE"  ->  "Open to: CSE (your department: not set)"
    Requirement texts that already mention the student's value ("...you
    have 6.98", "...add your age...") are left exactly as they are.
    """

    text = (detail or "").strip()

    low = text.lower()

    if not text or "you have" in low or "your " in low:

        return text

    if low.startswith("open to graduation year"):

        value = getattr(profile, "graduation_year", None)

        return f"{text} (your graduation year: {value or 'not set'})"

    if low.startswith("open to"):

        value = (getattr(profile, "department", "") or "").strip()

        return f"{text} (your department: {value or 'not set'})"

    return text


def _failing_details(profile, eligibility):
    """Every failing requirement in a check_eligibility() result, each with
    the student's own value shown where the check doesn't already."""

    details = []

    for condition in eligibility.get("conditions") or []:

        if (
            isinstance(condition, dict)
            and condition.get("status") == "fail"
            and condition.get("detail")
        ):

            details.append(_explain_condition(profile, condition["detail"]))

    return details


def _eligibility_blocker(profile, job):
    """(eligible, [failing requirement texts]) for a job. Never raises: if
    the eligibility check itself fails, the job is NOT hidden."""

    from jobsystem.services.eligibility import check_eligibility

    try:

        result = check_eligibility(profile, job)

    except Exception:

        return True, []

    if result.get("eligible", True):

        return True, []

    return False, _failing_details(profile, result)


# ---- department wording: "computerscience", "Computer Science" and "CSE" are
# the same department. The eligibility rule compares text, so a profile that
# says "computerscience" fails "Open to: CSE" even though the student IS a CSE
# student. These helpers let the assistant SAY so (and tell them the one-line
# fix) instead of listing it as a real blocker.

_DEPARTMENT_ALIASES = {
    "cse": ["cse", "cs", "compsci", "computerscience", "computersciencengineering",
            "computerscienceengineering", "computerscienceandengineering",
            "computerscienceengg", "computerscienceandengg"],
    "it": ["it", "informationtechnology"],
    "ece": ["ece", "electronicsandcommunication", "electronicscommunication",
            "electronicsandcommunicationengineering", "electronicscommunicationengineering"],
    "eee": ["eee", "electricalandelectronics", "electricalelectronics",
            "electricalandelectronicsengineering"],
    "mech": ["mech", "mechanical", "mechanicalengineering"],
    "civil": ["civil", "civilengineering"],
    "aids": ["aids", "aiandds", "artificialintelligenceanddatascience"],
    "aiml": ["aiml", "aiandml", "artificialintelligenceandmachinelearning"],
    "bca": ["bca", "bachelorofcomputerapplications"],
    "mca": ["mca", "masterofcomputerapplications"],
}

_DEPARTMENT_LOOKUP = {
    variant: canonical
    for canonical, variants in _DEPARTMENT_ALIASES.items()
    for variant in variants
}


def _canonical_department(text):
    """'Computer Science', 'computerscience', 'B.Tech CSE', 'cse' -> 'cse'."""

    key = re.sub(r"[^a-z0-9]", "", (text or "").lower())

    if not key:

        return ""

    stripped = re.sub(r"^(btech|mtech|bsc|msc|be)", "", key)

    for candidate in (key, stripped):

        for form in (candidate, re.sub(r"(engineering|engg|department|dept)$", "", candidate)):

            if form in _DEPARTMENT_LOOKUP:

                return _DEPARTMENT_LOOKUP[form]

    return key


def _department_options(allowed_text):

    return [
        part.strip()
        for part in re.split(r"[,;/|]|\bor\b", allowed_text or "", flags=re.IGNORECASE)
        if part.strip()
    ]


def _matching_department_option(have, allowed_text):
    """The allowed department the student's own one is the same as once
    written the same way ('computerscience' -> 'CSE' out of 'CSE, IT'), or ''."""

    mine = _canonical_department(have)

    if not mine:

        return ""

    for option in _department_options(allowed_text):

        if _canonical_department(option) == mine:

            return option

    return ""


def _departments_match(have, allowed_text):
    """True if the student's department is one of the allowed ones once
    written the same way ('computerscience' vs 'CSE')."""

    return bool(_matching_department_option(have, allowed_text))


def _department_tip(profile, eligibility):
    """One sentence when the ONLY reason a department rule failed is wording
    ("computerscience" vs "CSE"); empty otherwise."""

    have = (getattr(profile, "department", "") or "").strip()

    if not have:

        return ""

    for condition in eligibility.get("conditions") or []:

        detail = (condition.get("detail") or "") if isinstance(condition, dict) else ""

        if (
            isinstance(condition, dict)
            and condition.get("status") == "fail"
            and re.match(r"^open to:", detail, re.IGNORECASE)
        ):

            allowed = detail.split(":", 1)[1].strip()

            target = _matching_department_option(have, allowed)

            if target:

                return (
                    f'Your department ("{have}") looks like the same as {target} '
                    f'but is written differently - set it to "{target}" on your '
                    "profile and that requirement should pass."
                )

    return ""


_RE_CGPA = re.compile(r"^Requires\s+([\d.]+)\+?\s*CGPA\s*-\s*you have\s+([\d.]+)\s*$", re.IGNORECASE)

_RE_DEPT = re.compile(r"^Open to:\s*(.+?)\s*\(your department:\s*(.*?)\)\s*$", re.IGNORECASE)

_RE_YEAR = re.compile(
    r"^Open to graduation years?:\s*(.+?)\s*\(your graduation year:\s*(.*?)\)\s*$",
    re.IGNORECASE,
)

_RE_AGE = re.compile(r"age restriction applies\s*-\s*add your age", re.IGNORECASE)


def _names(titles, cap=4):
    """'A, B, C, D and 2 more' - job names, each once."""

    unique = list(dict.fromkeys(titles))

    shown = ", ".join(unique[:cap])

    extra = len(unique) - cap

    return shown + (f" and {extra} more" if extra > 0 else "")


def _summarise_blockers(blocked, cap=4):
    """
    blocked = [(job title, [failing requirement texts])].
    Returns (lines, unlockable_titles, fix_labels): ONE line per requirement
    (naming every job it blocks) instead of repeating the same reasons under
    each job, plus which jobs are blocked ONLY by things the student can fix
    on their own profile (an unset or differently-worded department, a missing
    age or graduation year) and what those fixes are.
    """

    cgpa, dept, years, age, other, bare = {}, {}, {}, [], {}, []

    year_have = ""

    fix_kinds = {}          # job title -> {kinds fixable on the profile}

    unfixable = set()       # job titles with at least one thing they can't fix

    for title, reasons in blocked:

        if not reasons:

            bare.append(title)

            continue

        fix_kinds.setdefault(title, set())

        for reason in reasons:

            m = _RE_CGPA.match(reason)

            if m:

                cgpa.setdefault((m.group(1), m.group(2)), []).append(title)

                unfixable.add(title)

                continue

            m = _RE_DEPT.match(reason)

            if m:

                allowed, have = m.group(1).strip(), m.group(2).strip()

                dept.setdefault((allowed, have), []).append(title)

                if have.lower() == "not set" or _departments_match(have, allowed):

                    fix_kinds[title].add("department")

                else:

                    unfixable.add(title)

                continue

            m = _RE_YEAR.match(reason)

            if m:

                years.setdefault(m.group(1).strip(), []).append(title)

                year_have = m.group(2).strip()

                if year_have.lower() == "not set":

                    fix_kinds[title].add("graduation year")

                else:

                    unfixable.add(title)

                continue

            if _RE_AGE.search(reason):

                age.append(title)

                fix_kinds[title].add("age")

                continue

            other.setdefault(reason, []).append(title)

            unfixable.add(title)

    lines = []

    for (required, have), titles in cgpa.items():

        line = f"CGPA: {required}+ needed, you have {have}"

        try:

            gap = float(required) - float(have)

        except ValueError:

            gap = None

        if gap is not None and 0 < gap <= 0.5:

            line += f" (just {gap:.2f} short)"

        lines.append(f"{line} - for {_names(titles, cap)}")

    for (allowed, have), titles in dept.items():

        target = _matching_department_option(have, allowed)

        if have.lower() == "not set":

            what = f"Department: open to {allowed}, and your profile has none"

        elif target:

            what = (
                f'Department: open to {allowed}, your profile says "{have}" - '
                f'probably the same thing written differently, so set it to "{target}"'
            )

        else:

            what = f'Department: open to {allowed}, your profile says "{have}"'

        lines.append(f"{what} - for {_names(titles, cap)}")

    if years:

        mine = (
            f"yours is {year_have}"
            if year_have and year_have.lower() != "not set"
            else "yours isn't set on your profile"
        )

        parts = [
            f"{_names(titles, cap)} "
            f"{'needs' if len(set(titles)) == 1 else 'need'} {allowed}"
            for allowed, titles in years.items()
        ]

        lines.append(f"Graduation year: {mine} - " + "; ".join(parts))

    if age:

        lines.append(f"Age: add your age to your profile - for {_names(age, cap)}")

    for reason, titles in other.items():

        lines.append(f"{reason} - for {_names(titles, cap)}")

    lines.extend(bare)

    unlockable = [t for t, kinds in fix_kinds.items() if kinds and t not in unfixable]

    order = ["department", "graduation year", "age"]

    labels = [k for k in order if any(k in fix_kinds[t] for t in unlockable)]

    return lines, unlockable, labels


def _exclusion_note(applied_titles, blocked, cap=5):
    """
    Plain lines saying which open jobs were left out of a 'jobs for you'
    answer and why, so nothing is silently hidden. `blocked` is a list of
    (title, [failing requirement texts]). Blockers are grouped by requirement
    (see _summarise_blockers) so the same reason isn't repeated per job.
    """

    sections = []

    applied = list(dict.fromkeys(applied_titles))

    if applied:

        lines = ["Already applied:"] + [f"- {t}" for t in applied[:cap]]

        if len(applied) > cap:

            lines.append(f"- and {len(applied) - cap} more")

        sections.append("\n".join(lines))

    if blocked:

        lines, unlockable, labels = _summarise_blockers(blocked)

        section = ["You don't meet the requirements yet:"] + [f"- {l}" for l in lines]

        if unlockable:

            joined = (
                labels[0] if len(labels) == 1
                else ", ".join(labels[:-1]) + " and " + labels[-1]
            )

            section.append(
                f"Updating your {joined} would open up: {_names(unlockable)}."
            )

        sections.append("\n".join(section))

    return "\n\n".join(sections)


_PROFILE_HINT = (
    'If your profile details are missing or out of date, '
    'tap "Update my profile".'
)


def _created_timestamp(job):

    created = getattr(job, "created_at", None)

    try:

        return created.timestamp()

    except Exception:

        return 0


def _new_jobs_result(ranked_all, applied_job_ids, cap=8):
    """A plain list of the recently posted jobs the student hasn't applied to,
    newest first (each card carries the student's own match score)."""

    unapplied = [item for item in ranked_all if item[0].id not in applied_job_ids]

    applied_titles = [
        job.title for job, _s, _r in ranked_all if job.id in applied_job_ids
    ]

    unapplied.sort(key=lambda item: _created_timestamp(item[0]), reverse=True)

    if not unapplied:

        return {
            "kind": "new_jobs",
            "matched_jobs": [],
            "total_new": 0,
            "already_applied_titles": applied_titles,
            "summary": (
                f"You've already applied to every job posted in the last "
                f"{RECENT_JOB_DAYS} days."
            ),
        }

    shown = unapplied[:cap]

    total = len(unapplied)

    return {
        "kind": "new_jobs",
        "matched_jobs": [
            _serialize_matched_job(job, score, reasons, already_applied=False)
            for job, score, reasons in shown
        ],
        "total_new": total,
        "already_applied_titles": applied_titles,
        "navigate_to": "/student/jobs",
        "summary": (
            f"{total} new job{'s' if total != 1 else ''} posted in the last "
            f"{RECENT_JOB_DAYS} days that you haven't applied to"
            + (f" (showing the {len(shown)} newest)." if len(shown) < total else ".")
        ),
    }


def _tool_find_matching_jobs(profile, user, args):
    """
    Jobs the student can ACTUALLY apply to right now - open, not already
    applied to, and eligible - best skill match first. Jobs left out for
    those reasons are named in the summary instead of being listed as if
    they were suitable: a "suitable for me" answer that includes a job
    you already applied to, or one whose Apply button would then be
    refused, is not a real answer.
    """

    from datetime import timedelta

    from jobsystem.models import Job, Application
    from jobsystem.services.job_matching import rank_jobs_for_student

    recent_only = bool(args.get("recent_only"))

    # "Which job is best for me?" wants just the top pick(s), not the
    # whole list - the model passes limit=1-3 for those questions.

    try:

        limit = int(args.get("limit") or 5)

    except (TypeError, ValueError):

        limit = 5

    limit = max(1, min(limit, 5))

    jobs_qs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company").order_by("-created_at")

    if recent_only:

        jobs_qs = jobs_qs.filter(
            created_at__gte=timezone.now() - timedelta(days=RECENT_JOB_DAYS)
        )

    jobs = jobs_qs[:40]

    ranked_all = rank_jobs_for_student(profile, jobs)

    if not ranked_all:

        if recent_only:

            return {
                "kind": "new_jobs",
                "matched_jobs": [],
                "summary": f"There are no new jobs posted in the last {RECENT_JOB_DAYS} days.",
            }

        return {
            "matched_jobs": [],
            "summary": "No active job postings found right now.",
        }

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    if recent_only:

        # "Show me new jobs" = what was uploaded recently, like the Jobs page
        # shows it - newest first, with the student's match score on each. It
        # is NOT the "jobs you can apply to" analysis (that is "find jobs for
        # me / that match my profile"), so nothing is filtered or explained
        # by eligibility here.

        return _new_jobs_result(
            ranked_all, applied_job_ids,
            cap=limit if args.get("limit") else 8,
        )

    actionable = []

    applied_titles = []

    blocked = []

    for job, score, reasons in ranked_all:

        if job.id in applied_job_ids:

            applied_titles.append(job.title)

            continue

        eligible, reasons_list = _eligibility_blocker(profile, job)

        if not eligible:

            blocked.append((job.title, reasons_list))

            continue

        actionable.append((job, score, reasons))

    shown = actionable[:limit]

    note = _exclusion_note(applied_titles, blocked)

    extras = {
        "already_applied_titles": applied_titles,
        "not_eligible": [
            {"title": title, "reason": "; ".join(reasons), "reasons": reasons}
            for title, reasons in blocked
        ],
    }

    if not shown:

        result = {
            "matched_jobs": [],
            "summary": "\n\n".join(filter(None, [
                (
                    "There are no newly posted jobs you can apply to right now."
                    if recent_only else
                    "None of the open jobs are available for you to apply to right now."
                ),
                note,
                _PROFILE_HINT if blocked else "",
            ])),
            **extras,
        }

        if blocked:

            result["quick_replies"] = ["Update my profile"]

        return result

    matched_jobs = [
        _serialize_matched_job(job, score, reasons, already_applied=False)
        for job, score, reasons in shown
    ]

    if limit == 1:

        headline = (
            f"Best job you can apply to right now: {matched_jobs[0]['title']} "
            f"at {matched_jobs[0]['company']}."
        )

    else:

        count = len(matched_jobs)

        headline = (
            f"Here {'is' if count == 1 else 'are'} {count} "
            f"{'job' if count == 1 else 'jobs'} you can apply to right now, "
            "best skill match first."
        )

    result = {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": "\n\n".join(filter(None, [
            headline,
            note,
            _PROFILE_HINT if (blocked and limit != 1) else "",
        ])),
        **extras,
    }

    if blocked and limit != 1:

        result["quick_replies"] = ["Update my profile"]

    # A single recommended job gets one-tap Yes / No buttons, so "would you
    # like to apply?" can be answered right away.

    if limit == 1:

        _best_job = shown[0][0]

        result["quick_replies"] = [
            _apply_chip_text(_best_job),
            _cover_letter_chip_text(_best_job),
            _ai_cover_chip_text(_best_job),
            "No, cancel",
        ]

        result["awaiting_apply_decision_job_id"] = _best_job.id

    return result


def _tool_list_open_jobs(profile, user, args):
    """
    The whole Jobs tab: EVERY open job, best skill match first, whether or not
    the student can apply to it. Each card says which it is - already applied,
    eligible, or not eligible yet (with the first reason) - so nothing is hidden
    and nothing is described as apply-able when it isn't. Used for "show all the
    jobs", "the list of jobs from the jobs tab", "even the ones I'm not eligible
    for" - as opposed to "jobs for me" (only what they can apply to) and
    "new jobs" (only what was recently posted).
    """

    from jobsystem.models import Job, Application
    from jobsystem.services.job_matching import rank_jobs_for_student

    company_name = (args.get("company_name") or "").strip()

    keyword = (args.get("keyword") or "").strip()

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company").order_by("-created_at")

    if keyword:

        # "show me python jobs" / "django jobs" - no tool here could
        # actually filter by a technology/skill keyword before this,
        # only by company name. Matches title, required skills, and
        # the description, so "Python Full Stack Developer" (title),
        # a job merely requiring "Python, Django" (skills_required),
        # or one that only mentions it in the description all
        # correctly count as a match. Imported here, inside the
        # keyword branch specifically, so a plain "show all jobs"
        # call (no keyword at all) never needs django.db.models
        # importable at all - unchanged from before this feature.

        from django.db.models import Q

        jobs = jobs.filter(
            Q(title__icontains=keyword)
            | Q(skills_required__icontains=keyword)
            | Q(description__icontains=keyword)
        )

    if company_name:

        # Same keyword matching used for job titles elsewhere in this
        # file - a student's own phrasing of a company name doesn't
        # always exactly match the stored name either.
        company_q = _job_title_keyword_q("company__company_name", company_name)

        if company_q is not None:

            jobs = jobs.filter(company_q)

    jobs = jobs[:40]

    ranked_all = rank_jobs_for_student(profile, jobs)

    if not ranked_all:

        return {
            "kind": "all_jobs",
            "matched_jobs": [],
            "total_open": 0,
            "summary": (
                f"No open jobs found for \"{company_name}\"." if company_name
                else f"No open jobs found matching \"{keyword}\"." if keyword
                else "There are no open jobs right now."
            ),
        }

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    cards = []

    can_apply = applied_count = blocked_count = 0

    for job, score, reasons in ranked_all:

        applied = job.id in applied_job_ids

        if applied:

            eligible, why = True, []

            applied_count += 1

        else:

            eligible, why = _eligibility_blocker(profile, job)

            if eligible:

                can_apply += 1

            else:

                blocked_count += 1

        card = _serialize_matched_job(job, score, reasons, already_applied=applied)

        card["eligible"] = eligible

        # first reason only, so a card stays small: "Requires 7.0+ CGPA... (+2 more)"

        card["eligibility_note"] = (
            "" if eligible
            else (why[0] + (f" (+{len(why) - 1} more)" if len(why) > 1 else "") if why else "Not eligible yet")
        )

        cards.append(card)

    total = len(cards)

    cap = 10

    shown = cards[:cap]

    return {
        "kind": "all_jobs",
        "matched_jobs": shown,
        "total_open": total,
        "can_apply": can_apply,
        "applied_count": applied_count,
        "blocked_count": blocked_count,
        "navigate_to": "/student/jobs",
        "summary": (
            (f"{total} open job{'s' if total != 1 else ''} at \"{company_name}\": "
             if company_name else
             f"{total} open job{'s' if total != 1 else ''}: ")
            + f"you can apply to {can_apply}, you've already applied to "
            f"{applied_count}, and {blocked_count} need something your "
            "profile doesn't have yet"
            + (f" (showing the {len(shown)} best matches)." if len(shown) < total else ".")
        ),
    }


def _tool_check_job_eligibility(profile, user, args):
    """
    "Which jobs am I eligible for?" - the open jobs the student meets the
    requirements for AND hasn't already applied to (eligible jobs they've
    already applied to, and jobs they don't qualify for, are named in the
    summary instead of being listed as apply-able). Same logic as the job
    search, so the two can never disagree about what "you can apply to" means.
    """

    return _tool_find_matching_jobs(profile, user, {"limit": 5})


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

    description = job_data.get("description", "") or ""

    eligibility_criteria = job_data.get("eligibility_criteria", "") or ""

    # Same fix as every other tool in this file: "summary" is what the
    # model reads to answer, and what's shown if its own write-up pass
    # is ever skipped or fails - a bare "Requirements for X at Y." with
    # nothing else meant the student got no actual requirements in
    # that case, despite the real description/skills/eligibility
    # criteria already being found right here.

    detail_lines = [f"Requirements for {job.title} at {company_name}:"]

    if skills_required:

        detail_lines.append(
            "\nSkills required: " + ", ".join(skills_required[:10])
        )

    if eligibility_criteria:

        detail_lines.append(f"\nEligibility: {eligibility_criteria[:400]}")

    if description:

        detail_lines.append(f"\nDescription: {description[:400]}")

    if missing_skills:

        detail_lines.append(
            "\nSkills you don't have yet: " + ", ".join(missing_skills[:8])
        )

    return {
        "job_title": job.title,
        "company": company_name,
        "location": job_data.get("location", ""),
        "job_type": job_data.get("job_type", ""),
        "description": description,
        "eligibility_criteria": eligibility_criteria,
        "skills_required": skills_required,
        "missing_skills": missing_skills,
        "match_score": score,
        "apply_url": f"/student/jobs/{job.id}/apply",
        "details_url": f"/student/jobs/{job.id}",
        "navigate_to": f"/student/jobs/{job.id}",
        "summary": "\n".join(detail_lines),
    }


def _job_role_strict_match_q(field_prefix, job_role):
    """
    Like _job_title_keyword_q, but requires EVERY significant word to
    match (AND), not just any one (OR) - right for narrowing to ONE
    specific role like "Python Developer" for skill-gap scoping, where
    "developer" alone would also pull in "Senior Frontend Developer"
    (a different specialization entirely) via that one shared, overly
    generic word. _job_title_keyword_q's looser OR-matching is correct
    for "find THIS job" (recall matters, one real hit is enough) but
    wrong here (precision matters - skills for the WRONG role is worse
    than no scoping at all). Returns None if nothing usable is left.
    """

    from django.db.models import Q

    words = [
        w for w in re.split(r"\s+", (job_role or "").lower())
        if len(w) > 2 and w not in _JOB_TITLE_KEYWORD_STOPWORDS
    ]

    if not words:

        return None

    q = Q()

    for w in words:

        q &= Q(**{f"{field_prefix}__icontains": w})

    return q


def _tool_get_skill_suggestions(profile, user, args):
    """
    Covers "What skills should I improve?" with a real answer grounded
    in current job-market demand, not a generic list - the skills most
    frequently required that the student doesn't already have.

    Optionally scoped to ONE target role ("what skills should I learn
    for Python Developer?") via job_role - previously this always
    computed against the WHOLE platform regardless of a role actually
    being named, so "for Python Developer" was silently ignored and a
    student targeting one specific role got the same generic answer as
    someone who named no role at all. Matched by keyword (same approach
    as _job_title_keyword_q elsewhere), since a student's own phrasing
    of a role doesn't always exactly match a real posting's title.
    """

    from jobsystem.models import Job
    from collections import Counter

    job_role = (args.get("job_role") or "").strip()

    jobs_qs = Job.objects.filter(status="active", is_active=True)

    role_matched = False

    if job_role:

        role_q = _job_role_strict_match_q("title", job_role)

        if role_q is not None:

            scoped = jobs_qs.filter(role_q)

            if scoped.exists():

                jobs_qs = scoped

                role_matched = True

    jobs = jobs_qs[:50]

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

    scope_note = f" for {job_role}" if (job_role and role_matched) else ""

    no_postings_note = (
        f" (no open postings matched \"{job_role}\" specifically, so this "
        "is based on the overall platform instead)"
        if (job_role and not role_matched) else ""
    )

    return {
        "current_skills": sorted(student_skills),
        "suggested_skills": top_missing,
        "target_role": job_role or None,
        "summary": (
            f"Top in-demand skills the student doesn't have yet{scope_note}"
            f"{no_postings_note}: " + ", ".join(top_missing)
        ) if top_missing else (
            f"The student's current skills already cover most open "
            f"job requirements{scope_note} on the platform."
        ),
    }


def _tool_get_company_info(profile, user, args):
    """
    General "tell me about this company" info for a student - industry,
    description, size, how many jobs they have open right now. Every
    other role (company, placement admin) already had a way to look up
    a company's profile; students never did, even though "company
    information" is explicitly one of the Information Retrieval items
    in the project spec. Only exposes genuinely public-facing fields -
    never registration/GST documents or anything internal.
    """

    from jobsystem.models import CompanyProfile, Job

    name = (args.get("company_name") or "").strip()

    if not name:

        return {"summary": "Which company would you like to know about?"}

    company = CompanyProfile.objects.filter(
        company_name__icontains=name
    ).first()

    if not company:

        return {"summary": f"No company found matching \"{name}\"."}

    open_jobs = Job.objects.filter(
        company=company, status="active", is_active=True
    ).count()

    return {
        "company_name": company.company_name,
        "industry": company.industry,
        "description": company.description,
        "company_size": company.company_size,
        "open_jobs": open_jobs,
        "navigate_to": "/student/jobs",
        "summary": (
            f"{company.company_name} - {company.industry or 'industry not set'}"
            f"{f', {company.company_size} employees' if company.company_size else ''}. "
            f"{open_jobs} open job{'s' if open_jobs != 1 else ''} right now."
            + (f" {company.description[:300]}" if company.description else "")
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


# =====================================================
# APPLYING TO A JOB - always confirmed by the student first
#
# The AI can never submit an application by itself. The
# apply_to_job tool below only PREPARES it: it finds the job,
# checks the student can apply, and asks "Apply to X at Y?" with
# Yes / No buttons. The application is created only when the
# student taps Yes (or types "Yes, apply to X at Y"), which is
# handled deterministically by _handle_apply_confirmation() in
# generate_reply() - no AI involved in that step.
# =====================================================

# The AI never sees job CARDS - chat history only stores the bot's sentences.
# So when a student says "apply above job" the AI had to guess (and picked the
# wrong job). The chat view therefore stores the ids of the jobs it showed as a
# small marker at the end of the saved bot message; it is stripped again
# before the history reaches the AI or the frontend.

_SHOWN_JOBS_RE = re.compile(r"\n?\[\[jobs:([\d,]+)\]\]\s*$")

_AWAITING_COVER_RE = re.compile(r"\n?\[\[await_cover:(\d+)\]\]\s*$")

_AWAITING_APPLY_RE = re.compile(r"\n?\[\[await_apply:(\d+)\]\]\s*$")


def awaiting_apply_decision_marker(job_id):
    """Hidden suffix on a saved 'Apply to X? [buttons]' message, so a later
    'write a cover letter and apply' with no job named can still resolve
    which job that prompt was about."""

    return f"\n[[await_apply:{int(job_id)}]]" if job_id else ""


def split_awaiting_apply_decision(text):

    text = text or ""

    match = _AWAITING_APPLY_RE.search(text)

    if not match:

        return text, None

    return text[:match.start()], int(match.group(1))


def awaiting_cover_letter_marker(job_id):
    """Hidden suffix added to a saved bot message that just asked the
    student to type a cover letter, so the NEXT message can be recognised
    as that cover letter rather than a fresh request."""

    return f"\n[[await_cover:{int(job_id)}]]" if job_id else ""


def split_awaiting_cover_letter(text):
    """(clean_text, job_id or None) - removes the marker added above."""

    text = text or ""

    match = _AWAITING_COVER_RE.search(text)

    if not match:

        return text, None

    return text[:match.start()], int(match.group(1))


def shown_jobs_marker(job_ids):

    ids = [str(int(i)) for i in job_ids if i]

    return f"\n[[jobs:{','.join(ids)}]]" if ids else ""


def split_shown_jobs(text):
    """(clean_text, [job ids]) - removes the marker added by shown_jobs_marker."""

    text = text or ""

    match = _SHOWN_JOBS_RE.search(text)

    if not match:

        return text, []

    ids = [int(x) for x in match.group(1).split(",") if x]

    return text[:match.start()], ids


def _shown_jobs_from_history(history):
    """Open jobs listed on the cards of the assistant's previous message."""

    if not history:

        return []

    last = history[-1]

    if last.get("sender") != "bot" or not last.get("jobs"):

        return []

    from jobsystem.models import Job

    ids = list(last["jobs"])

    by_id = {
        j.id: j
        for j in Job.objects.filter(
            id__in=ids, status="active", is_active=True
        ).select_related("company")
    }

    return [by_id[i] for i in ids if i in by_id]


def _apply_blocker(profile, job):
    """
    Dict explaining why the student can't apply, or None if they can.
    Shape: {"message": str, "navigate_to": str?, "quick_replies": [...]?}
    - the extra fields are only set for an ELIGIBILITY failure (never
    for "already applied", since there's nothing to go fix for that),
    so the student always has a real next step instead of a dead end.
    Two match_score can differ per job - the same 52% match on two
    different jobs can pass one and fail the other, since each job
    sets its own eligibility requirements independently of match_score
    (see the MATCH SCORE VS ELIGIBILITY prompt guidance).
    """

    from jobsystem.models import Application
    from jobsystem.services.eligibility import check_eligibility

    company_name = job.company.company_name if job.company else "the company"

    if Application.objects.filter(student=profile, job=job).exists():

        return {
            "message": f"You've already applied to {job.title} at {company_name}."
        }

    try:

        eligibility = check_eligibility(profile, job)

    except Exception:

        eligibility = {"eligible": True}

    if not eligibility.get("eligible", True):

        # check_eligibility()'s real shape is
        # {"eligible": bool, "conditions": [{"status": "fail"/"pass",
        # "detail": "..."}, ...]} - the same structure the Apply modal
        # reads. Earlier code here read "reasons"/"reason" (keys that
        # don't exist on the real response), so a student was NEVER
        # shown a real reason, only a generic "based on your current
        # profile" with nothing specific - exactly the confusion of
        # "why not, it's 52% match?" that this is meant to prevent.

        why = "; ".join(_failing_details(profile, eligibility))

        tip = _department_tip(profile, eligibility)

        message = (
            f"You're not eligible to apply to {job.title} at "
            f"{company_name} based on your current profile."
            + (f" Specifically: {why.rstrip('. ')}." if why else "")
            + (f" {tip}" if tip else "")
        )

        # A real next step, not just a dead-end explanation - some
        # failures (like a missing age) are things the student can fix
        # themselves on their Profile page. Offered as a BUTTON rather than
        # an automatic page jump: the reply also shows the jobs they CAN
        # apply to instead, and jumping away mid-answer would bury that.

        return {
            "message": message,
            "quick_replies": ["Update my profile"],
        }

    return None


def _blocker_payload(blocker, reply_key):
    """Turns an _apply_blocker() dict into a reply payload under the
    given key ("summary" for a tool result, "reply" for a direct
    early-return), carrying navigate_to/quick_replies through so a
    blocked apply always gives the student a real next step - not
    just at whichever single call site remembered to copy them."""

    payload = {reply_key: blocker["message"]}

    if blocker.get("navigate_to"):

        payload["navigate_to"] = blocker["navigate_to"]

    if blocker.get("quick_replies"):

        payload["quick_replies"] = blocker["quick_replies"]

    return payload


def _do_apply(profile, user, job, cover_letter=""):
    """The one place an application is actually created from chat."""

    from jobsystem.models import Application

    company_name = job.company.company_name if job.company else "the company"

    blocker = _apply_blocker(profile, job)

    if blocker:

        return {"success": False, **_blocker_payload(blocker, "summary")}

    application, created = Application.objects.get_or_create(
        student=profile,
        job=job,
        defaults={"status": "applied", "cover_letter": cover_letter or ""},
    )

    if not created:

        return {
            "success": False,
            "summary": f"You've already applied to {job.title} at {company_name}.",
        }

    # Same confirmation notification the Apply page sends.

    try:

        from jobsystem.services.notification_engine import dispatch

        dispatch(
            "application_confirmation",
            user,
            {
                "job_title": job.title,
                "company_name": company_name,
            },
        )

    except Exception as e:

        print("Chatbot apply notification error:", e)

    return {
        "success": True,
        "job_id": job.id,
        "job_title": job.title,
        "company": company_name,
        "summary": (
            f"Applied to {job.title} at {company_name} successfully. "
            + ("Your cover letter was included. " if cover_letter else "")
            + "You can track it under Applications."
        ),
    }


def _confirm_apply_text(job_title, company_name, location=None):

    text = f"Yes, apply to {job_title} at {company_name}"

    if location:

        text += f" ({location})"

    return text


def _apply_chip_text(job):
    """
    Text of the "Yes, apply to ..." button for a job. If another open job
    has the very same title AND company (e.g. two Software Tester posts in
    different cities), the location is added so each button is unique.
    """

    from jobsystem.models import Job

    company_name = job.company.company_name if job.company else "the company"

    duplicates = Job.objects.filter(
        status="active", is_active=True,
        title__iexact=job.title, company=job.company,
    ).count()

    location = (getattr(job, "location", "") or "").strip()

    return _confirm_apply_text(
        job.title, company_name,
        location if duplicates > 1 and location else None,
    )


_JOB_TEXT_SEPARATORS = [
    " \u2013 ", " \u2014 ", " - ", " at ", " @ ", " | ", ", ",
]


def _normalize_job_query(text):
    """
    "the Software Tester jobs" -> "Software Tester". Students (and the AI)
    say things like "software tester jobs" or add quotes around the title.
    """

    t = (text or "").strip().strip("\"'").strip()

    t = re.sub(r"\s+", " ", t)

    t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.IGNORECASE)

    t = re.sub(
        r"\s+(jobs?|positions?|roles?|openings?|vacanc(?:y|ies))$",
        "", t, flags=re.IGNORECASE,
    )

    return t.strip()


def _resolve_jobs(job_title, company_name=""):
    """
    Finds the open job(s) a student means, however it was written:
      "Software Tester"
      "Software Tester - TechNova Solutions Pvt Ltd"   (any dash, "at", "@")
      title + separate company name
      "software tester jobs"
    Returns a list of matching Job objects (possibly empty).
    """

    from jobsystem.models import Job

    base = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company")

    title = _normalize_job_query(job_title)

    company = (company_name or "").strip()

    if not title:

        return []

    # 1) "<title> <separator> <company>" - try every separator position

    if not company:

        lowered = title.lower()

        for sep in _JOB_TEXT_SEPARATORS:

            start = 0

            while True:

                idx = lowered.find(sep.lower(), start)

                if idx == -1:

                    break

                title_part = title[:idx].strip()

                company_part = title[idx + len(sep):].strip()

                hits = list(base.filter(
                    title__iexact=title_part,
                    company__company_name__iexact=company_part,
                ))

                if hits:

                    return hits

                start = idx + 1

    # 2) the title (optionally narrowed by the company)

    qs = base.filter(title__icontains=title)

    if company:

        qs = qs.filter(company__company_name__icontains=company)

    hits = list(qs)

    if hits:

        # an exact title beats a partial one ("Tester" vs "Software Tester")

        exact = [j for j in hits if j.title.lower() == title.lower()]

        return exact or hits

    # 3) the text CONTAINS an open job's full title

    lowered = title.lower()

    contained = [j for j in base if j.title.lower() in lowered]

    if len(contained) > 1:

        with_company = [
            j for j in contained
            if j.company and j.company.company_name.lower() in lowered
        ]

        contained = with_company or contained

    return contained


def _tool_apply_to_job(profile, user, args):
    """
    PREPARE step only - never creates an application. Returns a
    confirmation question plus quick_replies (Yes / No buttons).
    """

    from jobsystem.models import Job

    job_title = (args.get("job_title") or "").strip()

    if not job_title:

        return {
            "success": False,
            "summary": "Which job would you like to apply to? Tell me the job title.",
        }

    candidates = _resolve_jobs(job_title, args.get("company_name") or "")

    count = len(candidates)

    if count == 0:

        return {
            "success": False,
            "summary": (
                f"I couldn't find an open job matching \"{job_title}\". "
                "Check the exact title on the Jobs page."
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
            "quick_replies": [
                _apply_chip_text(j) for j in candidates[:5]
            ] + ["No, cancel"],
            "summary": (
                f"{count} jobs match \"{job_title}\". "
                "Which one would you like to apply to?"
            ),
        }

    return _prepare_apply(profile, candidates[0])


def _cover_letter_chip_text(job):
    """Button text for 'add a cover letter before applying'. Reuses the
    Yes-chip's own job phrase (title/company[/location]) so it can be
    parsed back to the same job with the same logic."""

    yes_chip = _apply_chip_text(job)

    job_phrase = yes_chip[len("Yes, apply to "):]

    return f"Add a cover letter for {job_phrase}"


def _ai_cover_chip_text(job):
    """Button text for 'write it for me and apply'. Reuses the Yes-chip's
    own job phrase, exactly like _cover_letter_chip_text."""

    yes_chip = _apply_chip_text(job)

    job_phrase = yes_chip[len("Yes, apply to "):]

    return f"Write a cover letter for me and apply to {job_phrase}"


def _generate_ai_cover_letter(profile, job):
    """
    Drafts a short, genuine cover letter from the student's own profile
    and the real job posting - never inventing experience they didn't
    list. Raises on failure so the caller can fall back gracefully
    (never applies with a broken/empty letter silently).
    """

    company_name = job.company.company_name if job.company else "the company"

    skills = (getattr(profile, "skills", "") or "").strip()

    course = (getattr(profile, "course", "") or "").strip()

    career_interest = (getattr(profile, "career_interest", "") or "").strip()

    job_skills = (getattr(job, "skills_required", "") or "").strip()

    job_description = (getattr(job, "description", "") or "").strip()[:800]

    prompt = f"""Write a concise, genuine-sounding cover letter (roughly 150-220
words) for a student named {profile.full_name or "the applicant"} applying to
the "{job.title}" role at {company_name}.

CANDIDATE (only use what's given - never invent experience, companies,
projects or numbers that aren't listed here):
- Course/degree: {course or "not specified"}
- Skills: {skills or "not specified"}
- Career interest: {career_interest or "not specified"}

JOB:
- Title: {job.title}
- Company: {company_name}
- Required skills: {job_skills or "not specified"}
- Description: {job_description or "not specified"}

Write in first person, a warm but professional tone, plain text only (no
markdown, no headers, no placeholders like "[Your Name]"). Three short
paragraphs: (1) interest in the role, (2) 2-3 of the candidate's real
skills that match the job, (3) a brief closing. Output ONLY the letter
text, nothing else."""

    return _clean_reply(_call_groq_plain([{"role": "user", "content": prompt}]))


_AI_COVER_WITH_JOB_RE = re.compile(
    r"^\s*(?:please\s+)?(?:write|generate|create)\s+(?:me\s+)?(?:a\s+)?"
    r"(?:perfect\s+|good\s+|great\s+|professional\s+)?cover\s*letter\s+"
    r"(?:for\s+me\s+)?and\s+apply\s+to\s+(?P<rest>.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_AI_COVER_NO_JOB_RE = re.compile(
    r"^\s*(?:please\s+)?(?:write|generate|create)\s+(?:me\s+)?(?:a\s+)?"
    r"(?:perfect\s+|good\s+|great\s+|professional\s+)?cover\s*letter\s+"
    r"(?:for\s+me\s+)?and\s+apply"
    r"(?:\s+to\s+(?:it|that|this|that\s+job|this\s+job|the\s+above\s+job))?"
    r"\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _single_shown_job(history):

    shown = _shown_jobs_from_history(history)

    return shown[0] if len(shown) == 1 else None


def _awaiting_apply_decision_job(history):
    """The open Job the assistant's previous 'Apply to X? [buttons]'
    message was about, if that's still the last message."""

    if not history:

        return None

    last = history[-1]

    if last.get("sender") != "bot":

        return None

    job_id = last.get("awaiting_apply_job_id")

    if not job_id:

        return None

    from jobsystem.models import Job

    return Job.objects.filter(
        id=job_id, status="active", is_active=True
    ).select_related("company").first()


def _apply_with_ai_cover_letter(profile, user, job):
    """Generates the letter and applies with it in one step. Shared by
    the button/typed-phrase path and the 'you write it' shortcut while
    a manual cover letter was pending."""

    blocker = _apply_blocker(profile, job)

    if blocker:

        return _blocker_payload(blocker, "reply")

    try:

        cover_letter = _generate_ai_cover_letter(profile, job)

    except Exception as e:

        print("AI cover letter generation error:", e)

        return {
            "reply": (
                "I couldn't write a cover letter just now. Want to type "
                "your own instead, or apply without one?"
            ),
            "quick_replies": [_apply_chip_text(job), "No, cancel"],
        }

    result = _do_apply(profile, user, job, cover_letter=cover_letter)

    payload = {"reply": result["summary"]}

    if result.get("success") and cover_letter:

        payload["reply"] += (
            f"\n\nHere's the cover letter I wrote:\n\n{cover_letter}"
        )

    if result.get("success"):

        payload["refresh"] = ["applications", "dashboard", "jobs"]

    return payload


def _handle_ai_cover_letter_apply(profile, user, message, history):
    """
    "Write a cover letter for me and apply to X" (with or without a job
    named) - generates the letter and applies immediately, no manual
    typing. Returns a reply dict, or None if the message doesn't match.
    """

    text = message or ""

    # Check the pointer-word form FIRST: "...and apply to it/that/this" must
    # resolve via the just-shown job, not be treated as a literal job name
    # ("it" is not a job title) by the more general WITH_JOB pattern below.

    if _AI_COVER_NO_JOB_RE.match(text):

        job = _awaiting_apply_decision_job(history) or _single_shown_job(history)

        if job is not None:

            return _apply_with_ai_cover_letter(profile, user, job)

        shown = _shown_jobs_from_history(history)

        if len(shown) > 1:

            return {
                "reply": "Which job should I write the cover letter for?",
                "quick_replies": [
                    _apply_chip_text(j) for j in shown[:5]
                ] + ["No, cancel"],
            }

        return None

    match = _AI_COVER_WITH_JOB_RE.match(text)

    if match:

        job = _resolve_job_from_apply_phrase(match.group("rest"))

        if not job:

            return _JOB_NOT_FOUND_REPLY

        return _apply_with_ai_cover_letter(profile, user, job)

    return None

def _apply_alternatives(profile, blocked_job):
    """(text, cards): after telling a student why they can't apply to one
    job, what they CAN apply to instead - or an honest 'nothing else'."""

    found = _tool_find_matching_jobs(profile, None, {"limit": 3})

    cards = found.get("matched_jobs") or []

    if cards:

        return "Here are jobs you can apply to instead:", cards

    others_blocked = [
        (item["title"], item.get("reasons") or [])
        for item in found.get("not_eligible", [])
        if item["title"] != blocked_job.title
    ]

    note = _exclusion_note(found.get("already_applied_titles", []), others_blocked)

    text = "There are no other open jobs you can apply to right now."

    return (f"{text}\n\n{note}" if note else text), []


def _prepare_apply(profile, job):
    """Confirmation question + Yes/No buttons for one job (writes nothing).
    Also shows the real job card (with the same match score/location the
    Jobs page shows) - asking to apply directly, without going through
    find_matching_jobs first, used to show a bare text question with no
    card at all."""

    company_name = job.company.company_name if job.company else "the company"

    blocker = _apply_blocker(profile, job)

    if blocker:

        result = {"success": False, **_blocker_payload(blocker, "summary")}

        # Not eligible (as opposed to "already applied"): the student
        # asked to apply and got a no - so also show what they CAN apply to.

        if blocker.get("quick_replies"):

            alt_text, alt_cards = _apply_alternatives(profile, job)

            result["summary"] = f"{result['summary']}\n\n{alt_text}"

            if alt_cards:

                result["matched_jobs"] = alt_cards

        return result

    confirm_text = _apply_chip_text(job)

    from jobsystem.services.job_matching import compute_job_match

    try:

        match_score, reasons = compute_job_match(profile, job)

    except Exception as e:

        print("Chatbot apply-confirmation match score error:", e)

        match_score, reasons = None, []

    return {
        "success": False,
        "needs_confirmation": True,
        "job_id": job.id,
        "job_title": job.title,
        "company": company_name,
        "matched_jobs": [
            _serialize_matched_job(
                job, match_score, reasons, already_applied=False
            )
        ],
        "quick_replies": [
            confirm_text,
            _cover_letter_chip_text(job),
            _ai_cover_chip_text(job),
            "No, cancel",
        ],
        "awaiting_apply_decision_job_id": job.id,
        "summary": (
            f"Apply to {job.title} at {company_name}? Tap Yes to confirm, "
            "add your own cover letter, or have me write one for you."
        ),
    }


_CONFIRM_APPLY_RE = re.compile(
    r"^\s*yes,?\s+apply\s+to\s+(?P<rest>.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_CANCEL_APPLY_RE = re.compile(
    r"^\s*no,?\s+cancel\s*[.!]?\s*$",
    re.IGNORECASE,
)


_APPLY_INTENT_RE = re.compile(
    r"^\s*(?:(?:yes|yeah|yep|ok|okay|sure|please|and)\b[,.!\s]*)*"
    r"(?:(?:i\s+(?:want|would\s+like|wanna|need)\s+to|i'd\s+like\s+to|"
    r"let'?s|can\s+you|could\s+you|please)\s+)*apply\b",
    re.IGNORECASE,
)

# Words that can follow "apply" while still just POINTING at a job that was
# shown ("apply above job", "apply for the second one", "yes apply now").
# If any other word appears (e.g. a job title), the message names a job itself.

_APPLY_POINTER_WORDS = {
    "to", "for", "the", "a", "an", "this", "that", "it", "above", "previous",
    "last", "first", "second", "third", "1st", "2nd", "3rd", "top",
    "recommended", "same", "job", "jobs", "position", "positions", "role",
    "roles", "one", "ones", "now", "please", "opening", "posting",
    "thanks", "thank", "you",
}


def _is_apply_pointer_phrase(text):
    """
    True for phrases that only POINT at a job already shown/asked about
    ("apply above job", "yes apply", "apply the second one") rather than
    naming one, or containing anything else (like real cover-letter text).
    """

    match = _APPLY_INTENT_RE.match(text or "")

    if not match:

        return False

    tokens = re.findall(r"[a-z0-9']+", (text or "")[match.end():].lower())

    return not any(t not in _APPLY_POINTER_WORDS for t in tokens)


def _awaiting_cover_letter_job(history):
    """The open Job the assistant just asked the student to write a
    cover letter for, if its previous message is still the last one."""

    if not history:

        return None

    last = history[-1]

    if last.get("sender") != "bot":

        return None

    job_id = last.get("awaiting_cover_job_id")

    if not job_id:

        return None

    from jobsystem.models import Job

    return Job.objects.filter(
        id=job_id, status="active", is_active=True
    ).select_related("company").first()


def _handle_apply_reference(profile, user, message, history):
    """
    "i want to apply above job" / "yes apply" / "apply the first one" -
    resolved from the jobs the assistant showed in its previous message,
    NOT guessed by the AI. Returns a reply dict, or None to carry on
    normally (e.g. the student named a specific job, or nothing was shown).
    """

    text = message or ""

    if not _is_apply_pointer_phrase(text):

        return None

    match = _APPLY_INTENT_RE.match(text)

    tokens = re.findall(r"[a-z0-9']+", text[match.end():].lower())

    shown = _shown_jobs_from_history(history)

    if not shown:

        return None

    if len(shown) == 1:

        job = shown[0]

    else:

        index = None

        if "second" in tokens or "2nd" in tokens:

            index = 1

        elif "third" in tokens or "3rd" in tokens:

            index = 2

        elif "last" in tokens:

            index = len(shown) - 1

        elif any(t in tokens for t in ("first", "1st", "top", "recommended")):

            index = 0

        if index is None or index >= len(shown):

            return {
                "reply": "Which job would you like to apply to?",
                "quick_replies": [
                    _apply_chip_text(j) for j in shown[:5]
                ] + ["No, cancel"],
            }

        job = shown[index]

    result = _prepare_apply(profile, job)

    # Reuse the exact same forwarding logic the apply_to_job TOOL path
    # already uses (_build_tool_payload), rather than hand-picking keys
    # here - hand-picking is what silently dropped "matched_jobs" (no
    # match-score card shown) and "awaiting_apply_decision_job_id" (a
    # later "write a cover letter and apply" with no job named couldn't
    # resolve it) when this function was first written, before
    # _prepare_apply grew those fields.

    return _build_tool_payload(
        result["summary"], [(None, "prepare_apply", result)]
    )


# "teacher job i want to apply", "i want to apply for the teacher role",
# "apply to Software Tester" ... a NAMED job plus a wish to apply. Sent
# straight to the apply flow instead of leaving it to the AI to pick the
# right tool - which once answered "teacher job i want to apply" with a
# generic list of eligible jobs and never explained why Teacher was blocked.

_NAMED_APPLY_PATTERNS = [
    re.compile(
        r"^\s*(?P<job>.+?)\s+(?:job|position|role)\s*,?\s*"
        r"(?:i\s+)?(?:want\s+to|would\s+like\s+to|wanna|need\s+to)\s+apply\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?(?:i\s+)?(?:want\s+to|would\s+like\s+to|wanna|need\s+to)\s+apply"
        r"\s+(?:to\s+|for\s+)?(?:the\s+)?(?P<job>.+?)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?apply\s+(?:to\s+|for\s+)?(?:the\s+)?(?P<job>.+?)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
]

_GENERIC_JOB_WORDS = {
    "job", "jobs", "position", "positions", "role", "roles", "opening",
    "openings", "vacancy", "vacancies", "a", "an", "the", "some", "any",
    "one", "ones", "it", "this", "that", "these", "those", "now", "please",
}


def _handle_named_apply(profile, user, message, history=None):
    """
    A named job + intent to apply -> the apply flow (a confirmation, or the
    real reasons it's blocked plus the jobs they CAN apply to). Returns None
    - so the normal AI flow continues - unless the name matches a real open
    job, so ordinary sentences containing the word "apply" are left alone.
    """

    text = (message or "").strip()

    if not text or _is_apply_pointer_phrase(text):

        return None

    job_text = None

    for pattern in _NAMED_APPLY_PATTERNS:

        match = pattern.match(text)

        if match:

            job_text = match.group("job").strip()

            break

    if not job_text or len(job_text.split()) > 8:

        return None

    words = re.findall(r"[a-z0-9']+", _normalize_job_query(job_text).lower())

    if not words or all(w in _GENERIC_JOB_WORDS or w in _APPLY_POINTER_WORDS for w in words):

        return None

    if not _resolve_jobs(job_text):

        return None

    result = _tool_apply_to_job(profile, user, {"job_title": job_text})

    return _build_tool_payload(
        result["summary"], [(None, "apply_to_job", result)]
    )


def _user_facing(summary):
    """Tool summaries are written for the AI ("the student"); if one has to
    be shown to the student directly, speak to them instead."""

    text = summary or ""

    replacements = [
        (r"\bthe student hasn't\b", "you haven't"),
        (r"\bthe student isn't\b", "you aren't"),
        (r"\bthe student doesn't\b", "you don't"),
        (r"\bthe student has\b", "you have"),
        (r"\bthe student is\b", "you are"),
        (r"\bthe student was\b", "you were"),
        (r"\bthe student's\b", "your"),
        (r"\bstudent's\b", "your"),
        (r"\bthe student\b", "you"),
    ]

    for pattern, replacement in replacements:

        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text[:1].upper() + text[1:] if text else text


def _resolve_job_from_apply_phrase(rest):
    """
    "<title> at <company>[ (Location)]" -> the matching open Job, or None.
    Shared by the Yes-confirmation handler and the "add a cover letter for
    ..." handler below, since both buttons carry the same phrase format.
    """

    from jobsystem.models import Job

    # optional trailing "(Chennai)" - used when two open jobs share the
    # same title and company

    location = None

    loc_match = re.search(r"\s*\(([^()]+)\)\s*$", rest)

    if loc_match:

        location = loc_match.group(1).strip()

        rest = rest[:loc_match.start()].strip()

    # "<title> at <company>" - try every " at " as the split point,
    # so titles or company names that contain "at" still resolve.

    for split in re.finditer(r"\s+at\s+", rest, flags=re.IGNORECASE):

        title = rest[:split.start()].strip()

        company = rest[split.end():].strip()

        lookup = dict(
            status="active", is_active=True,
            title__iexact=title,
            company__company_name__iexact=company,
        )

        if location:

            lookup["location__iexact"] = location

        job = Job.objects.filter(**lookup).select_related("company").first()

        if job:

            return job

    return None


_JOB_NOT_FOUND_REPLY = {
    "reply": (
        "I couldn't find that open job any more. Ask me to find "
        "jobs again and I'll show the current list."
    )
}


def _handle_apply_confirmation(profile, user, message):
    """
    Deterministic handler for the Yes / No buttons after an apply
    confirmation. Returns a reply dict, or None if the message is
    not a confirmation (so the normal AI flow continues).
    """

    text = message or ""

    if _CANCEL_APPLY_RE.match(text):

        return {
            "reply": "Okay, I won't apply. Let me know if you'd like anything else."
        }

    match = _CONFIRM_APPLY_RE.match(text)

    if not match:

        return None

    job = _resolve_job_from_apply_phrase(match.group("rest"))

    if not job:

        return _JOB_NOT_FOUND_REPLY

    result = _do_apply(profile, user, job)

    payload = {"reply": result["summary"]}

    if result.get("success"):

        payload["refresh"] = ["applications", "dashboard", "jobs"]

    else:

        # Blocked (ineligible / already applied) - forward the real next
        # step _apply_blocker attached, so tapping Yes on a job that
        # turns out to be blocked still ends with something the student
        # can actually do, not just a repeated dead-end message.

        for key in ("navigate_to", "quick_replies"):

            if result.get(key):

                payload[key] = result[key]

    return payload


_COVER_LETTER_REQUEST_RE = re.compile(
    r"^\s*add\s+a\s+cover\s*letter\s+for\s+(?P<rest>.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _handle_cover_letter_request(profile, user, message):
    """
    "Add a cover letter for X at Y" (the third button under a job
    recommendation) - asks the student to type it, and remembers which
    job it's for via a marker on the saved reply. Returns a reply dict,
    or None if the message doesn't match.
    """

    match = _COVER_LETTER_REQUEST_RE.match(message or "")

    if not match:

        return None

    job = _resolve_job_from_apply_phrase(match.group("rest"))

    if not job:

        return _JOB_NOT_FOUND_REPLY

    blocker = _apply_blocker(profile, job)

    if blocker:

        return _blocker_payload(blocker, "reply")

    company_name = job.company.company_name if job.company else "the company"

    return {
        "reply": (
            f"Sure! Type your cover letter for {job.title} at "
            f"{company_name} and I'll include it when I apply "
            "(or say \"skip\" to apply without one)."
        ),
        "awaiting_cover_letter_job_id": job.id,
    }


_SKIP_COVER_RE = re.compile(
    r"^\s*(skip|no|none|no\s+cover\s*letter)\s*[.!]?\s*$",
    re.IGNORECASE,
)

# While the student was just asked to TYPE a cover letter, this lets them
# hand it back to the assistant instead ("write it for me", "you write it").

_AI_WRITE_FOR_ME_RE = re.compile(
    r"^\s*(?:you\s+write\s+it|write\s+it\s+for\s+me|write\s+one\s+for\s+me|"
    r"generate\s+(?:one|it)(?:\s+for\s+me)?|ai\s+write\s+it|"
    r"can\s+you\s+write\s+it)\s*[.!]?\s*$",
    re.IGNORECASE,
)

# Broader than _CANCEL_APPLY_RE (which only matches the "No, cancel" BUTTON
# text) - here the student is typing free text with no button, so "cancel"
# or "never mind" alone must also work.

_CANCEL_COVER_RE = re.compile(
    r"^\s*(cancel|never\s*mind|stop|don'?t\s+apply)\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _handle_pending_cover_letter_text(profile, user, message, history):
    """
    While the student was just asked "type your cover letter", THIS
    message is that cover letter (unless it's clearly a cancel or a
    fresh "apply the second one"-style pointer). Returns a reply dict,
    or None to fall through to the normal flow.
    """

    job = _awaiting_cover_letter_job(history)

    if job is None:

        return None

    text = (message or "").strip()

    if _CANCEL_APPLY_RE.match(text) or _CANCEL_COVER_RE.match(text):

        return {
            "reply": "Okay, I won't apply. Let me know if you'd like anything else."
        }

    if _is_apply_pointer_phrase(text):

        # e.g. "apply the second one" - a fresh apply request, not the
        # cover letter text that was asked for.

        return None

    if _AI_WRITE_FOR_ME_RE.match(text):

        return _apply_with_ai_cover_letter(profile, user, job)

    cover_letter = "" if (not text or _SKIP_COVER_RE.match(text)) else text[:4000]

    result = _do_apply(profile, user, job, cover_letter=cover_letter)

    payload = {"reply": result["summary"]}

    if result.get("success"):

        payload["refresh"] = ["applications", "dashboard", "jobs"]

    return payload


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

        # Attach a real upcoming interview's date/time/mode AND that
        # job's required skills whenever one exists - checked
        # regardless of the application's own status label, NOT only
        # when status=="interview". A company can schedule (or
        # re-schedule) an interview for a candidate already marked
        # "selected" or "shortlisted" without changing that label
        # back (see CompanyInterviewCreateView), so gating on the
        # label alone silently hid real, upcoming interviews here -
        # exactly what made the assistant wrongly say "no interviews
        # scheduled" for a student who actually had two.

        upcoming_iv = Interview.objects.filter(
            application=app,
            interview_date__gte=timezone.now(),
            status__in=["scheduled", "rescheduled"],
        ).order_by("interview_date").first()

        if upcoming_iv:

            job_skills = [
                s.strip()
                for s in (app.job.skills_required or "").split(",")
                if s.strip()
            ]

            entry["interview"] = {
                "date": _to_india_time(upcoming_iv.interview_date).strftime("%b %d, %Y"),
                "time": _to_india_time(upcoming_iv.interview_date).strftime("%I:%M %p"),
                "mode": upcoming_iv.get_interview_mode_display(),
                "job_skills_required": job_skills,
            }

            has_interview_scheduled = True

        applications.append(entry)

    # Same fix already applied to the ATS check and resume feedback tools:
    # "summary" is what the model reads for its answer AND, if the second
    # pass ever falls back to the raw tool result (the account's tight
    # shared Groq quota making that call fail), the one thing shown to the
    # student. A bare count meant "what jobs did I apply to?" could only
    # ever be answered with "3 applications found." and nothing else.

    if applications:

        lines = [
            f"- {a['job_title']} at {a['company']}: {a['status']}"
            for a in applications[:8]
        ]

        summary = (
            f"{len(applications)} application(s):\n\n" + "\n".join(lines)
        )

    else:

        summary = "The student hasn't applied to any jobs yet."

    return {
        "applications": applications,
        "has_interview_scheduled": has_interview_scheduled,
        "navigate_to": "/student/applications",
        "summary": summary,
    }


def _tool_get_upcoming_interviews(profile, user, args):

    from jobsystem.models import Interview

    now = timezone.now()

    week_only = bool(args.get("this_week"))

    today_only = bool(args.get("today"))

    week_end = now + timedelta(days=7)

    qs = Interview.objects.filter(
        application__student=profile,
        interview_date__gte=now,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    if today_only:

        # "Any interview scheduled today?" - a real gap found by report:
        # no tool here could answer "today" specifically at all before
        # this, only "this week" (a much wider window). Computed in
        # INDIA TIME specifically (see _india_today_utc_bounds), not
        # server/UTC time, since that's the actual timezone of this
        # platform's real users - a student asking "today" late in the
        # evening IST should never get an answer based on what UTC or
        # the server's own Asia/Kuala_Lumpur clock considers "today".

        _today_start, today_end = _india_today_utc_bounds()

        qs = qs.filter(interview_date__lt=today_end)

    elif week_only:

        qs = qs.filter(interview_date__lte=week_end)

    interviews = [_serialize_interview(iv) for iv in qs]

    # Matches the project spec's own worked example almost exactly:
    # "You have 2 interviews this week: ABC Technologies - Aug 28,
    # 10:00 AM; XYZ Solutions - Aug 30, 2:00 PM." Same fix as every
    # other tool here - the real interview data was already being
    # fetched, it just never made it into the actual answer.

    if interviews:

        lines = [
            f"- {iv['company']} ({iv['job_title']}): {iv['date']} at {iv['time']} ({iv['mode']})"
            for iv in interviews[:8]
        ]

        scope = " today" if today_only else (" this week" if week_only else "")

        summary = (
            f"You have {len(interviews)} upcoming interview(s){scope}"
            + ":\n\n" + "\n".join(lines)
        )

    elif today_only:

        summary = "You don't have any interviews scheduled for today."

    else:

        summary = (
            "You don't have any interviews scheduled"
            + (" this week." if week_only else " right now.")
        )

    return {
        "interviews": interviews,
        "navigate_to": "/student/interviews",
        "summary": summary,
    }


_JOB_TITLE_KEYWORD_STOPWORDS = {
    "the", "a", "an", "job", "jobs", "role", "roles", "position",
    "positions", "for", "of", "related", "interview", "interviews",
    "prepare", "preparing", "prep", "want", "to", "i", "need", "my",
}


def _job_title_keyword_q(field_prefix, job_title):
    """
    Builds a Q matching ANY significant word in job_title against
    <field_prefix>__icontains, instead of requiring the WHOLE phrase
    as one literal substring - "software developer job related
    interview" should still find a real posting like "Junior Python
    Full Stack Developer" via the shared word "developer", even
    though the real title never contains "software developer" (or
    the student's full sentence) as one continuous substring. Same
    approach as get_job_description on the company side - a
    recruiter's or student's own phrasing of a role very often
    doesn't literally appear in the real posting title. Returns None
    if nothing usable is left after stripping filler words.
    """

    from django.db.models import Q

    words = [
        w for w in re.split(r"\s+", (job_title or "").lower())
        if len(w) > 2 and w not in _JOB_TITLE_KEYWORD_STOPWORDS
    ]

    if not words:

        return None

    q = Q()

    for w in words:

        q |= Q(**{f"{field_prefix}__icontains": w})

    return q


def _tool_get_interview_prep(profile, user, args):
    """
    Covers "How can I prepare for this interview?" with real
    grounding: the actual scheduled interview's job title, company,
    and required skills, so the model's prep suggestions are
    genuinely specific rather than generic advice.

    If nothing is scheduled yet, falls back to a real application the
    student already made for that role instead of refusing outright -
    a student waiting to hear back, or simply studying ahead for a job
    they applied to, is a completely normal thing to want prep help
    for, and the same real data (skills required, job description,
    company) already exists on the application regardless of whether
    an interview has been booked.
    """

    from jobsystem.models import Interview, Application

    job_title = (args.get("job_title") or "").strip()

    qs = Interview.objects.filter(
        application__student=profile,
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date")

    if job_title:

        # Strict (AND, every word must match) rather than the loose
        # OR-matching _job_title_keyword_q uses elsewhere - a real
        # report found "prepare for Senior Frontend Developer"
        # incorrectly returning the student's actual "Senior Software
        # Tester" application/interview, purely because both titles
        # happen to share the single word "Senior". Loose matching is
        # right when finding ANY plausible job is good enough; it is
        # wrong here, where confidently naming the WRONG role's real
        # data is worse than correctly finding nothing.

        title_q = _job_role_strict_match_q("application__job__title", job_title)

        if title_q is not None:

            qs = qs.filter(title_q)

    interview = qs.first()

    if interview:

        job = interview.application.job

        skills_required = [
            s.strip() for s in (job.skills_required or "").split(",")
            if s.strip()
        ]

        company_name = job.company.company_name if job.company else "Company"

        job_description = getattr(job, "description", "") or ""

        # Same fix as every other tool in this file: "summary" is what
        # gets shown if the model's own write-up pass is ever skipped
        # or fails (a busy time/token budget, a Groq hiccup) - a bare
        # one-liner here meant the student got NOTHING useful in that
        # case, despite the real skills/description already being
        # found. Listing them directly means there is always a real,
        # useful fallback answer, not just a dead end.

        prep_lines = [
            f"Interview for {job.title} at {company_name} on "
            f"{_to_india_time(interview.interview_date).strftime('%b %d, %Y')} at "
            f"{_to_india_time(interview.interview_date).strftime('%I:%M %p')} "
            f"({interview.get_interview_mode_display()})."
        ]

        if skills_required:

            prep_lines.append(
                "\nKey skills to prepare: " + ", ".join(skills_required[:10])
            )

        if job_description:

            prep_lines.append(f"\nRole: {job_description[:400]}")

        return {
            "job_title": job.title,
            "company": company_name,
            "interview_date": _to_india_time(interview.interview_date).strftime("%b %d, %Y"),
            "interview_time": _to_india_time(interview.interview_date).strftime("%I:%M %p"),
            "mode": interview.get_interview_mode_display(),
            "skills_required": skills_required,
            "job_description": job_description,
            "summary": "\n".join(prep_lines),
        }

    apps_qs = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company").order_by("-applied_date")

    if job_title:

        # Same precision fix as the interview search above, and for
        # the same reason - the application fallback must not claim a
        # different real application just because it shares one word
        # with the role actually asked about.

        title_q = _job_role_strict_match_q("job__title", job_title)

        if title_q is not None:

            apps_qs = apps_qs.filter(title_q)

    application = apps_qs.first()

    if application:

        job = application.job

        skills_required = [
            s.strip() for s in (job.skills_required or "").split(",")
            if s.strip()
        ]

        job_description = getattr(job, "description", "") or ""

        company_name = job.company.company_name if job.company else "Company"

        prep_lines = [
            f"No interview is scheduled yet for {job.title} at "
            f"{company_name} (application status: "
            f"{application.get_status_display()}), but here's what "
            "to prepare based on the role's real requirements."
        ]

        if skills_required:

            prep_lines.append(
                "\nKey skills to prepare: " + ", ".join(skills_required[:10])
            )

        if job_description:

            prep_lines.append(f"\nRole: {job_description[:400]}")

        return {
            "job_title": job.title,
            "company": company_name,
            "interview_scheduled": False,
            "application_status": application.get_status_display(),
            "skills_required": skills_required,
            "job_description": job_description,
            "summary": "\n".join(prep_lines),
        }

    return {
        "summary": (
            "No upcoming interview found to prepare for."
            + (f" (looked for \"{job_title}\")" if job_title else "")
        ),
    }


def _tool_get_resume_feedback(profile, user, args):
    """
    Returns the OFFICIAL resume score - the one saved by the AI
    analysis on the Resume page - never a newly calculated one, so
    the chatbot always shows the same number as the Resume page.
    """

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume:

        return {
            "has_resume": False,
            "summary": "The student hasn't uploaded a resume yet.",
        }

    missing_information = resume.missing_information or []

    skills_detected = resume.skills or []

    suggested_job_categories = resume.job_categories or []

    # Same fix as check_ats_friendliness below: "summary" is what the
    # model reads to write its answer AND, if that second pass ever
    # falls back to the raw tool result (the model's own explanatory
    # call failing, or the account's tight shared Groq quota - see the
    # daily token ceiling), the one thing shown to the student. A bare
    # score with no real content here meant "what's my score?" and
    # "what do I need to improve?" produced the exact same unhelpful
    # line, since neither question's real answer was ever written down.

    if missing_information:

        lines = [f"- {item}" for item in missing_information[:8]]

        summary = (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100. To improve it:\n\n"
            + "\n".join(lines)
        )

    else:

        summary = (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100. No specific gaps were flagged - "
            "this resume already covers the essentials."
        )

    return {
        "has_resume": True,
        "resume_score": resume.resume_score,
        "skills_detected": skills_detected,
        "missing_information": missing_information,
        "suggested_job_categories": suggested_job_categories,
        "navigate_to": "/student/resume",
        "summary": summary,
    }


# check_ats_friendliness is the one student tool that genuinely needs a
# fresh Groq call every time it runs - unlike "what's my score" (a plain
# database read), it's real AI analysis, so it can never be made a
# zero-AI-call shortcut the way plain lookups were. What it CAN be is
# cheap to ask again: this caches the last SUCCESSFUL result per
# (resume, target_role) for a few minutes, so a student asking "is my
# resume ATS friendly" twice in a row - or the student and a classmate
# both asking about a resume moments apart - gets the same real answer
# instantly the second time, instead of spending another slice of the
# account's tight shared quota re-computing something already known.
# Deliberately in-memory, not persisted to the database or a migration -
# it only needs to survive a few minutes on the same running process,
# and a fresh resume upload naturally gets a new resume.id, so it can
# never serve a stale result for a resume that's since changed.
#
# Failures are NEVER cached - a busy/rate-limited attempt should always
# get a genuine fresh try next time, not be locked into repeating the
# same failure for the cache's whole lifetime.

_ATS_CHECK_CACHE = {}   # (resume_id, target_role) -> (cached_at, result dict)

ATS_CHECK_CACHE_TTL = float(os.getenv("ATS_CHECK_CACHE_TTL", "300"))


def _tool_check_ats_friendliness(profile, user, args):
    """
    Uses AI to find ATS problems and suggestions, but NEVER returns
    its own separate score - the only score shown anywhere is the
    official resume_score saved by the Resume page's AI analysis,
    so the chatbot and the Resume page always show the same number.
    """

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

    cache_key = (resume.id, target_role)

    cached = _ATS_CHECK_CACHE.get(cache_key)

    if cached and (time.monotonic() - cached[0]) < ATS_CHECK_CACHE_TTL:

        return cached[1]

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
            "resume_score": resume.resume_score,
            "summary": f"Could not run the ATS check right now ({e}).",
        }

    issues = result.get("issues", [])

    suggestions = result.get("suggestions", [])

    # analyze_ats_friendliness() catches ITS OWN failures internally and
    # returns a normal-shaped success dict even when every model attempt
    # failed - its one "issue" in that case is the raw error text (a Groq
    # rate-limit message, a timeout, etc.), not a real finding about the
    # resume. Without this check, that raw error text got listed as if it
    # were genuine ATS feedback - showing the student a fake "issue" that
    # was actually just Groq's rate-limit message with an org ID and
    # token counts in it. Detected and reported as what it actually is:
    # the check couldn't run right now, try again shortly.

    if len(issues) == 1 and issues[0].startswith("ATS analysis failed:"):

        # The ATS-SPECIFIC check genuinely needs a live AI call and just
        # failed (shared quota busy) - but the ORIGINAL resume analysis,
        # done once at upload time, already found real, concrete gaps
        # (missing_information) and saved them. Reading that back here
        # costs nothing - zero AI calls - so "the AI is busy" no longer
        # means the student gets nothing actionable, just not the
        # ATS-specific formatting/parsing checks (headers, columns,
        # fonts) that genuinely require a fresh analysis.

        fallback_lines = [
            "I couldn't run the ATS check just now - the AI service is "
            f"temporarily busy. Your official resume score is still "
            f"{resume.resume_score}/100 either way."
        ]

        if resume.missing_information:

            fallback_lines.append(
                "\nWhat's already known to improve it:\n"
                + "\n".join(f"- {item}" for item in resume.missing_information[:8])
            )

        fallback_lines.append(
            "\nFor the ATS-specific formatting checks (headers, columns, "
            "parsing), please try again in a minute."
        )

        return {
            "has_resume": True,
            "resume_score": resume.resume_score,
            "missing_information": resume.missing_information,
            "summary": "\n".join(fallback_lines),
        }

    # The actual issue/suggestion TEXT goes into "summary" - not just their
    # count. "summary" is what the model reads for its answer AND, once
    # written into the model's reply, the one thing that gets saved to
    # chat history - a bare count here meant a student asking a natural
    # follow-up ("what are the issues?") gave the model nothing to answer
    # from, so it silently re-ran the ENTIRE ATS check again (a real Groq
    # call, wasting time and the account's rate-limit budget) just to
    # re-discover the same information a second time. Listing the real
    # text here means the first answer is already useful, and a follow-up
    # can be answered from history with no extra tool call at all.

    if issues:

        lines = [f"- {issue}" for issue in issues[:8]]

        if suggestions:

            lines.append("")

            lines.append("Suggested fixes:")

            lines.extend(f"- {item}" for item in suggestions[:8])

        summary = (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100. ATS check found "
            f"{len(issues)} issue(s):\n\n" + "\n".join(lines)
        )

    else:

        summary = (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100. No ATS issues found - "
            "this resume should parse cleanly."
        )

    payload = {
        "has_resume": True,
        "resume_score": resume.resume_score,
        "issues": issues,
        "suggestions": suggestions,
        "rewritten_bullets": result.get("rewritten_bullets", []),
        "summary": summary,
    }

    # Only a genuine success is cached - see the note above
    # _ATS_CHECK_CACHE for why a failure never is.

    _ATS_CHECK_CACHE[cache_key] = (time.monotonic(), payload)

    return payload


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

    if len(message_text) < 5:

        return {
            "success": False,
            "summary": (
                "What would you like to ask the placement team? Tell me the "
                "question or problem and I'll send it."
            ),
        }

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


def _tool_rewrite_resume(profile, user, args):
    """
    Generates an improved, rewritten version of the resume's CONTENT as
    text in chat - grounded in what the original analysis already found
    (missing_information, the real extracted text) - without touching
    the student's actual stored file. Deliberately does NOT auto-replace
    the uploaded resume: turning AI-written text into a new, properly
    formatted PDF/DOCX and silently swapping it in for the official
    record is a much bigger, riskier undertaking than reading it back
    safely in chat first. This always shows the proposed version for
    the student to review and copy into their own resume, never a
    silent replacement - the same "prepare, don't just do it" caution
    already used for applying to jobs and shortlisting candidates.
    """

    from jobsystem.models import Resume

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    if not resume or not resume.extracted_text:

        return {
            "has_resume": False,
            "summary": (
                "I don't have readable text from a resume to rewrite yet - "
                "please upload one first (or re-upload if it was a scanned "
                "image), then ask me to rewrite it."
            ),
        }

    missing = resume.missing_information or []

    prompt = f"""You are an expert resume writer. Below is a student's actual
resume text, and a list of real gaps already identified in it. Rewrite the
resume to address those gaps - add a professional summary if missing, make
bullet points achievement-focused and quantified wherever the original
text gives you real numbers/outcomes to work with, improve structure and
keyword relevance - but NEVER invent experience, companies, metrics, or
outcomes that aren't genuinely implied by the original text. If the
original doesn't support a specific number, phrase the bullet point
strongly without fabricating one.

Known gaps to address:
{chr(10).join(f"- {item}" for item in missing) if missing else "(none specifically flagged - improve clarity and impact generally)"}

Original resume text:
---
{resume.extracted_text[:6000]}
---

Output ONLY the rewritten resume text, plain text, no markdown, no
commentary before or after it."""

    try:

        rewritten = _clean_reply(_call_groq_plain([{"role": "user", "content": prompt}]))

    except Exception as e:

        return {
            "has_resume": True,
            "summary": (
                "I couldn't generate a rewrite just now - the AI service is "
                f"temporarily busy ({e}). Please try again in a moment."
            ),
        }

    return {
        "has_resume": True,
        "rewritten_resume": rewritten,
        "summary": (
            "Here's a proposed rewrite based on your resume and the gaps "
            "already identified. Nothing has changed yet - this is only a "
            "suggestion for you to review:\n\n" + rewritten +
            "\n\nIf you'd like, copy what you want into your resume and "
            "re-upload it so your official score updates too."
        ),
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


def _looks_like_a_skill(text):
    """A skill is a short name ('SQL', 'API Testing', 'C++'), never a sentence
    such as 'i want to prepare lunch today'."""

    words = re.findall(r"[a-z0-9+#.']+", (text or "").lower())

    return 0 < len(words) <= 4 and len(text) <= 30 and not (set(words) & _SENTENCE_WORDS)


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

    candidates = [x.strip() for x in new_skills_raw.split(",") if x.strip()]

    valid = [x for x in candidates if _looks_like_a_skill(x)]

    if not valid:

        return {
            "success": False,
            "summary": (
                "Those don't look like skills, so I haven't added anything. "
                "Tell me the skills as a comma-separated list, for example: "
                "Selenium, API Testing, SQL."
            ),
        }

    for skill in valid:

        if skill.lower() not in existing_lower:

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
        "summary": f"Added {', '.join(added)} to the student's skills.",
    }


def _tool_update_my_projects(profile, user, args):
    """
    A real write action - adds new projects directly to the student's
    profile from chat, the same additive/non-destructive design as
    update_my_skills above (never removes or overwrites existing
    projects). Stored one per line (profile.projects is free-text,
    unlike the comma-tagged skills field), so a project's own
    description can safely contain commas. Only call when the student
    clearly asks to add a project - see the guardrail in SYSTEM_TEMPLATE.
    """

    new_projects_raw = (args.get("projects") or "").strip()

    if not new_projects_raw:

        return {
            "success": False,
            "summary": "No project was given to add.",
        }

    existing_lines = [
        p.strip() for p in (profile.projects or "").split("\n") if p.strip()
    ]

    existing_lower = set(p.lower() for p in existing_lines)

    candidates = [
        p.strip() for p in new_projects_raw.split("\n") if p.strip()
    ] or [new_projects_raw]

    added = []

    for project in candidates:

        if project.lower() not in existing_lower:

            added.append(project)

            existing_lower.add(project.lower())

    if not added:

        return {
            "success": False,
            "summary": "That project is already on the student's profile.",
        }

    profile.projects = "\n".join(existing_lines + added)

    profile.save()

    return {
        "success": True,
        "added_projects": added,
        "all_projects": profile.projects,
        "summary": f"Added \"{', '.join(added)}\" to the student's projects.",
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

If the candidate says they genuinely don't know the answer and asks you to
explain it or tell them (e.g. "I don't know, you tell me", "what's the
answer?", "can you explain it?"), that is a normal, reasonable moment in a
PREPARATION tool, not an attempt to skip the question - briefly give a real,
helpful model answer or explanation (2-4 sentences: what a strong answer
would actually cover), say something encouraging and low-pressure, then
move on to the next question. This is different from the off-topic case
below - an honest "I don't know" about the CURRENT interview question
deserves real teaching, not a refusal, since the whole point of practicing
is to learn what a good answer looks like.

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
    r"\bquit\b.*interview", r"\bexit\b.*interview",
    # A leading "ok"/"yes"/"please" acknowledgment before the real exit
    # word - a real report found bare "stop" correctly ending a mock
    # interview, but "ok stop" and "yes stop" (asked right after) did
    # not, instead being sent to Groq as if they were the candidate's
    # actual answer to the current question. Same class of leading-
    # filler-word gap fixed elsewhere in this file for other shortcuts.
    r"^\s*(?:ok(?:ay)?|yes|please|sure)[,.\s]+(?:stop|cancel|quit|exit|end)\s*[.!]?\s*$",
    r"^\s*(stop|cancel|quit|exit|end)\s*[.!]?\s*$",
    r"^\s*i\s+want\s+to\s+(?:stop|end)(?:\s+(?:this|the)?\s*interview)?\s*[.!]?\s*$",
    r"^\s*let'?s\s+stop\s*[.!]?\s*$",
    r"^\s*that'?s\s+enough\s*[.!]?\s*$",
]


def _is_interview_exit(message):

    text = (message or "").lower()

    return any(re.search(p, text) for p in _INTERVIEW_EXIT_PATTERNS)


# "know move to next question" / "skip this one" / "next question please" -
# a request to move PAST the current question, not an attempt at a real
# answer. Without this, a garbled or unsure skip attempt gets recorded and
# scored as the candidate's actual answer - exactly what happened in a real
# report: "know move to next question" (almost certainly a typo for "ok,
# move to next question") was scored as a near-zero technical/communication
# answer, when the candidate never actually tried to answer the question
# at all.

_INTERVIEW_SKIP_PATTERNS = [
    r"\bskip\b", r"\bpass\b.*question", r"\bnext\s+question\b",
    r"\bmove\s+(?:on\s+)?to\s+(?:the\s+)?next\b",
    r"\bi\s+don'?t\s+(?:want|wanna)\s+to\s+answer\b",
    r"\bcan'?t\s+answer\s+this\b",
]

MIN_MOCK_INTERVIEW_QUESTIONS = int(os.getenv("MIN_MOCK_INTERVIEW_QUESTIONS", "4"))


def _is_interview_skip(message):

    text = (message or "").lower()

    return any(re.search(p, text) for p in _INTERVIEW_SKIP_PATTERNS)


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

    skipped = _is_interview_skip(message)

    if turns and turns[-1].get("answer") is None:

        turns[-1]["answer"] = (
            "(the candidate chose to skip this question without answering)"
            if skipped else message
        )

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

        answered_count = sum(1 for t in turns if t.get("answer") is not None)

        if answered_count < MIN_MOCK_INTERVIEW_QUESTIONS:

            # The prompt already tells the model not to end this early,
            # but a prompt is a strong nudge, not a guarantee - this is
            # the real bug a live report caught: the model ended the
            # whole interview after a single skipped question, scoring
            # it 10/100 off almost nothing. Enforced in CODE here as a
            # hard backstop: ask it again, this time with no
            # end_interview tool even offered, so ending early is not
            # an option it can choose regardless of its own judgment.

            print(
                f"[chatbot] mock interview tried to end after only "
                f"{answered_count} answered question(s) - enforcing the "
                f"{MIN_MOCK_INTERVIEW_QUESTIONS}-question minimum in code"
            )

            try:

                next_question = _call_groq_plain(
                    messages + [{
                        "role": "user",
                        "content": (
                            "Continue the interview - ask the next "
                            "question now. Do not end the interview yet."
                        ),
                    }]
                ).strip()

            except Exception as e:

                print("Mock interview forced-continue error:", e)

                return _finish_mock_interview(session, turns)

            if not next_question:

                return _finish_mock_interview(session, turns)

            turns.append({"question": next_question, "answer": None})

            session.turns = turns

            session.save()

            return {"reply": next_question}

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


def _tool_get_career_plan(profile, user, args):
    """
    A full placement readiness snapshot in ONE tool call, combining
    what would otherwise take 3-4 separate questions: resume score
    and gaps, top in-demand skills the student is missing, the best
    currently-matching unapplied jobs, and a summary of where their
    real applications/interviews stand. Returned together so the
    model can build a single prioritized, cross-referenced action
    plan (see the CAREER PLAN guidance in SYSTEM_TEMPLATE) instead of
    a disconnected list of facts.
    """

    from collections import Counter

    from jobsystem.models import Resume, Job, Application, Interview
    from jobsystem.services.job_matching import rank_jobs_for_student

    # ---- Resume (official saved score - same as Resume page) ----

    resume = Resume.objects.filter(
        student=user, is_active=True
    ).first()

    resume_data = None

    if resume:

        resume_data = {
            "score": resume.resume_score,
            "missing_information": resume.missing_information,
        }

    # ---- Skill gap (in-demand skills the student doesn't have) ----

    active_jobs = Job.objects.filter(status="active", is_active=True)[:50]

    student_skills = set(
        s.strip().lower()
        for s in (getattr(profile, "skills", "") or "").split(",")
        if s.strip()
    )

    missing_counter = Counter()

    for job in active_jobs:

        for skill in (job.skills_required or "").split(","):

            skill = skill.strip()

            if skill and skill.lower() not in student_skills:

                missing_counter[skill] += 1

    top_missing_skills = [
        skill for skill, _ in missing_counter.most_common(6)
    ]

    # ---- Top unapplied job matches ----

    applied_job_ids = set(
        Application.objects.filter(
            student=profile
        ).values_list("job_id", flat=True)
    )

    candidate_jobs = Job.objects.filter(
        status="active", is_active=True
    ).exclude(id__in=applied_job_ids).select_related("company")[:40]

    ranked = rank_jobs_for_student(profile, candidate_jobs)[:3]

    top_matches = [
        _serialize_matched_job(job, score, reasons, already_applied=False)
        for job, score, reasons in ranked
    ]

    # ---- Application / interview status ----

    applications = Application.objects.filter(student=profile)

    upcoming_interview = Interview.objects.filter(
        application__student=profile,
        interview_date__gte=timezone.now(),
        status__in=["scheduled", "rescheduled"],
    ).select_related(
        "application__job", "application__job__company"
    ).order_by("interview_date").first()

    next_interview_info = None

    if upcoming_interview:

        next_interview_info = {
            "job_title": upcoming_interview.application.job.title,
            "company": (
                upcoming_interview.application.job.company.company_name
                if upcoming_interview.application.job.company else ""
            ),
            "date": _to_india_time(upcoming_interview.interview_date).strftime("%b %d, %Y"),
        }

    return {
        "resume": resume_data,
        "top_missing_skills": top_missing_skills,
        "top_job_matches": top_matches,
        "matched_jobs": top_matches,
        "total_applied": applications.count(),
        "interview_stage_count": applications.filter(status="interview").count(),
        "selected_count": applications.filter(status="selected").count(),
        "next_interview": next_interview_info,
        "profile_completion": getattr(profile, "profile_completion", 0),
        "navigate_to": "/student/dashboard",
        "summary": "Full placement readiness snapshot compiled.",
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "find_matching_jobs",
            "description": (
                "Two different uses. (1) DEFAULT - jobs for THIS student: "
                "the open jobs they can actually apply to right now, best "
                "skill match first. Use when they ask to find, search, see "
                "or get suitable / recommended / matching jobs for "
                "themselves or their profile. Only jobs they are eligible "
                "for and have not applied to come back as cards; jobs left "
                "out are named in the summary, so never describe an "
                "excluded job as suitable. (2) recent_only=true - what was "
                "NEW on the platform: a plain list of recently posted jobs "
                "they haven't applied to, newest first, NOT filtered by "
                "their profile. Use when they ask for new / latest / "
                "recently posted jobs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recent_only": {
                        "type": "boolean",
                        "description": (
                            "Set true when the student asks about NEW, "
                            "latest, newly posted or recently added jobs - "
                            "returns a plain list of postings from the last "
                            "two weeks that they haven't applied to, newest "
                            "first, without checking their profile. Leave "
                            "false/omitted for 'find jobs for me' or 'jobs "
                            "that match my profile'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "How many jobs to return (1-5). Use 1 when "
                            "the student asks which ONE job is best / "
                            "most preferred / most suitable / what to "
                            "apply to first; use 3 for 'top jobs'. "
                            "Omit for a general 'find jobs for me' "
                            "request (returns up to 5)."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_open_jobs",
            "description": (
                "The whole Jobs tab: EVERY open job, best match first, "
                "including ones the student is not eligible for or has "
                "already applied to - each card is marked so. Use when they "
                "ask to see ALL jobs, the list of jobs, the jobs tab, what "
                "jobs are available/open, or say 'even if I'm not eligible'. "
                "Not for 'jobs for me / that match my profile' "
                "(find_matching_jobs) or 'new jobs' (find_matching_jobs with "
                "recent_only)."
                "Also supports filtering to one named company (e.g. "
                "\"show me TechNova's posted jobs\") via company_name, or "
                "one named technology/skill (e.g. \"show me python jobs\", "
                "\"django jobs\") via keyword."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Filter to jobs from this company, if the student named one (e.g. 'TechNova').",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Filter to jobs matching this technology/skill/term, if the student named one (e.g. 'python', 'django', 'react').",
                    },
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
                "List the open jobs the student is eligible for and "
                "hasn't applied to yet, based on their profile (CGPA, "
                "department, backlogs, etc). Use ONLY for a general "
                "'which jobs am I eligible for' question - never when "
                "the student names one specific job and wants to apply "
                "to it (use apply_to_job for that). Jobs left out "
                "(already applied / not eligible) are named in the "
                "summary."
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
                "asks what skills to improve or learn - pass job_role "
                "when they named a specific target role ('skills for "
                "Python Developer'), so the answer is scoped to real "
                "demand for THAT role, not the whole platform; omit "
                "it when they asked generally with no role named."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_role": {
                        "type": "string",
                        "description": "The target role the student named, if any (e.g. 'Python Developer', 'Data Analyst').",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": (
                "General information about a company - industry, "
                "description, size, how many jobs they have open "
                "right now. Use for 'tell me about <company>'/'what "
                "does <company> do' style questions. For skills "
                "needed at that company's jobs specifically, use "
                "get_company_skill_gap instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name the student asked about.",
                    }
                },
                "required": ["company_name"],
            },
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
                "Start an application for the student to a specific "
                "open job. This only asks the student to confirm "
                "(Yes / No buttons) - it never submits by itself. "
                "Only use when the student explicitly asks to apply "
                "to a named job, or says yes to applying to a job "
                "you just showed. Pass ONLY the job title in "
                "job_title (e.g. \"Software Tester\") and the company "
                "in company_name - never join them into one string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "Just the job title, e.g. \"Software Tester\" - without the company name.",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "The company offering the job, if known (e.g. from a job card you showed).",
                    },
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
                "their statuses. Any application with a real upcoming "
                "interview also returns its date/time/mode and that "
                "job's required skills (regardless of the "
                "application's own status label) - after showing "
                "this, proactively offer role-and-company-specific "
                "interview prep. For a general question about "
                "interview status/schedule/updates ('any interview "
                "updates', 'when is my interview'), prefer "
                "get_upcoming_interviews instead - it is the "
                "authoritative source."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_interviews",
            "description": (
                "Get the student's upcoming scheduled interviews - the "
                "authoritative source for any interview status/"
                "schedule/update question ('any interview updates', "
                "'do I have interviews', 'when is my interview'). Use "
                "this rather than get_application_status for these, "
                "since a real scheduled interview can exist even when "
                "the linked application's own status says something "
                "else (e.g. 'Selected' or 'Shortlisted')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "this_week": {
                        "type": "boolean",
                        "description": "True only if the student specifically asked about interviews this week.",
                    },
                    "today": {
                        "type": "boolean",
                        "description": "True only if the student specifically asked about interviews today (e.g. 'any interview today', 'do I have an interview scheduled today').",
                    },
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
                "skills, description) to generate genuinely tailored "
                "preparation suggestions or practice questions - not "
                "generic advice. Use when the student asks how to "
                "prepare for an interview OR to prepare for/study for "
                "a job they've applied to, even with no interview "
                "scheduled yet - it falls back to the real application "
                "in that case, so never refuse this just because "
                "nothing is booked yet. If it finds NOTHING (the "
                "student is asking about a role type they've never "
                "applied to or interviewed for - e.g. 'Data Analyst' "
                "when they've only ever applied to Software Tester "
                "roles), that is NOT a dead end: still give genuinely "
                "useful general preparation advice for that role type "
                "from your own knowledge - common interview questions, "
                "key skills to highlight, what interviewers typically "
                "look for. Never just report that nothing was found "
                "and stop there."
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
            "description": (
                "Get the student's official resume score (the same "
                "score shown on the Resume page) and suggestions for "
                "improving it - reads from what was already saved at "
                "upload time, so this is instant and free. Use for ANY "
                "general question about the resume score or how to "
                "improve/raise/build it - this is the DEFAULT choice "
                "for that. Prefer this over check_ats_friendliness "
                "unless the student specifically says ATS / Applicant "
                "Tracking System / parsing - check_ats_friendliness "
                "needs a fresh, costly AI call every single time, "
                "while this one never does."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_ats_friendliness",
            "description": (
                "Check the student's resume SPECIFICALLY for ATS "
                "(Applicant Tracking System) parsing problems - only "
                "use when the student explicitly mentions ATS, "
                "Applicant Tracking Systems, or resume parsing. For a "
                "general 'how do I improve my resume' or 'raise my "
                "score' question with no ATS mention, use "
                "get_resume_feedback instead - it answers instantly "
                "from already-saved data, while this tool requires a "
                "fresh, costly AI call every time it runs. Optionally "
                "checked against a specific target job role. Returns "
                "the official resume score plus ATS issues/suggestions "
                "- it does not produce a "
                "separate score. Your answer MUST list the actual "
                "issues and suggestions returned (not just how many "
                "there are) - a bare count answers nothing and forces "
                "a needless, costly re-check the moment the student "
                "asks a natural follow-up like 'what are the issues?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_role": {
                        "type": ["string", "null"],
                        "description": "The job role to check the resume against, if the student mentioned one - omit or send null otherwise.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_resume",
            "description": (
                "Generate an improved, rewritten version of the "
                "student's resume content as text, addressing the real "
                "gaps already found in it. This only shows a proposed "
                "version in chat for the student to review - it never "
                "replaces their actual uploaded file. Use when the "
                "student asks to rewrite, improve, or get a better "
                "version of their resume content."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
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
            "name": "get_career_plan",
            "description": (
                "Get a full placement readiness snapshot in one "
                "call - resume score/gaps, top missing skills, best "
                "current job matches, and application/interview "
                "status - to build ONE prioritized, cross-referenced "
                "action plan. Use for broad requests like 'help me "
                "get placed', 'what should I do next', 'give me a "
                "career plan', or 'how am I doing overall' - prefer "
                "this over calling several separate tools when the "
                "student's question is this broad."
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
            "name": "update_my_projects",
            "description": (
                "Add one or more new projects directly to the "
                "student's profile. Only use when the student "
                "explicitly asks to add a project to their profile - "
                "never as a side effect of a general conversation "
                "about projects. Your answer stays in the chat - "
                "never tell the student their profile page opened, "
                "since it doesn't."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "projects": {
                        "type": "string",
                        "description": "The project name/description to add, exactly as the student described it. Multiple projects may be separated with newlines.",
                    }
                },
                "required": ["projects"],
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
    "list_open_jobs": _tool_list_open_jobs,
    "check_job_eligibility": _tool_check_job_eligibility,
    "get_job_details": _tool_get_job_details,
    "get_skill_suggestions": _tool_get_skill_suggestions,
    "get_company_info": _tool_get_company_info,
    "get_company_skill_gap": _tool_get_company_skill_gap,
    "apply_to_job": _tool_apply_to_job,
    "get_application_status": _tool_get_application_status,
    "get_upcoming_interviews": _tool_get_upcoming_interviews,
    "get_interview_prep": _tool_get_interview_prep,
    "get_resume_feedback": _tool_get_resume_feedback,
    "check_ats_friendliness": _tool_check_ats_friendliness,
    "get_resume_download_link": _tool_get_resume_download_link,
    "get_my_profile": _tool_get_my_profile,
    "get_career_plan": _tool_get_career_plan,
    "rewrite_resume": _tool_rewrite_resume,
    "update_my_skills": _tool_update_my_skills,
    "update_my_projects": _tool_update_my_projects,
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

    if results:

        lines = [
            f"- {c['name']} ({c['course'] or 'course not set'}, "
            f"CGPA {c['cgpa'] if c['cgpa'] is not None else 'N/A'})"
            for c in results[:8]
        ]

        summary = (
            f"Found {len(results)} matching student profile(s):\n\n"
            + "\n".join(lines)
        )

    else:

        summary = "No matching student profiles found."

    return {
        "candidates": results,
        "navigate_to": "/company/candidates",
        "summary": summary,
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

    if scored:

        lines = [
            f"- {c['name']} ({c['match_score']}% match): {c['status']}"
            for c in scored[:8]
        ]

        summary = (
            f"Top applicants for {job.title}:\n\n" + "\n".join(lines)
        )

    else:

        summary = f"No applicants yet for {job.title}."

    return {
        "candidates": scored[:10],
        "job_title": job.title,
        "navigate_to": "/company/candidates",
        "summary": summary,
    }


def _tool_get_duplicate_candidate_names(profile, user, args):
    """
    Groups the company's recent applications by candidate name and
    surfaces any name that appears more than once. This is purely a
    grouping/counting operation on already-fetched data - detecting a
    repeated name never needed live AI reasoning to begin with, it's
    a Python-level computation, same as counting applications or
    listing job titles.

    Crucially distinguishes the two very different things a repeated
    name can mean: the SAME student applying to several jobs (normal,
    not a real "duplicate") versus two DIFFERENT students who simply
    share a name (a genuine thing a recruiter needs to know, since
    treating them as one person risks shortlisting/rejecting the
    wrong applicant). Compared by student_id, not just the name text.
    """

    from jobsystem.models import Application
    from collections import defaultdict

    apps = Application.objects.filter(
        job__company=profile
    ).select_related("student", "job").order_by("-applied_date")[:50]

    by_name = defaultdict(list)

    for app in apps:

        by_name[app.student.full_name].append(app)

    duplicate_groups = {
        name: entries
        for name, entries in by_name.items()
        if len(entries) > 1
    }

    if not duplicate_groups:

        return {
            "duplicate_candidates": [],
            "summary": "No two applicants currently share the same name.",
        }

    lines = []

    payload_groups = []

    for name, entries in duplicate_groups.items():

        distinct_student_ids = set(e.student_id for e in entries)

        same_person = len(distinct_student_ids) == 1

        note = (
            "same applicant, multiple jobs"
            if same_person else
            "DIFFERENT applicants - same name only"
        )

        job_list = ", ".join(
            f"{e.job.title} ({e.get_status_display()})" for e in entries
        )

        lines.append(f"- {name} ({note}): {job_list}")

        payload_groups.append({
            "name": name,
            "same_person": same_person,
            "applications": [
                {"job_title": e.job.title, "status": e.get_status_display()}
                for e in entries
            ],
        })

    summary = (
        f"{len(duplicate_groups)} name(s) appear more than once:\n\n"
        + "\n".join(lines[:8])
    )

    return {
        "duplicate_candidates": payload_groups,
        "navigate_to": "/company/candidates",
        "summary": summary,
    }


def _tool_get_job_description(profile, user, args):
    """
    Full detail for one (or a few) of the company's OWN job
    postings - description, requirements, skills, qualification,
    experience, salary, location - not just a title+application-count
    row the way get_active_job_postings/list_all_job_postings give.
    Use whenever the recruiter asks to see/describe/review what a
    job posting actually SAYS, not just which postings exist or how
    many applied to them.

    Matched by keyword, not an exact title match: a recruiter's own
    phrasing of a role ("the software developer jobs") very often
    doesn't literally appear in the real posting title ("Junior
    Python Full Stack Developer", "Senior Frontend Developer") -
    splitting the query into significant words and matching ANY of
    them against the title catches this, where an exact substring
    match would silently return nothing.
    """

    from django.db.models import Q
    from jobsystem.models import Job

    query = (args.get("job_title") or "").strip()

    jobs_qs = Job.objects.filter(company=profile)

    if query:

        stopwords = {
            "the", "a", "an", "job", "jobs", "posting", "postings",
            "role", "roles", "position", "positions", "for", "of",
        }

        words = [
            w for w in re.split(r"\s+", query.lower())
            if len(w) > 2 and w not in stopwords
        ]

        if words:

            word_filter = Q()

            for w in words:

                word_filter |= Q(title__icontains=w)

            jobs_qs = jobs_qs.filter(word_filter)

    jobs = list(jobs_qs.order_by("-created_at")[:5])

    if not jobs:

        return {
            "jobs": [],
            "summary": (
                f"No job posting found matching \"{query}\"."
                if query else
                "No job postings found."
            ),
        }

    data = []

    blocks = []

    for job in jobs:

        status_label = (
            job.get_status_display()
            if hasattr(job, "get_status_display") else job.status
        )

        skills = job.skills_required or "Not specified"

        data.append({
            "title": job.title,
            "status": status_label,
            "description": job.description or "",
            "requirements": job.requirements or "",
            "skills_required": skills,
            "qualification_required": job.qualification_required or "",
            "experience_required": job.experience_required or "",
            "salary": job.salary or "",
            "location": job.location or "",
        })

        blocks.append(
            f"**{job.title}** ({status_label})\n"
            f"Location: {job.location or 'Not specified'} | "
            f"Salary: {job.salary or 'Not disclosed'} | "
            f"Experience: {job.experience_required or 'Not specified'}\n"
            f"Skills: {skills}\n"
            f"Description: {job.description or 'No description given'}"
        )

    return {
        "jobs": data,
        "navigate_to": "/company/jobs",
        "summary": "\n\n".join(blocks),
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

    if data:

        lines = [
            f"- {a['candidate']} ({a['job_title']}): {a['status']}"
            for a in data[:8]
        ]

        summary = (
            f"{len(data)} recent application(s):\n\n" + "\n".join(lines)
        )

    else:

        summary = "No applications received yet."

    return {
        "applications": data,
        "navigate_to": "/company/candidates",
        "summary": summary,
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
            "date": _to_india_time(iv.interview_date).strftime("%b %d, %Y"),
            "time": _to_india_time(iv.interview_date).strftime("%I:%M %p"),
        }
        for iv in interviews
    ]

    if data:

        lines = [
            f"- {iv['candidate']} ({iv['job_title']}): "
            f"{iv['date']} at {iv['time']}"
            for iv in data[:8]
        ]

        summary = (
            f"{len(data)} upcoming interview(s):\n\n" + "\n".join(lines)
        )

    else:

        summary = "No upcoming interviews scheduled."

    return {
        "interviews": data,
        "navigate_to": "/company/interviews",
        "summary": summary,
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

    if data:

        lines = [
            f"- {j['title']}: {j['applications']} application(s)"
            for j in data[:8]
        ]

        summary = (
            f"{len(data)} active job posting(s):\n\n" + "\n".join(lines)
        )

    else:

        summary = "No active job postings right now."

    return {
        "jobs": data,
        "navigate_to": "/company/jobs",
        "summary": summary,
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

    if data:

        lines = [
            f"- {j['title']} ({j['status']}): {j['applications']} application(s)"
            for j in data[:8]
        ]

        summary = (
            f"{len(data)} job posting(s) total:\n\n" + "\n".join(lines)
        )

    else:

        summary = "No jobs posted yet."

    return {
        "jobs": data,
        "navigate_to": "/company/jobs",
        "summary": summary,
    }


def _tool_get_company_analytics_summary(profile, user, args):

    from jobsystem.models import Job, Application, Interview

    jobs_qs = Job.objects.filter(company=profile)

    applications_qs = Application.objects.filter(job__company=profile)

    interviews_qs = Interview.objects.filter(
        application__job__company=profile
    )

    total_jobs_posted = jobs_qs.count()

    active_jobs = jobs_qs.filter(status="active").count()

    total_applications = applications_qs.count()

    interviews_scheduled = interviews_qs.filter(status="scheduled").count()

    hired_candidates = applications_qs.filter(status="selected").count()

    return {
        "total_jobs_posted": total_jobs_posted,
        "active_jobs": active_jobs,
        "total_applications": total_applications,
        "interviews_scheduled": interviews_scheduled,
        "hired_candidates": hired_candidates,
        "navigate_to": "/company/analytics",
        "summary": (
            f"{total_jobs_posted} job(s) posted ({active_jobs} active), "
            f"{total_applications} total application(s), "
            f"{interviews_scheduled} interview(s) scheduled, "
            f"{hired_candidates} candidate(s) hired."
        ),
    }


# =====================================================
# CANDIDATE ACTIONS - shortlisting/rejecting from chat, always
# confirmed by the recruiter first (mirrors the student apply flow's
# safety pattern: the AI can only PREPARE a question with Yes/No
# buttons; the actual status change happens in a separate,
# deterministic step that never depends on the AI's own judgment).
# =====================================================

def _resolve_application_for_candidate_action(company_profile, candidate_name, job_title):
    """The one open Application this company owns matching a candidate
    name + job title, or None if it can't be resolved unambiguously."""

    from jobsystem.models import Application

    name = (candidate_name or "").strip()

    title = (job_title or "").strip()

    if not name or not title:

        return None

    exact = Application.objects.filter(
        job__company=company_profile,
        job__title__iexact=title,
        student__full_name__iexact=name,
    ).select_related("student", "job").first()

    if exact:

        return exact

    # fall back to a looser match (the AI may paraphrase slightly) -
    # only used if it resolves to exactly one application

    loose = list(Application.objects.filter(
        job__company=company_profile,
        job__title__icontains=title,
        student__full_name__icontains=name,
    ).select_related("student", "job"))

    return loose[0] if len(loose) == 1 else None


def _set_candidate_status(company_profile, application, new_status):
    """The one place a candidate's status is actually changed from
    chat. Mirrors CompanyApplicationStatusView's own notification
    dispatch, so a chat-driven change behaves identically to one made
    from the Candidates page."""

    application.status = new_status

    application.save()

    status_to_event = {"shortlisted": "shortlisted", "rejected": "rejected"}

    event_key = status_to_event.get(new_status)

    if event_key:

        try:

            from jobsystem.services.notification_engine import dispatch

            dispatch(
                event_key,
                application.student.user,
                {
                    "job_title": application.job.title,
                    "company_name": company_profile.company_name,
                },
            )

        except Exception as e:

            print("Chatbot candidate-status notification error:", e)

    return {
        "success": True,
        "summary": (
            f"{application.student.full_name} has been {new_status} "
            f"for {application.job.title}. They've been notified."
        ),
    }


def _prepare_candidate_action(company_profile, candidate_name, job_title, action, verb):
    """PREPARE step only for shortlist/reject - never writes anything.
    Returns a confirmation question with Yes/No buttons."""

    if not (candidate_name or "").strip() or not (job_title or "").strip():

        return {
            "summary": "Which candidate and which job? Please name both."
        }

    application = _resolve_application_for_candidate_action(
        company_profile, candidate_name, job_title
    )

    if not application:

        return {
            "summary": (
                f"I couldn't find an application from \"{candidate_name}\" "
                f"for \"{job_title}\". Check the exact name and job title "
                "on the Candidates page."
            )
        }

    if application.status == action:

        return {
            "summary": (
                f"{application.student.full_name} is already {action} "
                f"for {application.job.title}."
            )
        }

    if application.status == "selected" and action == "rejected":

        return {
            "summary": (
                f"{application.student.full_name} has already been "
                f"selected for {application.job.title}."
            )
        }

    confirm_text = (
        f"Yes, {verb} {application.student.full_name} "
        f"for {application.job.title}"
    )

    return {
        "needs_confirmation": True,
        "quick_replies": [confirm_text, "No, cancel"],
        "summary": (
            f"{verb.capitalize()} {application.student.full_name} for "
            f"{application.job.title}? Tap Yes to confirm."
        ),
    }


def _tool_shortlist_candidate(profile, user, args):

    return _prepare_candidate_action(
        profile,
        args.get("candidate_name"),
        args.get("job_title"),
        action="shortlisted",
        verb="shortlist",
    )


def _tool_reject_candidate(profile, user, args):

    return _prepare_candidate_action(
        profile,
        args.get("candidate_name"),
        args.get("job_title"),
        action="rejected",
        verb="reject",
    )


_CONFIRM_SHORTLIST_RE = re.compile(
    r"^\s*yes,?\s+shortlist\s+(?P<name>.+?)\s+for\s+(?P<job>.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_CONFIRM_REJECT_RE = re.compile(
    r"^\s*yes,?\s+reject\s+(?P<name>.+?)\s+for\s+(?P<job>.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_CANCEL_CANDIDATE_RE = re.compile(r"^\s*no,?\s+cancel\s*[.!]?\s*$", re.IGNORECASE)


def _handle_candidate_action_confirmation(company_profile, user, message):
    """
    Deterministic handler for the Yes / No buttons after a shortlist or
    reject confirmation. Returns a reply dict, or None if the message
    is not one of these (so the normal AI flow continues). The actual
    status change happens ONLY here, never from the AI's own judgment.
    """

    text = message or ""

    if _CANCEL_CANDIDATE_RE.match(text):

        return {
            "reply": "Okay, no changes made. Let me know if you'd like anything else."
        }

    for pattern, new_status in (
        (_CONFIRM_SHORTLIST_RE, "shortlisted"),
        (_CONFIRM_REJECT_RE, "rejected"),
    ):

        match = pattern.match(text)

        if not match:

            continue

        application = _resolve_application_for_candidate_action(
            company_profile, match.group("name"), match.group("job")
        )

        if not application:

            return {
                "reply": (
                    "I couldn't find that application any more. Ask me "
                    "to show the candidates again."
                )
            }

        # Guards against a duplicate tap (e.g. a stale button still on
        # screen after a refresh) silently re-sending the notification.

        if application.status == new_status:

            return {
                "reply": (
                    f"{application.student.full_name} is already "
                    f"{new_status} for {application.job.title}."
                )
            }

        result = _set_candidate_status(company_profile, application, new_status)

        payload = {"reply": result["summary"]}

        if result.get("success"):

            payload["refresh"] = ["candidates"]

        return payload

    return None


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
        "summary": (
            f"{profile.company_name} - "
            f"{profile.industry or 'industry not set'}. "
            f"{'Verified' if profile.verified else 'Not yet verified'}, "
            f"approval status: {profile.approval_status}."
        ),
    }


def _tool_raise_company_query(profile, user, args):
    """
    A company raising a question to the placement admin team - a new
    capability (CompanyQuery is a new model; the existing
    PlacementQuery is student-specific and has no company/answer
    fields at all, confirmed directly against the real models.py).
    Mirrors _tool_raise_placement_query's style on the student side.
    """

    from jobsystem.models import CompanyQuery, Job

    subject = (args.get("subject") or "").strip()

    question_text = (args.get("question_text") or "").strip()

    job_title = (args.get("related_job_title") or "").strip()

    if not subject or len(question_text) < 5:

        return {
            "success": False,
            "summary": (
                "I can raise this with the placement team - what's a short "
                "subject line, and what would you like to ask?"
            ),
        }

    related_job = None

    if job_title:

        title_q = _job_role_strict_match_q("title", job_title)

        if title_q is not None:

            related_job = Job.objects.filter(
                title_q, company=profile
            ).first()

    query = CompanyQuery.objects.create(
        company=profile,
        subject=subject,
        question_text=question_text,
        related_job=related_job,
        source="chatbot",
    )

    return {
        "success": True,
        "query_id": query.id,
        "summary": (
            f"Question raised as CQ-{query.id}: \"{subject}\" - the "
            "placement team will respond soon. You can ask me "
            f"\"has CQ-{query.id} been answered\" to check later."
        ),
    }


def _tool_get_my_company_queries(profile, user, args):
    """
    A company checking its own previously raised questions and any
    saved admin answers. Scoped to the authenticated company's own
    records only (profile is the authenticated CompanyProfile, never
    a company_id trusted from the message/LLM arguments).
    """

    from jobsystem.models import CompanyQuery

    status_filter = (args.get("status") or "").strip().lower()

    qs = CompanyQuery.objects.filter(company=profile).order_by("-created_at")

    if status_filter in {"pending", "in_review", "answered", "closed"}:

        qs = qs.filter(status=status_filter)

    queries = list(qs[:15])

    if not queries:

        summary = (
            f"No {status_filter} questions found." if status_filter
            else "You haven't raised any questions yet."
        )

        return {"queries": [], "summary": summary}

    lines = []

    for q in queries:

        line = f"- CQ-{q.id}: {q.subject} ({q.get_status_display()})"

        if q.status == "answered" and q.admin_answer:

            line += f"\n  Answer: {q.admin_answer}"

        lines.append(line)

    return {
        "queries": [
            {
                "id": q.id,
                "subject": q.subject,
                "status": q.get_status_display(),
                "answer": q.admin_answer or None,
            }
            for q in queries
        ],
        "summary": f"{len(queries)} question(s):\n\n" + "\n".join(lines),
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
            "name": "get_duplicate_candidate_names",
            "description": (
                "Find candidates whose name appears more than once "
                "among recent applicants, and clarify whether it's "
                "the SAME student applying to several jobs, or "
                "DIFFERENT students who happen to share a name. Use "
                "when the recruiter asks about duplicate/same-name "
                "candidates."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_description",
            "description": (
                "Get the FULL content of one of the company's own "
                "job postings - description, requirements, skills, "
                "qualification, experience, salary, location. Use "
                "when the recruiter asks to describe/see/review what "
                "a job posting actually says - get_active_job_postings "
                "and list_all_job_postings only give a title and "
                "application count, never the actual content, so "
                "prefer THIS tool whenever the real text is wanted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job title or role the recruiter named, exactly as they said it - matched by keyword, not an exact title.",
                    }
                },
                "required": [],
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
            "description": (
                "Lists titles and application counts only - NOT the "
                "posting's actual description/requirements/skills. "
                "For that, use get_job_description instead. Get the "
                "company's currently active job postings and how "
                "many applications each has."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_job_postings",
            "description": (
                "Lists titles, status and application counts only - "
                "NOT the posting's actual description/requirements/ "
                "skills. For that, use get_job_description instead. "
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
    {
        "type": "function",
        "function": {
            "name": "shortlist_candidate",
            "description": (
                "Start shortlisting a candidate for one of the "
                "company's jobs. This only asks the recruiter to "
                "confirm (Yes / No buttons) - it never shortlists by "
                "itself. Use when the recruiter asks to shortlist a "
                "named candidate for a named job, or agrees to "
                "shortlist someone just shown in a candidate list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_name": {
                        "type": "string",
                        "description": "The candidate's full name, exactly as shown.",
                    },
                    "job_title": {
                        "type": "string",
                        "description": "The job they applied to.",
                    },
                },
                "required": ["candidate_name", "job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_candidate",
            "description": (
                "Start rejecting a candidate's application for one "
                "of the company's jobs. This only asks the recruiter "
                "to confirm (Yes / No buttons) - it never rejects by "
                "itself. Use when the recruiter asks to reject a "
                "named candidate for a named job."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_name": {
                        "type": "string",
                        "description": "The candidate's full name, exactly as shown.",
                    },
                    "job_title": {
                        "type": "string",
                        "description": "The job they applied to.",
                    },
                },
                "required": ["candidate_name", "job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "raise_company_query",
            "description": (
                "Raise a question/issue to the Placement Admin team on "
                "behalf of the authenticated company - e.g. a deadline "
                "extension request, a question about a drive or job "
                "posting. Only call when the company clearly asked to "
                "raise/submit a question and you have both a subject "
                "and the actual question text - ask for whichever is "
                "missing rather than inventing one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "A short subject line for the question.",
                    },
                    "question_text": {
                        "type": "string",
                        "description": "The actual question or issue, in the company's own words.",
                    },
                    "related_job_title": {
                        "type": "string",
                        "description": "This company's own job the question relates to, if any.",
                    },
                },
                "required": ["subject", "question_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_company_queries",
            "description": (
                "Get the authenticated company's own previously raised "
                "questions, their status, and any saved admin answer. "
                "Use for 'show my questions', 'has CQ-102 been "
                "answered', 'what's the status of my question'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "pending/in_review/answered/closed, if the company asked for a specific status.",
                    }
                },
                "required": [],
            },
        },
    },
]


COMPANY_TOOL_EXECUTORS = {
    "raise_company_query": _tool_raise_company_query,
    "get_my_company_queries": _tool_get_my_company_queries,
    "get_duplicate_candidate_names": _tool_get_duplicate_candidate_names,
    "get_job_description": _tool_get_job_description,
    "search_candidates": _tool_search_candidates,
    "get_top_candidates_for_job": _tool_get_top_candidates_for_job,
    "get_company_applications": _tool_get_company_applications,
    "get_company_interviews": _tool_get_company_interviews,
    "get_active_job_postings": _tool_get_active_job_postings,
    "list_all_job_postings": _tool_list_all_job_postings,
    "get_company_analytics_summary": _tool_get_company_analytics_summary,
    "get_company_profile_info": _tool_get_company_profile_info,
    "shortlist_candidate": _tool_shortlist_candidate,
    "reject_candidate": _tool_reject_candidate,
}

# =====================================================
# PLACEMENT ADMIN TOOLS - read-only for now. Grounded in the same
# queries the real Placement admin pages already use (Dashboard,
# Companies, Students, Drives, Company History, Reports, Candidate
# Pipeline), just trimmed to what fits a chat answer. No write
# actions yet (approving a company, verifying a student, etc.) -
# those need the same Yes/No confirmation pattern already used for
# student applications and company shortlist/reject, added
# separately once this read-only layer is proven.
# =====================================================

def _tool_get_placement_overview(profile, user, args):

    from jobsystem.models import (
        StudentProfile, CompanyProfile, Job, Application, PlacementDrive,
    )

    total_students = StudentProfile.objects.count()

    total_companies = CompanyProfile.objects.count()

    active_jobs = Job.objects.filter(status="active").count()

    total_applications = Application.objects.count()

    placed = Application.objects.filter(
        status="selected"
    ).values("student").distinct().count()

    placement_pct = (
        round((placed / total_students) * 100, 1) if total_students else 0
    )

    active_drives = PlacementDrive.objects.filter(
        status__in=["upcoming", "ongoing"]
    ).count()

    return {
        "total_students": total_students,
        "total_companies": total_companies,
        "active_jobs": active_jobs,
        "total_applications": total_applications,
        "placed_students": placed,
        "placement_percentage": placement_pct,
        "active_drives": active_drives,
        "navigate_to": "/placement/dashboard",
        "summary": (
            f"{placed} of {total_students} students placed "
            f"({placement_pct}%). {total_companies} companies, "
            f"{active_jobs} active jobs, {active_drives} active drive(s)."
        ),
    }


def _tool_get_pending_company_approvals(profile, user, args):

    from jobsystem.models import CompanyProfile

    pending = CompanyProfile.objects.filter(
        approval_status="pending"
    ).order_by("-created_at")[:15]

    data = [
        {
            "company_name": c.company_name,
            "industry": c.industry,
            "submitted_on": str(c.created_at),
        }
        for c in pending
    ]

    if data:

        lines = [
            f"- {c['company_name']} ({c['industry'] or 'industry not set'})"
            for c in data[:8]
        ]

        summary = (
            f"{len(data)} compan{'y' if len(data) == 1 else 'ies'} "
            "awaiting approval:\n\n" + "\n".join(lines)
        )

    else:

        summary = "No companies are awaiting approval right now."

    return {
        "companies": data,
        "navigate_to": "/placement/companies",
        "summary": summary,
    }


def _tool_list_students(profile, user, args):
    """
    A general, ALL-students roster - not scoped to only unverified
    ones the way get_unverified_students is. "give me students
    name"/"show me students" had nothing to call before this, so the
    model could only give a vague refusal instead of real names, even
    though the exact same data already backs the real Students page
    and Candidate Pipeline.
    """

    from jobsystem.models import StudentProfile

    students = StudentProfile.objects.all().order_by("-id")[:15]

    data = [
        {
            "full_name": s.full_name,
            "department": s.department,
            "verified": s.verified,
            "placement_status": s.placement_status,
        }
        for s in students
    ]

    if not data:

        return {"students": [], "summary": "No students registered yet."}

    lines = [
        f"- {s['full_name']} ({s['department'] or 'department not set'}): "
        f"{s['placement_status']}"
        + ("" if s["verified"] else " - not verified")
        for s in data[:8]
    ]

    summary = f"{len(data)} student(s):\n\n" + "\n".join(lines)

    return {
        "students": data,
        "navigate_to": "/placement/students",
        "summary": summary,
    }


def _tool_get_unverified_students(profile, user, args):

    from jobsystem.models import StudentProfile

    unverified = StudentProfile.objects.filter(
        verified=False
    ).order_by("-id")[:15]

    data = [
        {"full_name": s.full_name, "department": s.department}
        for s in unverified
    ]

    if data:

        lines = [
            f"- {st['full_name']} ({st['department'] or 'department not set'})"
            for st in data[:8]
        ]

        summary = (
            f"{len(data)} student(s) not yet verified:\n\n" + "\n".join(lines)
        )

    else:

        summary = "All students are verified."

    return {
        "students": data,
        "navigate_to": "/placement/students",
        "summary": summary,
    }


def _tool_get_placement_drives(profile, user, args):

    from jobsystem.models import PlacementDrive

    valid_statuses = {"upcoming", "ongoing", "completed", "cancelled"}

    status_filter = (args.get("status") or "upcoming").strip().lower()

    if status_filter not in valid_statuses:

        status_filter = "upcoming"

    drives = PlacementDrive.objects.filter(
        status=status_filter
    ).select_related("company").order_by("drive_date")[:10]

    data = [
        {
            "title": d.title,
            "company": d.company.company_name if d.company else "",
            "date": str(d.drive_date),
            "status": (
                d.get_status_display()
                if hasattr(d, "get_status_display") else d.status
            ),
        }
        for d in drives
    ]

    if data:

        lines = [
            f"- {d['title']} ({d['company'] or 'company not set'}): {d['date']}"
            for d in data[:8]
        ]

        summary = (
            f"{len(data)} {status_filter} placement drive(s):\n\n"
            + "\n".join(lines)
        )

    else:

        summary = f"No {status_filter} placement drives."

    return {
        "drives": data,
        "navigate_to": "/placement/drives",
        "summary": summary,
    }


def _tool_get_company_insights(profile, user, args):
    """
    An ACROSS-ALL-COMPANIES overview - unlike get_company_history
    (which needs one specific company named), this is for "Company
    Insights" clicked with no particular company in mind: which
    companies are posting the most, hiring the most, still pending
    approval. The "Company Insights" capability advertised on this
    page had no tool behind it for the general case before this -
    only the single-company lookup existed.
    """

    from jobsystem.models import CompanyProfile, Job, Application

    companies = CompanyProfile.objects.all()

    rows = []

    for c in companies:

        jobs_count = Job.objects.filter(company=c).count()

        apps = Application.objects.filter(job__company=c)

        hired = apps.filter(status="selected").count()

        rows.append({
            "company_name": c.company_name,
            "industry": c.industry,
            "approval_status": c.approval_status,
            "jobs_posted": jobs_count,
            "applications": apps.count(),
            "hired": hired,
        })

    if not rows:

        return {
            "companies": [],
            "summary": "No companies registered yet.",
        }

    rows.sort(key=lambda r: (r["jobs_posted"], r["applications"]), reverse=True)

    top = rows[:8]

    lines = [
        f"- {r['company_name']} ({r['industry'] or 'industry not set'}, "
        f"{r['approval_status']}): {r['jobs_posted']} job(s) posted, "
        f"{r['applications']} application(s), {r['hired']} hired"
        for r in top
    ]

    pending_count = sum(1 for r in rows if r["approval_status"] == "pending")

    summary = (
        f"{len(rows)} compan{'y' if len(rows) == 1 else 'ies'} registered "
        f"({pending_count} awaiting approval). Top by activity:\n\n"
        + "\n".join(lines)
    )

    return {
        "companies": rows,
        "navigate_to": "/placement/companies",
        "summary": summary,
    }


def _tool_get_company_history(profile, user, args):

    from jobsystem.models import CompanyProfile, Job, Application

    name = (args.get("company_name") or "").strip()

    if not name:

        return {"summary": "Which company would you like details on?"}

    company = CompanyProfile.objects.filter(
        company_name__icontains=name
    ).first()

    if not company:

        return {"summary": f"No company found matching \"{name}\"."}

    jobs_count = Job.objects.filter(company=company).count()

    apps = Application.objects.filter(job__company=company)

    hired = apps.filter(status="selected").count()

    return {
        "company_name": company.company_name,
        "industry": company.industry,
        "approval_status": company.approval_status,
        "total_jobs_posted": jobs_count,
        "total_applications": apps.count(),
        "students_hired": hired,
        "navigate_to": "/placement/companies",
        "summary": (
            f"{company.company_name}: {jobs_count} job(s) posted, "
            f"{apps.count()} application(s), {hired} hired."
        ),
    }


def _tool_get_placement_report(profile, user, args):

    from jobsystem.models import StudentProfile, CompanyProfile, Application

    total_students = StudentProfile.objects.count()

    selected = Application.objects.filter(status="selected").count()

    placement_pct = (
        round((selected / total_students) * 100, 1) if total_students else 0
    )

    return {
        "total_students": total_students,
        "total_companies": CompanyProfile.objects.count(),
        "selected_students": selected,
        "placement_percentage": placement_pct,
        "navigate_to": "/placement/reports",
        "summary": (
            f"Placement report: {selected} of {total_students} students "
            f"placed ({placement_pct}%)."
        ),
    }


def _tool_find_jobs_platform_wide(profile, user, args):
    """
    Lists job postings ACROSS THE WHOLE PLATFORM (every company, not
    one company's own) - the "Find Jobs" capability advertised on the
    Placement Admin AI Chatbot page had nothing behind it at all
    before this; there was no tool a placement admin could reach for
    jobs/companies/status, so every "find jobs"/"jobs at X" question
    fell through to the AI with no real data to answer from.

    Supports an optional company_name keyword ("jobs at Google") and
    an optional status filter - both matched flexibly, same approach
    as get_job_description on the company side. Also supports an
    optional department keyword ("jobs for Computer Science students") -
    a real report found this specific question with no tool behind it
    at all, even though Job.eligible_departments already holds exactly
    this data; it just had never been queried anywhere in the chatbot.

    Also supports deadline_filter ("expired"/"closing_soon") - Job has
    no "expired" STATUS value at all (only pending/active/closed/
    rejected - confirmed directly from the real model), so "expired"
    has to be computed: an "active" job whose application_deadline has
    already passed, using India time for consistency with the rest of
    this file's date handling. "Closing soon" is active with a
    deadline in the next 7 days.

    Also supports keyword (role/title - "Python developer jobs") and
    location ("jobs in Chennai"). keyword is TITLE-PRIORITY: a real
    report found "show active Python developer jobs in Chennai"
    incorrectly returning an unrelated Senior Frontend Developer
    posting, purely because "Python" happened to appear somewhere in
    THAT job's skills list. Matches the job TITLE first; only if
    nothing matches the title does it fall back to a skills-based
    match, returned SEPARATELY (skill_matched_jobs) and clearly
    labelled as such, rather than silently mixed into the main results
    as if it were an equally strong, title-based match.
    """

    from django.db.models import Q
    from jobsystem.models import Job

    company_name = (args.get("company_name") or "").strip()

    status_filter = (args.get("status") or "").strip().lower()

    department = (args.get("department") or "").strip()

    deadline_filter = (args.get("deadline_filter") or "").strip().lower()

    keyword = (args.get("keyword") or "").strip()

    location = (args.get("location") or "").strip()

    jobs_qs = Job.objects.select_related("company")

    if department:

        jobs_qs = jobs_qs.filter(
            eligible_departments__icontains=department
        )

    if company_name:

        jobs_qs = jobs_qs.filter(
            company__company_name__icontains=company_name
        )

    if location:

        jobs_qs = jobs_qs.filter(location__icontains=location)

    if status_filter in {"active", "pending", "closed", "rejected"}:

        jobs_qs = jobs_qs.filter(status=status_filter)

    skill_matched_note = False

    if keyword:

        title_matches = jobs_qs.filter(title__icontains=keyword)

        if title_matches.exists():

            jobs_qs = title_matches

        else:

            # No job TITLE contains this keyword - fall back to a
            # skills-based match, but keep it clearly distinct rather
            # than silently treating "mentions this skill somewhere"
            # as equivalent to "this role is literally this title".

            jobs_qs = jobs_qs.filter(skills_required__icontains=keyword)

            skill_matched_note = True

    if deadline_filter in {"expired", "closing_soon"}:

        today = _india_now().date()

        jobs_qs = jobs_qs.filter(
            status="active", application_deadline__isnull=False
        )

        if deadline_filter == "expired":

            jobs_qs = jobs_qs.filter(application_deadline__lt=today)

        else:

            jobs_qs = jobs_qs.filter(
                application_deadline__gte=today,
                application_deadline__lte=today + timedelta(days=7),
            )

    # Real total BEFORE the display slice - a "how many jobs are
    # posted" question needs the true count, not however many happen
    # to fit in the detailed list below. Capping the count itself to
    # the display limit would silently under-report once postings
    # exceed that limit (e.g. truly 50 postings, incorrectly answered
    # "15 job posting(s)").

    total_count = jobs_qs.count()

    jobs = list(jobs_qs.order_by("-created_at")[:15])

    if not jobs:

        if deadline_filter == "expired":

            summary = "No expired job postings found - every active posting's deadline is still open."

        elif deadline_filter == "closing_soon":

            summary = "No job postings are closing in the next 7 days."

        elif keyword:

            summary = f"No job postings found matching \"{keyword}\"" + (
                f" in {location}." if location else "."
            )

        elif department:

            summary = f"No job postings found eligible for \"{department}\" students."

        elif company_name:

            summary = f"No job postings found for \"{company_name}\"."

        else:

            summary = "No job postings found."

        return {"jobs": [], "summary": summary}

    data = []

    lines = []

    for job in jobs:

        company = job.company.company_name if job.company else "Unknown company"

        status_label = (
            job.get_status_display()
            if hasattr(job, "get_status_display") else job.status
        )

        deadline_display = (
            job.application_deadline.strftime("%b %d, %Y")
            if job.application_deadline else "no deadline set"
        )

        data.append({
            "title": job.title,
            "company": company,
            "status": status_label,
            "location": job.location or "",
            "salary": job.salary or "",
            "skills_required": job.skills_required or "",
            "application_deadline": deadline_display,
        })

        if deadline_filter in {"expired", "closing_soon"}:

            # The deadline itself is the whole point of this question -
            # shown instead of salary, which isn't what was asked about.

            lines.append(
                f"- {job.title} at {company} - deadline: {deadline_display}"
            )

        else:

            lines.append(
                f"- {job.title} at {company} ({status_label}) - "
                f"{job.location or 'location not set'}, "
                f"{job.salary or 'salary not disclosed'}"
            )

    shown_note = (
        f" (showing the {len(data)} most recent)" if total_count > len(data) else ""
    )

    deadline_label = (
        " expiring" if deadline_filter == "expired"
        else " closing within 7 days" if deadline_filter == "closing_soon"
        else ""
    )

    skill_match_prefix = (
        f"No job titled \"{keyword}\" found - showing postings that "
        f"require \"{keyword}\" as a skill instead:\n\n"
        if skill_matched_note else ""
    )

    summary = (
        skill_match_prefix
        + f"{total_count} job posting(s){deadline_label}{shown_note}:\n\n"
        + "\n".join(lines[:8])
    )

    return {
        "jobs": data,
        "skill_matched": skill_matched_note,
        "navigate_to": "/placement/jobs",
        "summary": summary,
    }


def _tool_get_candidate_pipeline(profile, user, args):
    """
    A real report found "how many students applied for Junior Python
    Full Stack Developer" answered with a platform-wide total (every
    job, not that one) alongside a "most recent" candidate list that
    could easily belong to a DIFFERENT job entirely - because this
    tool had no job filter at all, so it was the only thing the AI
    could call regardless of whether a specific job was named, and the
    count and the displayed names were never actually scoped together.

    job_title now properly scopes BOTH the stats and the candidate
    list to one specific job (strict, all-words matching - same
    precision fix used elsewhere in this file for the identical
    "Senior X" vs "X" false-match risk). Omitted, this is unchanged:
    the original platform-wide pipeline.

    When scoped to one job, candidates are also ranked by real AI
    match score (reusing compute_job_match, the same scoring already
    used on the company side's own top-candidates tool) so "who is
    the top candidate for this job" has a real, grounded answer
    instead of an invented one.
    """

    from jobsystem.models import Application

    job_title = (args.get("job_title") or "").strip()

    rank_candidates = bool(args.get("rank_candidates"))

    apps_qs = Application.objects.select_related(
        "student", "job", "job__company"
    )

    job_matched = False

    if job_title:

        title_q = _job_role_strict_match_q("job__title", job_title)

        if title_q is not None:

            scoped = apps_qs.filter(title_q)

            if scoped.exists():

                apps_qs = scoped

                job_matched = True

    if job_title and not job_matched:

        return {
            "candidates": [],
            "summary": (
                f"No applications found for a job matching "
                f"\"{job_title}\" - please confirm the exact title or "
                "company."
            ),
        }

    stats = {
        "total_applicants": apps_qs.count(),
        "shortlisted": apps_qs.filter(status="shortlisted").count(),
        "interviews_scheduled": apps_qs.filter(status="interview").count(),
        "final_selected": apps_qs.filter(status="selected").count(),
    }

    if job_matched and rank_candidates:

        # Real ranking, not just the most recent - rank_jobs-style
        # scoring per application so "top candidate" is a genuine,
        # grounded answer rather than guessed or invented. Imported
        # here, inside the job-scoped branch specifically, so the
        # plain platform-wide pipeline (no job_title at all) never
        # needs this importable - unchanged from before this feature,
        # same reasoning as the django.db.models.Q scoping elsewhere
        # in this file.
        #
        # Gated behind rank_candidates specifically - a real report
        # found "how many students applied for X" (a plain count
        # question) ALWAYS getting a "Top candidate: ..." line
        # attached, even when nobody asked for a ranking. That's a
        # different question ("who is the top candidate for X") and
        # now only runs this real scoring work when actually asked.

        from jobsystem.services.job_matching import compute_job_match

        scored = []

        for a in apps_qs.order_by("-applied_date")[:30]:

            try:

                score, _ = compute_job_match(a.student, a.job)

            except Exception:

                score = None

            scored.append((a, score))

        scored.sort(key=lambda pair: (pair[1] if pair[1] is not None else -1), reverse=True)

        apps = [a for a, _ in scored[:15]]

        candidates = [
            {
                "name": a.student.full_name,
                "job_title": a.job.title,
                "company": a.job.company.company_name if a.job.company else "",
                "status": a.get_status_display(),
                "match_score": score,
            }
            for a, score in scored[:15]
        ]

        if candidates and candidates[0].get("match_score") is not None:

            top = candidates[0]

            top_line = (
                f"Top candidate for {job_title}: {top['name']} "
                f"({top['match_score']}% match, {top['status']}).\n\n"
            )

        else:

            top_line = ""

        list_lines = [
            f"- {c['name']}"
            + (f" ({c['match_score']}% match)" if c.get("match_score") is not None else "")
            + f": {c['status']}"
            for c in candidates[:8]
        ]

        summary = (
            top_line
            + f"{stats['total_applicants']} applicant(s) for {job_title}, "
            f"{stats['shortlisted']} shortlisted, "
            f"{stats['interviews_scheduled']} in interview stage, "
            f"{stats['final_selected']} selected.\n\n"
            + "\n".join(list_lines)
        )

    elif job_matched:

        # Job-scoped, but ranking was NOT asked for - a plain count
        # and real applicant list for this one job, no match-score
        # computation, no "top candidate" line. This is the actual
        # fix for the real report: "how many applied for X" now gets
        # exactly that, nothing more.

        apps = list(apps_qs.order_by("-applied_date")[:15])

        candidates = [
            {
                "name": a.student.full_name,
                "job_title": a.job.title,
                "company": a.job.company.company_name if a.job.company else "",
                "status": a.get_status_display(),
            }
            for a in apps
        ]

        list_lines = [
            f"- {c['name']}: {c['status']}" for c in candidates[:8]
        ]

        summary = (
            f"{stats['total_applicants']} applicant(s) for {job_title}, "
            f"{stats['shortlisted']} shortlisted, "
            f"{stats['interviews_scheduled']} in interview stage, "
            f"{stats['final_selected']} selected.\n\n"
            + "\n".join(list_lines)
        )

    else:

        apps = list(apps_qs.order_by("-applied_date")[:15])

        candidates = [
            {
                "name": a.student.full_name,
                "job_title": a.job.title,
                "company": a.job.company.company_name if a.job.company else "",
                "status": a.get_status_display(),
            }
            for a in apps
        ]

        recent_lines = [
            f"- {c['name']} ({c['job_title']} at {c['company'] or 'company not set'}): {c['status']}"
            for c in candidates[:5]
        ]

        summary = (
            f"{stats['total_applicants']} total applicant(s), "
            f"{stats['shortlisted']} shortlisted, "
            f"{stats['interviews_scheduled']} in interview stage, "
            f"{stats['final_selected']} selected.\n\nMost recent:\n"
            + "\n".join(recent_lines)
        )

    return {
        "candidates": candidates,
        "navigate_to": "/placement/candidates/pipeline",
        "summary": summary,
    }


def _tool_get_job_eligibility_criteria(profile, user, args):
    """
    A real report found "Senior Software Tester eligibility
    requirements" answered with a job LISTING (title/company/status),
    not the actual eligibility fields - because no tool existed for
    this at all, so the AI fell back to the only job-related tool it
    had. Job already stores REAL structured eligibility data
    (min_cgpa, min_percentage, eligible_departments,
    eligible_graduation_years, max_backlogs, min_age, max_age) plus
    free-text fields (eligibility_criteria, qualification_required,
    experience_required) - this reads them directly and states
    plainly which ones aren't set, rather than inventing a plausible-
    looking requirement for a blank field.
    """

    from jobsystem.models import Job

    job_title = (args.get("job_title") or "").strip()

    company_name = (args.get("company_name") or "").strip()

    if not job_title:

        return {"summary": "Which job would you like the eligibility criteria for?"}

    title_q = _job_role_strict_match_q("title", job_title)

    jobs_qs = Job.objects.select_related("company")

    if title_q is not None:

        jobs_qs = jobs_qs.filter(title_q)

    if company_name:

        jobs_qs = jobs_qs.filter(company__company_name__icontains=company_name)

    matches = list(jobs_qs[:5])

    if not matches:

        return {
            "summary": (
                f"No job found matching \"{job_title}\""
                + (f" at \"{company_name}\"" if company_name else "")
                + " - please confirm the exact title or company."
            )
        }

    if len(matches) > 1 and not company_name:

        options = "; ".join(
            f"{j.title} at {j.company.company_name if j.company else 'unknown company'}"
            for j in matches
        )

        return {
            "summary": (
                f"Multiple postings match \"{job_title}\": {options}. "
                "Which one did you mean - please name the company too?"
            )
        }

    job = matches[0]

    company_display = job.company.company_name if job.company else "Unknown company"

    lines = [f"Eligibility criteria for {job.title} at {company_display}:"]

    def add(label, value):

        lines.append(f"- {label}: {value if value not in (None, '', []) else 'not specified'}")

    add("Minimum CGPA", job.min_cgpa)

    add("Minimum 10th/12th percentage", job.min_percentage)

    add("Eligible departments", job.eligible_departments or "all departments")

    add("Eligible graduation years", job.eligible_graduation_years or "any year")

    add("Maximum backlogs allowed", job.max_backlogs if job.max_backlogs is not None else "no limit")

    age_range = (
        f"{job.min_age or 'no minimum'}-{job.max_age or 'no maximum'}"
        if (job.min_age or job.max_age) else None
    )

    add("Age range", age_range)

    add("Required qualification", job.qualification_required)

    add("Required experience", job.experience_required)

    if job.eligibility_criteria:

        lines.append(f"- Additional criteria: {job.eligibility_criteria}")

    return {
        "job_title": job.title,
        "company": company_display,
        "summary": "\n".join(lines),
    }


def _tool_list_company_queries(profile, user, args):
    """
    A placement admin listing company-raised questions, optionally
    filtered by status and/or company. New capability - see
    _tool_raise_company_query's docstring for why PlacementQuery
    (student-specific) couldn't be reused for this.
    """

    from jobsystem.models import CompanyQuery

    status_filter = (args.get("status") or "").strip().lower()

    company_name = (args.get("company_name") or "").strip()

    job_title = (args.get("job_title") or "").strip()

    qs = CompanyQuery.objects.select_related(
        "company", "related_job", "answered_by"
    ).order_by("-created_at")

    if status_filter in {"pending", "in_review", "answered", "closed"}:

        qs = qs.filter(status=status_filter)

    if company_name:

        qs = qs.filter(company__company_name__icontains=company_name)

    if job_title:

        title_q = _job_role_strict_match_q("related_job__title", job_title)

        if title_q is not None:

            qs = qs.filter(title_q)

    total_count = qs.count()

    queries = list(qs[:15])

    if not queries:

        label = status_filter or (f"from \"{company_name}\"" if company_name else "")

        summary = f"No {label} company questions found." if label else "No company questions found."

        return {"queries": [], "summary": summary}

    lines = [
        f"- CQ-{q.id}: {q.subject} ({q.company.company_name if q.company else 'unknown company'}) - {q.get_status_display()}"
        for q in queries
    ]

    shown_note = f" (showing the {len(queries)} most recent)" if total_count > len(queries) else ""

    return {
        "queries": [
            {
                "id": q.id,
                "subject": q.subject,
                "company": q.company.company_name if q.company else "",
                "status": q.get_status_display(),
            }
            for q in queries
        ],
        "summary": f"{total_count} company question(s){shown_note}:\n\n" + "\n".join(lines[:10]),
    }


def _tool_get_company_query_detail(profile, user, args):
    """A placement admin retrieving one specific question's full detail."""

    from jobsystem.models import CompanyQuery

    query_id = args.get("query_id")

    if not query_id:

        return {"summary": "Which question - please give the CQ number (e.g. CQ-102)."}

    query = CompanyQuery.objects.select_related(
        "company", "related_job", "answered_by"
    ).filter(id=query_id).first()

    if not query:

        return {"summary": f"No question found with ID CQ-{query_id}."}

    lines = [
        f"CQ-{query.id}: {query.subject}",
        f"Company: {query.company.company_name if query.company else 'unknown'}",
        f"Status: {query.get_status_display()}",
        f"Question: {query.question_text}",
    ]

    if query.related_job:

        lines.append(f"Related job: {query.related_job.title}")

    if query.status == "answered" and query.admin_answer:

        lines.append(f"Answer: {query.admin_answer}")

        lines.append(f"Answered by: {query.answered_by.email if query.answered_by else 'unknown'}")

    return {
        "query_id": query.id,
        "status": query.status,
        "summary": "\n".join(lines),
    }


def _tool_answer_company_query(profile, user, args):
    """
    A placement admin answering a company question. Writes directly
    when the question isn't already answered - the admin has already
    given both the exact target (query_id) and the complete answer
    text in one message, unlike a vague "shortlist this candidate"
    request, so there's materially less ambiguity to confirm here.
    If a question ALREADY has an answer, this does NOT silently
    overwrite it - shows the existing answer and asks for explicit
    confirmation first, per the project's own specified behavior for
    this exact case.
    """

    from django.utils import timezone as _tz
    from jobsystem.models import CompanyQuery

    query_id = args.get("query_id")

    answer_text = (args.get("answer_text") or "").strip()

    if not query_id:

        return {"success": False, "summary": "Which question - please give the CQ number."}

    if not answer_text:

        return {"success": False, "summary": "What would you like the answer to say?"}

    query = CompanyQuery.objects.filter(id=query_id).first()

    if not query:

        return {"success": False, "summary": f"No question found with ID CQ-{query_id}."}

    if query.status == "answered" and query.admin_answer and not args.get("confirm_overwrite"):

        return {
            "success": False,
            "summary": (
                f"CQ-{query.id} already has an answer: \"{query.admin_answer}\". "
                "Reply with \"yes, overwrite\" if you want to replace it with "
                "your new answer, or ask something else."
            ),
        }

    query.admin_answer = answer_text

    query.status = "answered"

    query.answered_by = user

    query.answered_at = _tz.now()

    query.save()

    try:

        from jobsystem.services.notification_engine import dispatch

        dispatch(
            "company_query_answered",
            query.company.user,
            {"subject": query.subject, "query_id": query.id},
        )

    except Exception as e:

        print("CompanyQuery answer notification error:", e)

    return {
        "success": True,
        "summary": f"Answer saved for CQ-{query.id}. The company has been notified.",
    }


def _tool_update_company_query_status(profile, user, args):
    """A placement admin changing a question's status without necessarily answering it (e.g. marking it 'in review')."""

    from jobsystem.models import CompanyQuery

    query_id = args.get("query_id")

    new_status = (args.get("status") or "").strip().lower()

    if not query_id:

        return {"success": False, "summary": "Which question - please give the CQ number."}

    if new_status not in {"pending", "in_review", "answered", "closed"}:

        return {"success": False, "summary": "Status must be one of: pending, in review, answered, closed."}

    query = CompanyQuery.objects.filter(id=query_id).first()

    if not query:

        return {"success": False, "summary": f"No question found with ID CQ-{query_id}."}

    query.status = new_status

    query.save()

    return {
        "success": True,
        "summary": f"CQ-{query.id} marked as {query.get_status_display()}.",
    }


PLACEMENT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_job_eligibility_criteria",
            "description": (
                "Get the ACTUAL eligibility requirements for ONE "
                "specific job posting - min CGPA, min percentage, "
                "eligible departments, eligible graduation years, max "
                "backlogs, age range, required qualification/"
                "experience. Use when the admin asks about eligibility "
                "requirements/criteria for a named job, or whether a "
                "job needs specific qualifications - NOT for a plain "
                "job listing (use find_jobs_platform_wide for that)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The job's title, as named by the admin.",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "The company, if named or needed to disambiguate multiple similarly-titled postings.",
                    },
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_jobs_platform_wide",
            "description": (
                "Find job postings ACROSS THE WHOLE PLATFORM (every "
                "company, not one). Use for 'find jobs'/'jobs at "
                "<company>'/'show me jobs' style questions from the "
                "placement admin - this is the 'Find Jobs' capability "
                "advertised on this page. Pass department when the "
                "admin asked which jobs suit a specific department's "
                "students (e.g. 'jobs for Computer Science students'). "
                "Pass deadline_filter='expired' or 'closing_soon' for "
                "'show expired jobs'/'which jobs are closing soon' "
                "style questions. Pass keyword for a role/title "
                "('Python developer', 'frontend') and location for a "
                "place ('Chennai') - keyword matches the job TITLE "
                "first; a skills-only match (the role isn't in the "
                "title, but the skill is required) is clearly labelled "
                "as such, never silently mixed in as if equivalent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "A company name to filter by, if the admin named one.",
                    },
                    "status": {
                        "type": "string",
                        "description": "active/pending/closed/rejected, if the admin asked for a specific status.",
                    },
                    "department": {
                        "type": "string",
                        "description": "A department/course to filter by eligibility, if the admin named one (e.g. 'Computer Science').",
                    },
                    "deadline_filter": {
                        "type": "string",
                        "description": "'expired' for active jobs whose application deadline has already passed, or 'closing_soon' for active jobs with a deadline in the next 7 days. Use when the admin asks about expired jobs or jobs closing soon.",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "A role/title/technology to filter by, if the admin named one (e.g. 'Python developer', 'frontend'). Matches the job title first.",
                    },
                    "location": {
                        "type": "string",
                        "description": "A location to filter by, if the admin named one (e.g. 'Chennai').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_insights",
            "description": (
                "ACROSS-ALL-COMPANIES overview - which companies are "
                "posting the most jobs, hiring the most, pending "
                "approval. Use for 'company insights'/'tell me about "
                "our companies' with no specific company named. For "
                "ONE named company's own history, use "
                "get_company_history instead."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_placement_overview",
            "description": (
                "Get overall placement stats: total students, "
                "companies, active jobs, applications, placed "
                "students, placement percentage, and active drives. "
                "Use for broad questions like 'how are we doing?' or "
                "'what's our placement rate?'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_company_approvals",
            "description": (
                "Get companies whose registration is still awaiting "
                "approval. Use when asked which companies need "
                "approval/review, or how many are pending."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_students",
            "description": (
                "A general, ALL-students roster with real names, "
                "department and placement status - NOT scoped to "
                "only unverified ones. Use for 'give me students "
                "name'/'show me students'/'list students' with no "
                "further filter. For ONLY unverified students, use "
                "get_unverified_students instead."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unverified_students",
            "description": (
                "Get ONLY students who haven't been verified yet - "
                "for a general all-students list, use list_students "
                "instead. Use when asked which students still need "
                "verification."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_placement_drives",
            "description": (
                "Get placement drives filtered by status. Use for "
                "questions about upcoming/ongoing/past placement "
                "drives."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": (
                            "One of upcoming, ongoing, completed, "
                            "cancelled. Defaults to upcoming."
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
            "name": "get_company_history",
            "description": (
                "Get one specific company's placement history: jobs "
                "posted, applications received, students hired, "
                "approval status. Use when a specific company is "
                "named."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name to look up.",
                    }
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_placement_report",
            "description": (
                "Get the overall placement report summary: total "
                "students, companies, students placed, placement "
                "percentage. Use for 'give me a report' style "
                "questions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_candidate_pipeline",
            "description": (
                "Get the candidate pipeline: applicants, their job, and "
                "their current stage, plus pipeline stage counts. "
                "Omit job_title for the platform-wide pipeline (every "
                "company). Pass job_title when the admin asked about "
                "ONE specific job's applicants/candidates - 'how many "
                "applied for X', 'show applicants for X' - this scopes "
                "both the counts and the candidate list to that job "
                "only. Set rank_candidates=true ONLY for a genuine "
                "ranking question - 'who is the top candidate for X', "
                "'which candidate is the best match' - NOT for a plain "
                "count question; those are different questions and a "
                "count question should never include a ranking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "The specific job to scope to, if the admin named one.",
                    },
                    "rank_candidates": {
                        "type": "boolean",
                        "description": "True only if the admin explicitly asked for the top/best/highest-ranked candidate - not for a plain applicant count.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_company_queries",
            "description": (
                "List company-raised questions, optionally filtered by "
                "status, company, or related job. Use for 'show pending "
                "company questions', 'how many company questions are "
                "pending', 'show questions raised by X', 'show answered "
                "company questions'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "pending/in_review/answered/closed, if the admin asked for a specific status.",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "A company name, if the admin named one.",
                    },
                    "job_title": {
                        "type": "string",
                        "description": "A related job title, if the admin asked about questions for a specific job.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_query_detail",
            "description": (
                "Get one specific company question's full detail, "
                "including its answer if it has one. Use for 'show "
                "question CQ-102', 'show the full history of CQ-102'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "integer",
                        "description": "The CQ number the admin named.",
                    }
                },
                "required": ["query_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_company_query",
            "description": (
                "Answer a company question. Only call when the admin "
                "gave BOTH the exact question (a CQ number) and the "
                "complete answer text in their message - never invent "
                "an answer, and never call this just because a "
                "question was discussed without an explicit answer "
                "being dictated. If the question already has a saved "
                "answer, this will ask for confirmation before "
                "overwriting it rather than silently replacing it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "integer",
                        "description": "The CQ number to answer.",
                    },
                    "answer_text": {
                        "type": "string",
                        "description": "The exact answer text the admin dictated.",
                    },
                    "confirm_overwrite": {
                        "type": "boolean",
                        "description": "True only if the admin just confirmed overwriting an existing answer.",
                    },
                },
                "required": ["query_id", "answer_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_company_query_status",
            "description": (
                "Change a company question's status WITHOUT answering "
                "it (e.g. marking it 'in review'). Use for 'mark CQ-102 "
                "as in review' - for actually answering a question, "
                "use answer_company_query instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "integer",
                        "description": "The CQ number to update.",
                    },
                    "status": {
                        "type": "string",
                        "description": "pending/in_review/answered/closed.",
                    },
                },
                "required": ["query_id", "status"],
            },
        },
    },
]


PLACEMENT_TOOL_EXECUTORS = {
    "list_students": _tool_list_students,
    "get_company_insights": _tool_get_company_insights,
    "list_company_queries": _tool_list_company_queries,
    "get_company_query_detail": _tool_get_company_query_detail,
    "answer_company_query": _tool_answer_company_query,
    "update_company_query_status": _tool_update_company_query_status,
    "find_jobs_platform_wide": _tool_find_jobs_platform_wide,
    "get_job_eligibility_criteria": _tool_get_job_eligibility_criteria,
    "get_placement_overview": _tool_get_placement_overview,
    "get_pending_company_approvals": _tool_get_pending_company_approvals,
    "get_unverified_students": _tool_get_unverified_students,
    "get_placement_drives": _tool_get_placement_drives,
    "get_company_history": _tool_get_company_history,
    "get_placement_report": _tool_get_placement_report,
    "get_candidate_pipeline": _tool_get_candidate_pipeline,
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

        left = _time_left()

        if left is not None and left < GROQ_MIN_ATTEMPT_WINDOW:

            print(f"[chatbot] time budget used up ({left:.1f}s left) - not trying {model_name}")

            break

        started = time.monotonic()

        try:

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.4,
                max_tokens=500,
            )

            print(f"[chatbot] {model_name} answered in {time.monotonic() - started:.1f}s")

            return response.choices[0].message.content.strip()

        except Exception as e:

            last_error = e

            print(
                f"[chatbot] {model_name} failed after "
                f"{time.monotonic() - started:.1f}s: {type(e).__name__}: {e}"
            )

            continue

    raise last_error or Exception("Chatbot: all models failed or time budget used up")


def _call_groq_with_tools(messages, tools, tool_choice="auto"):

    last_error = None

    for model_name in GROQ_MODEL_FALLBACKS:

        left = _time_left()

        if left is not None and left < GROQ_MIN_ATTEMPT_WINDOW:

            print(f"[chatbot] time budget used up ({left:.1f}s left) - not trying {model_name}")

            break

        started = time.monotonic()

        try:

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=0.3,
                max_tokens=600,
            )

            print(f"[chatbot] {model_name} answered in {time.monotonic() - started:.1f}s")

            return response

        except Exception as e:

            last_error = e

            print(
                f"[chatbot] {model_name} failed after "
                f"{time.monotonic() - started:.1f}s: {type(e).__name__}: {e}"
            )

            continue

    raise last_error or Exception("Chatbot: all models failed or time budget used up")


# =====================================================
# MAIN ENTRY POINT
# =====================================================

# Keys that, when present in a tool's result, are forwarded to the
# frontend as-is (never rewritten by the model) so it can render
# real cards/lists/buttons instead of plain text.

_FORWARDED_LIST_KEYS = (
    "matched_jobs", "candidates", "applications",
    "interviews", "jobs", "drives", "notifications",
    "companies", "students",
)


# Tools that create/modify a real database record (or, for
# apply_to_job, ask the student to confirm one). Their own "summary" is
# used as the reply text - never a model paraphrase - so what the student
# reads always matches exactly what happened.

_WRITE_ACTION_TOOLS = {
    "apply_to_job", "request_interview_slot",
    "raise_placement_query", "update_my_skills", "update_my_projects",
    "shortlist_candidate", "reject_candidate",
}


# Tabs the frontend should reload after a successful chatbot action.

_REFRESH_AFTER = {
    "update_my_skills": ["profile", "dashboard", "jobs"],
    "update_my_projects": ["profile", "dashboard"],
    "request_interview_slot": ["interviews"],
    "raise_placement_query": ["queries"],
}


def _clean_reply(text):
    """The chat shows plain text, so strip markdown the model sometimes adds."""

    text = (text or "").replace("**", "")

    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)

    return text.strip()


def _execute_tool_calls(tool_calls, tool_executors, actor_profile, user):
    """
    Runs every tool the model asked for (at most 3) and returns a list of
    (call, tool_name, result). "Show my applications and my interviews"
    used to answer only the first half.
    """

    calls = list(tool_calls)[:3]

    # Starting a mock interview changes the conversation state (the next
    # messages become interview answers), so it always runs on its own.

    for call in calls:

        if call.function.name == "start_mock_interview":

            calls = [call]

            break

    executed = []

    for call in calls:

        name = call.function.name

        try:

            args = json.loads(call.function.arguments or "{}")

        except Exception:

            args = {}

        executor = tool_executors.get(name)

        if not executor:

            result = {
                "failed": True,
                "summary": "I'm not able to do that yet - try asking in a different way.",
            }

        else:

            tool_started = time.monotonic()

            try:

                result = executor(actor_profile, user, args)

                print(f"[chatbot] tool {name} took {time.monotonic() - tool_started:.2f}s")

            except Exception as e:

                print("Chatbot tool execution error:", name, e)

                result = {
                    "failed": True,
                    "summary": (
                        "I ran into an issue while doing that. Please try "
                        "again in a moment, or ask me in a different way."
                    ),
                }

        executed.append((call, name, result))

    return executed


# Tools whose result is shown as real cards in BOTH chat screens (job cards,
# notification list), so the reply text only needs to be a short intro line
# that the tool's own summary already provides. For these the second AI call
# (which only re-words that summary) is skipped - roughly halving the wait.
# Deliberately NOT included: tools whose lists the widget can't render as
# cards (interviews, applications, drives...), where the AI's wording is
# what actually shows the details.

_FAST_REPLY_TOOLS = {
    "find_matching_jobs", "check_job_eligibility", "list_open_jobs",
    "get_saved_jobs", "get_notifications",

    # Added once these three tools' own summaries were fixed to include
    # real detail (skills, description, eligibility) rather than a bare
    # one-liner - the AI's second "write-up" pass was only ever
    # re-wording something already good, so skipping it for a simple
    # request halves the AI-call cost (and the quota exposure) for any
    # question that successfully routes to one of these, not just a
    # specific hand-picked phrase. get_career_plan and
    # get_company_skill_gap are deliberately NOT included - their real
    # value is the AI actively cross-referencing/prioritizing the raw
    # data into a plan, which a skipped write-up pass would lose.
    "get_job_details", "get_interview_prep", "get_skill_suggestions",
}


def _can_skip_text_pass(executed):
    """True when every executed tool is a card-rendered list tool whose own
    summary is a fine reply (no AI re-wording needed)."""

    if not executed:

        return False

    for call, name, result in executed:

        if name not in _FAST_REPLY_TOOLS or result.get("failed"):

            return False

        if name in ("get_interview_prep", "get_job_details") and "job_title" not in result:

            # The "nothing found" case for these two tools is a BARE
            # one-liner by design ("No upcoming interview found...") -
            # real content only exists once a real job/interview/
            # application was actually found (the "job_title" key is
            # only ever set then). Skipping the AI here would silently
            # bypass the "give genuinely useful general advice instead
            # of a dead end" instruction built specifically for this
            # exact case (see BE A REAL CAREER ASSISTANT in the system
            # prompt) - the bug this fixes was discovered from a real
            # report: "no upcoming interview found" was being shown
            # verbatim for a role the student had never applied to,
            # instead of the general prep advice that instruction
            # exists to provide.

            return False

        if name == "find_matching_jobs":

            # "which job is best?" (limit=1) needs the AI to explain WHY.

            try:

                args = json.loads(call.function.arguments or "{}")

                limit = int(args.get("limit") or 5)

            except Exception:

                limit = 5

            if limit == 1:

                return False

    return True


# ----------------------------- agent loop helpers -----------------------------

# The assistant can look something up, read the result, then decide to look up
# something else - up to this many rounds of tools per message. Writes are never
# part of the loop: they only ever PREPARE a confirmation and end it.

_MAX_TOOL_ROUNDS = 3


def _call_signature(call):
    """Same tool + same arguments = same call, however the JSON is spaced."""

    try:

        args = json.dumps(json.loads(call.function.arguments or "{}"), sort_keys=True)

    except Exception:

        args = str(call.function.arguments)

    return f"{call.function.name}:{args}"


def _is_simple_request(message):
    """Short, single-purpose messages ("find jobs for me") can be answered
    from the tool's own result without another model call. Longer ones may
    be asking for something that needs a second lookup or real reasoning."""

    return len((message or "").split()) <= 8


def _append_tool_round(messages, choice_message, executed):
    """Adds one round of (assistant tool calls -> tool results) to the
    conversation the model sees."""

    messages.append({
        "role": "assistant",
        "content": choice_message.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": call.function.arguments,
                },
            }
            for call, name, _result in executed
        ],
    })

    for call, name, result in executed:

        if name in _WRITE_ACTION_TOOLS:

            # The model must not restate these - their confirmation text
            # is appended to the reply automatically.

            tool_content = {
                "success": bool(result.get("success")),
                "note": (
                    "The result of this action is added to your reply "
                    "automatically - do not describe or repeat it."
                ),
            }

        else:

            tool_content = result

        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(tool_content, default=str),
        })


def _round_is_final(all_executed, message):
    """True when nothing more should be asked of the model this message:
    a write was prepared (its confirmation IS the answer), a mock interview
    started (its first question is the answer), or it was a short request
    whose card-rendered result already says it all."""

    names = [name for _call, name, _result in all_executed]

    if any(name in _WRITE_ACTION_TOOLS for name in names):

        return True

    if "start_mock_interview" in names:

        return True

    return _can_skip_text_pass(all_executed) and _is_simple_request(message)


def _friendly_fast_text(name, result):
    """A natural-sounding reply for a card-rendered result when no model call
    is made - says something about the results and asks the natural next
    question, instead of a bare "Found 3 jobs."."""

    summary = _user_facing(result.get("summary", "Here's what I found."))

    if name == "list_open_jobs":

        cards = result.get("matched_jobs") or []

        if not cards:

            return summary

        total = result.get("total_open", len(cards))

        can = result.get("can_apply", 0)

        applied = result.get("applied_count", 0)

        blocked = result.get("blocked_count", 0)

        one = total == 1

        if one:

            lead = "There is 1 open job right now."

        elif len(cards) < total:

            lead = f"There are {total} open jobs - here are the {len(cards)} best matches."

        else:

            lead = f"Here are all {total} open jobs, best match first."

        bits = []

        if can:

            bits.append("you can apply to it right now" if one else f"you can apply to {can} of them right now")

        if applied:

            bits.append("you've already applied to it" if one else f"you've already applied to {applied}")

        if blocked:

            bits.append(
                "it needs something your profile doesn't have yet" if one
                else f"{blocked} need something your profile doesn't have yet"
            )

        status = ""

        if bits:

            joined = bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + ", and " + bits[-1]

            status = " " + joined[0].upper() + joined[1:] + "."

        tail = (
            ' Ask me "find jobs that match my profile" to see exactly what each one needs.'
            if blocked else ""
        )

        return lead + status + tail

    if name in ("find_matching_jobs", "check_job_eligibility"):

        cards = result.get("matched_jobs") or []

        if not cards:

            return summary

        if result.get("kind") == "new_jobs":

            newest = cards[0]

            score = newest.get("match_score")

            best = (
                f"{newest.get('title')} at {newest.get('company')}"
                + (f" ({score}% match)" if score is not None else "")
            )

            total = result.get("total_new", len(cards))

            if total == 1:

                lead = f"1 new job was posted in the last {RECENT_JOB_DAYS} days: {best}."

            else:

                lead = (
                    f"{total} new jobs were posted in the last {RECENT_JOB_DAYS} "
                    f"days. The newest is {best}"
                    + (
                        f" - here are the {len(cards)} newest."
                        if len(cards) < total else "."
                    )
                )

            return lead + " Want me to check which ones match your profile?"

        top = cards[0]

        score = top.get("match_score")

        best = (
            f"{top.get('title')} at {top.get('company')}"
            + (f" ({score}% match)" if score is not None else "")
        )

        count = len(cards)

        lead = (
            f"I found 1 job you can apply to right now: {best}. "
            "Want me to apply, or tell you more about it?"
            if count == 1 else
            f"I found {count} jobs you can apply to right now, and the best "
            f"match is {best}. Want me to apply to one, or tell you more "
            "about any of them?"
        )

        # keep the "already applied / requirements / profile" notes that
        # follow the headline in the tool's own summary

        return "\n\n".join([lead] + summary.split("\n\n")[1:])

    if name == "get_notifications" and not (result.get("notifications") or []):

        return "You're all caught up - you don't have any notifications yet."

    return summary


def _fast_reply_text(executed):

    parts = [
        _friendly_fast_text(name, result)
        for _call, name, result in executed
    ]

    return "\n\n".join(part for part in parts if part)


def _next_step_chips(executed):
    """One-tap follow-ups that fit what was just shown. Only used when the
    reply has no buttons of its own (apply confirmations etc. always win)."""

    for _call, name, result in executed:

        if name in ("find_matching_jobs", "check_job_eligibility"):

            cards = result.get("matched_jobs") or []

            if cards:

                title = cards[0].get("title")

                if result.get("kind") == "new_jobs":

                    return ["Find jobs that match my profile", f"Tell me more about {title}"]

                return [f"Tell me more about {title}", f"Apply to {title}"]

        if name == "list_open_jobs":

            cards = result.get("matched_jobs") or []

            if cards:

                chips = ["Find jobs that match my profile"]

                open_card = next(
                    (c for c in cards if c.get("eligible") and not c.get("already_applied")),
                    None,
                )

                if open_card:

                    chips.append(f"Apply to {open_card.get('title')}")

                return chips

        if name == "get_upcoming_interviews" and (result.get("interviews") or []):

            return ["Help me prepare for my interview", "Start a mock interview"]

        if name == "get_application_status" and result.get("has_interview_scheduled"):

            return ["Help me prepare for my interview"]

    return []


# Exact texts the chat's own buttons send (quick actions / alert chips).
# Tapping one runs the matching tool directly - no AI call at all, so
# these answer almost instantly.

_NEW_JOBS_PHRASES = {
    "show me new jobs", "show new jobs", "new jobs", "any new jobs",
    "are there any new jobs", "list new jobs", "find new jobs",
    "latest jobs", "show me latest jobs", "show me the latest jobs",
    "recent jobs", "show me recent jobs", "newly posted jobs",
    "show me newly posted jobs", "what are the new jobs",
    "what are the new jobs posted", "what are the jobs posted",
}

# "find jobs that match my profile", "find jobs match at my profile",
# "show me jobs that suit me", "get jobs for my skills" ...

_PROFILE_MATCH_RE = re.compile(
    r"^(?:find|show|get|give) (?:me )?(?:the )?(?:all )?(?:best )?jobs? "
    r"(?:that |which )?(?:match|matches|matching|suit|suits|fit|fits|for) "
    r"(?:at |with |to |for )?(?:my|me)(?: profile| skills| resume)?$"
)


# "show all the jobs even though its not eligible to my profile",
# "show me the list of jobs from jobs tab", "list all jobs", "all jobs"...
# Taken over ONLY when every word is ordinary "show me all the jobs" wording, so
# anything with an extra ask (apply, new, match, a place, a salary...) still
# goes to the model.

_ALL_JOBS_WORDS = {
    "show", "list", "see", "display", "give", "get", "open", "what", "are",
    "is", "there", "any", "me", "all", "every", "the", "of", "jobs", "job",
    "available", "posted", "from", "in", "on", "tab", "page", "even",
    "though", "thought", "if", "when", "its", "it", "s", "not", "eligible",
    "ineligible", "to", "for", "my", "profile", "please", "whole",
    "complete", "full",
}

_ALL_JOBS_CUES = {
    "all", "list", "tab", "page", "eligible", "ineligible", "available",
    "every", "whole", "complete", "full", "posted",
}


def _wants_all_jobs(normalized):

    words = normalized.split()

    if not words or len(words) > 18 or not ({"job", "jobs"} & set(words)):

        return False

    return set(words) <= _ALL_JOBS_WORDS and bool(set(words) & _ALL_JOBS_CUES)


# "what jobs did I apply to" and the many ways to ask it - answered
# instantly for the exact same reason "show me jobs" was: this is a
# completely plain, common question that has no reason to ever depend on
# the shared account's tight Groq quota.

_APPLICATION_STATUS_PHRASES = {
    "what jobs did i apply to", "what jobs have i applied to",
    "what are the jobs i applied", "what jobs did i apply for",
    "show my applications", "show me my applications", "my applications",
    "what is my application status", "whats my application status",
    "what is my application status", "show my application status",
    "what jobs have i applied for", "which jobs did i apply to",
    "show applications", "list my applications", "list applications",
    # First-person "did I actually apply?" phrasings - a very natural way
    # to ask the exact same thing, especially for a non-native English
    # speaker, but grammatically different enough that none of the
    # "what/which jobs...to" phrasings above already covered them - so
    # these fell through to a live AI call for no reason, same as
    # "show me jobs" did before it got the same treatment.
    "i applied any jobs", "i applied jobs", "i applied to jobs",
    "i already applied jobs", "i already applied to jobs",
    "did i apply any jobs", "did i apply to any jobs", "did i apply jobs",
    "have i applied any jobs", "have i applied to any jobs",
    "have i applied jobs", "have i applied to jobs",

    # "applied jobs" as a NOUN PHRASE ("jobs that are applied") - a
    # different grammatical shape from the VERB-phrase forms above
    # ("jobs I applied"), reported as a real gap: "show me applied
    # jobs" fell through to a live AI call despite "what are the jobs
    # i applied" (same meaning, different word order) already working.
    "show me applied jobs", "show applied jobs", "my applied jobs",
    "applied jobs",
}


# Catches the natural GRAMMAR of "did I apply to jobs?" directly, instead
# of needing every individual wording added to _APPLICATION_STATUS_PHRASES
# by hand as each new variant gets reported - "what jobs i applied" (a
# dropped "did"/"have"), "what jobs did i apply to", "i applied any jobs",
# "have i applied to any jobs", "any jobs i applied recently" and similar
# all match one of these three sentence shapes (question-word led,
# "I"-led, and "any"-led), each also tolerating a trailing "recently" /
# "lately" / "so far". Deliberately anchored end-to-end ($) so asking
# about ONE specific job ("did i apply to software tester") or adding
# anything else after the verb phrase still correctly falls through to
# the AI instead of being swallowed here.

_TIME_TRAILER = r"(?:\s+(?:recently|lately|so\s+far|till\s+now|until\s+now|up\s+to\s+now))?"

_MY_APPLICATIONS_RE = re.compile(
    r"^(?:what|which)\s+(?:are\s+the\s+)?jobs?\s+(?:did\s+i\s+|have\s+i\s+|i\s+)?"
    r"appl(?:y|ied)(?:\s+(?:to|for))?" + _TIME_TRAILER + r"$"
    r"|^(?:i\s+|did\s+i\s+|have\s+i\s+)(?:already\s+)?appl(?:y|ied)\s+(?:to\s+)?(?:any\s+)?jobs?"
    + _TIME_TRAILER + r"$"
    r"|^any\s+jobs?\s+(?:did\s+i\s+|have\s+i\s+|i\s+)appl(?:y|ied)(?:\s+(?:to|for))?"
    + _TIME_TRAILER + r"$"
    r"|^how\s+many\s+jobs?\s+(?:have\s+i\s+|did\s+i\s+|i\s+(?:have\s+)?)appl(?:y|ied)(?:\s+(?:to|for))?"
    + _TIME_TRAILER + r"$"
    r"|^how\s+many\s+applications?\s+(?:have\s+i\s+made|did\s+i\s+make|have\s+i\s+submitted)?" + _TIME_TRAILER + r"$"
)


# "how do I improve my resume" / "I want my resume score more than 90" and
# similar - answered from the ALREADY-STORED resume_score/missing_info
# (get_resume_feedback), instantly, with zero AI calls. This matters more
# than it looks: without it, a generic "improve my resume" question was
# genuinely ambiguous between this free tool and check_ats_friendliness
# (which needs a live, costly Groq call every time) - and the model
# sometimes picked the costly one for a question the free one could
# already answer just as well. Deliberately does NOT match anything that
# mentions ATS/applicant tracking - those still correctly go to the real
# ATS check.

# "What skills should I improve?" (and close variants) - a literal example
# question from the project spec, with zero shortcut coverage before this.
# get_skill_suggestions already computes real, detailed data (the top
# in-demand skills the student doesn't have yet) - this just makes the
# common phrasings of this exact question answer instantly.

# "Any interview scheduled?" / "job interview scheduled" / "when is my
# interview" - a very common plain question with ZERO shortcut coverage
# before this (confirmed by testing: even the phrasing the student said
# "worked" was actually just a lucky successful AI call, not a shortcut -
# every variant of this question was going through a live call every time).

_INTERVIEW_CHECK_RE = re.compile(
    r"^(?:any\s+)?(?:job\s+)?interviews?\s+scheduled\??$"
    r"|^do\s+i\s+have\s+(?:an\s+|any\s+)?(?:job\s+)?interviews?\??$"
    r"|^is\s+my\s+interview\s+scheduled\??$"
    r"|^when\s+is\s+my\s+(?:next\s+)?interview\??$"
    r"|^(?:do\s+i\s+have\s+)?(?:an\s+|any\s+)?upcoming\s+interviews?\??$"
    r"|^my\s+interviews?$"
)


# A trailing "this week" / "in this week" / "within this week" clause, or
# a trailing "today", on any of the interview-check phrases above - "any
# interview scheduled today" and "interview scheduled this week" need the
# SAME shortcut, but also need today=True/this_week=True actually passed
# through to the tool, not just the phrase recognised. Stripped off
# before matching, so the core _INTERVIEW_CHECK_RE above stays simple and
# this extra case can't silently drift out of sync with it.

_THIS_WEEK_SUFFIX_RE = re.compile(r"\s+(?:in\s+|within\s+)?this\s+week$")

_TODAY_SUFFIX_RE = re.compile(r"\s+today$")

# A leading "yes"/"ok" acknowledgment word before a REAL question - a
# real report found "yes any interview scheduled today" treated as a
# bare confirmation (since it starts with "yes"), when it's actually a
# genuine, complete question with a throwaway leading word. Stripped
# before matching, same idea as the suffix stripping above.

_LEADING_ACK_RE = re.compile(r"^(?:yes|yeah|yep|ok|okay|sure)[,.\s]+")


def _interview_check_args(normalized):
    """None if not an interview-check phrase; otherwise the args to pass
    to get_upcoming_interviews (today=True / this_week=True / {} based
    on which trailing clause, if any, was present)."""

    text = _LEADING_ACK_RE.sub("", normalized)

    this_week = False

    today = False

    match = _TODAY_SUFFIX_RE.search(text)

    if match:

        text = text[:match.start()]

        today = True

    else:

        match = _THIS_WEEK_SUFFIX_RE.search(text)

        if match:

            text = text[:match.start()]

            this_week = True

    if _INTERVIEW_CHECK_RE.match(text):

        if today:

            return {"today": True}

        return {"this_week": True} if this_week else {}

    return None


# "check my resume score" (and close variants) - the student-reported
# phrasing that still fell through even after "what is my resume score"
# was added. Broader than the exact-match entries in _STUDENT_SHORTCUTS,
# since "I want check my resume score" / "can you check my resume score"
# are natural but weren't literally covered by those exact strings.

_RESUME_SCORE_RE = re.compile(
    r"^(?:i\s+want\s+(?:to\s+)?|can\s+you\s+|please\s+|pls\s+)*"
    r"check\s+my\s+resume\s*(?:score)?\??$"
    r"|^(?:what\s+is|whats|show)\s+my\s+resume\s+score\??$"
    r"|^my\s+resume\s+score\??$"
)


_SKILL_SUGGESTION_RE = re.compile(
    r"^(?:what|which)\s+skills?\s+(?:should|do|must|can)\s+i\s+"
    r"(?:improve|learn|develop|need|add|gain|build|focus\s+on|work\s+on)"
    r"(?:\s+to\s+(?:improve|learn|develop))?\??$"
    r"|^(?:how\s+(?:to|do\s+i|can\s+i)\s+)?improve\s+(?:my\s+)?skills?$"
    r"|^(?:what|which)\s+skills?\s+(?:do\s+i\s+)?(?:need|am\s+i\s+missing|do\s+i\s+lack|lack)\??$"
    r"|^(?:help\s+me\s+)?(?:improve|develop)\s+my\s+skills?$"
    r"|^suggest\s+(?:some\s+)?skills?(?:\s+to\s+(?:learn|improve|develop|focus\s+on))?$"
    r"|^(?:give\s+me\s+)?skill\s+(?:suggestions?|recommendations?)$"
    r"|^(?:how\s+(?:to|do\s+i|can\s+i)\s+)?buil[dt]\s+(?:up\s+)?my\s+skills?$"
)


_IMPROVE_RESUME_RE = re.compile(
    r"^(?:i\s+want\s+to\s+|how\s+(?:to|do\s+i|can\s+i)\s+|please\s+)?"
    r"(?:buil\w*|improve\w*|increase\w*|raise\w*|boost\w*|get)\s+"
    r"(?:my\s+)?resume(?:s)?\s*"
    r"(?:score)?\s*"
    r"(?:is\s+|to\s+be\s+|to\s+|be\s+)?"
    r"(?:more\s+than|above|over|higher(?:\s+than)?|better(?:\s+than)?)?\s*\d*%?$"
)


# "i saved any jobs" (and other word-order variants of the exact phrases
# already in _STUDENT_SHORTCUTS) - a natural way to ask the same question
# that the exact-match dict alone didn't cover, same class of gap as
# _MY_APPLICATIONS_RE catching application-status grammar.

_SAVED_JOBS_RE = re.compile(
    r"^(?:any\s+)?jobs?\s+i\s+saved\??$"
    r"|^i\s+saved\s+(?:any\s+)?jobs?\??$"
    r"|^(?:what|which)\s+jobs?\s+(?:have\s+|did\s+)?i\s+save[d]?\??$"
    r"|^(?:any|my|show(?:\s+me)?)\s+saved\s+jobs?\??$"
    r"|^saved\s+jobs?\??$"
)


_PLAIN_JOBS_RE = re.compile(
    r"^(?:please )?(?:show|find|get|give|see|display)"
    r"(?: me)?(?: the)?(?: available)? jobs?(?: for me)?(?: please)?$"
    r"|^jobs(?: for me)?$"
)


# "I want to prepare software Tester job" / "prepare me for a Python
# Developer job" / "give me suggestions to prepare for teacher job role" -
# extracts the named role and routes DIRECTLY to get_interview_prep,
# skipping the orchestrator's own "which tool?" call entirely. Reported
# multiple times as the same recurring phrasing, so worth a real,
# carefully tested extraction rather than another one-off exact phrase.
#
# Deliberately NOT treated as a guaranteed-instant shortcut: if the named
# role is found (a real application/interview), the tool's own summary is
# shown directly, zero AI calls. If NOTHING is found, this returns None -
# NOT a bare "not found" message - so the request correctly falls through
# to the normal AI flow, where the "give genuinely useful general advice"
# instruction (see BE A REAL CAREER ASSISTANT in the system prompt) can
# still apply. Skipping that check here would silently reintroduce the
# exact "Teacher -> bare not-found message, no real advice" bug already
# found and fixed once in this file - short-circuiting is only safe when
# real data was actually found.

_INTERVIEW_PREP_REQUEST_RE = re.compile(
    r"^i\s+want\s+to\s+prepare\s+(?:for\s+)?(?:an?\s+)?(?:interview\s+for\s+)?(?:the\s+)?(?P<job>.+?)"
    r"(?:\s+(?:job\s+role|job|role|interview|position)s?)*$"
    r"|^(?:please\s+)?prepare\s+(?:me\s+)?for\s+(?:an?\s+)?(?:the\s+)?(?P<job2>.+?)"
    r"(?:\s+(?:job\s+role|job|role|interview|position)s?)*$"
    r"|^(?:can\s+you\s+)?give\s+(?:me\s+)?(?:some\s+)?suggestions?\s+to\s+prepare\s+for\s+(?:an?\s+)?(?:the\s+)?(?P<job3>.+?)"
    r"(?:\s+(?:job\s+role|job|role|interview|position)s?)*$"
    r"|^help\s+me\s+prepare\s+for\s+(?:an?\s+)?(?:the\s+)?(?P<job4>.+?)"
    r"(?:\s+(?:job\s+role|job|role|interview|position)s?)*$"
)

# The trailing suffix group above now repeats (* not ?) - a real report
# found "I want to prepare teacher job interview" incorrectly extracting
# "teacher job" as the role (with "job" wrongly left attached), because
# the old version could only strip ONE trailing descriptor word, and
# this phrase stacks two ("job" then "interview"). Allowing the suffix
# to match zero-OR-MORE such words correctly strips both, leaving just
# "teacher".

# A real report found the earlier version of this regex only worked when
# the sentence ended with an explicit "job"/"role" keyword - "I want to
# prepare software tester JOB" matched, but the equally natural "I want
# to prepare Junior Python Full Stack Developer" (no trailing keyword at
# all) did not. Made that trailing word optional to catch both. Making it
# optional on its own introduces a new risk though: "prepare for MY
# INTERVIEW" or "prepare for my scheduled interview" would otherwise get
# "my"/"my scheduled" extracted as if that were a literal role name -
# this is specifically the OTHER request (their own real, scheduled
# interview), not a named role, and needs to be rejected here so it
# falls through to the AI, which already handles that case correctly.

_INTERVIEW_PREP_NON_ROLE_WORDS = {
    "my", "the", "a", "an", "this", "that", "next", "upcoming",
    "scheduled", "interview", "job", "role", "position",
}


def _extract_interview_prep_role(message):
    """The named role from a 'prepare for X job' style message, or None
    if nothing meaningful was actually named (e.g. "prepare for my
    interview" - that's a reference to their own real interview, not a
    role name, and must fall through to the AI instead)."""

    normalized = _normalize_shortcut(message)

    match = _INTERVIEW_PREP_REQUEST_RE.match(normalized)

    if not match:

        return None

    extracted = (
        match.group("job") or match.group("job2") or match.group("job3")
        or match.group("job4") or ""
    ).strip()

    meaningful = [
        w for w in extracted.split() if w not in _INTERVIEW_PREP_NON_ROLE_WORDS
    ]

    if not meaningful:

        return None

    return extracted


_STUDENT_SHORTCUTS = {
    "find jobs for me": ("find_matching_jobs", {}),
    "show me new jobs": ("find_matching_jobs", {"recent_only": True}),
    "show my notifications": ("get_notifications", {}),
    "update my profile": ("get_my_profile", {}),
    "show my profile": ("get_my_profile", {}),

    # "what is my resume score" and close variants - a very common,
    # basic question that slipped through: _IMPROVE_RESUME_RE only
    # matches phrases led by a verb (build/improve/raise...), and this
    # one is a plain "what is" question with no such verb, so it fell
    # through to a full AI call for no reason, same class of gap as
    # every other shortcut in this file.
    "what is my resume score": ("get_resume_feedback", {}),
    "whats my resume score": ("get_resume_feedback", {}),
    "what's my resume score": ("get_resume_feedback", {}),
    "my resume score": ("get_resume_feedback", {}),
    "show my resume score": ("get_resume_feedback", {}),
    "show me my resume score": ("get_resume_feedback", {}),
    "what is my resume score out of 100": ("get_resume_feedback", {}),

    # "any jobs i saved" and close variants - a very common, plain
    # question about bookmarked jobs that had zero shortcut coverage,
    # even though get_saved_jobs is an existing, working, instant tool.
    "any jobs i saved": ("get_saved_jobs", {}),
    "show my saved jobs": ("get_saved_jobs", {}),
    "show saved jobs": ("get_saved_jobs", {}),
    "my saved jobs": ("get_saved_jobs", {}),
    "saved jobs": ("get_saved_jobs", {}),
    "show me my saved jobs": ("get_saved_jobs", {}),
    "what jobs have i saved": ("get_saved_jobs", {}),
    "which jobs did i save": ("get_saved_jobs", {}),

    # "is my resume ATS friendly" had ZERO shortcut coverage, meaning it
    # needed TWO separate live Groq calls just to get started: the
    # orchestrator's own "what tool should I call" decision, THEN the
    # ATS tool's real analysis call - two separate chances to hit the
    # shared quota, for one of the most common questions in the whole
    # app. Routed directly now, skipping the orchestrator call entirely -
    # down to exactly one real AI call (the genuine analysis itself,
    # which can never be avoided), with the existing busy-fallback and
    # 5-minute cache still fully in effect either way. This also feeds
    # the semantic matcher (built FROM this dict), so close variants in
    # different word orders are covered too without needing a separate
    # hand-written regex.
    "is my resume ats friendly": ("check_ats_friendliness", {}),
    "is the resume ats friendly": ("check_ats_friendliness", {}),
    "is the uploaded resume ats friendly": ("check_ats_friendliness", {}),
    "is my resume ats friendly or not": ("check_ats_friendliness", {}),
    "check my resume ats friendliness": ("check_ats_friendliness", {}),
    "check if my resume is ats friendly": ("check_ats_friendliness", {}),
    "is my resume ats friendly or not need to improve something": ("check_ats_friendliness", {}),
}


# A leading conversational preamble ("can you please tell me...", "could
# you...") before the REAL question - a real report found "can you please
# tell me how many jobs i have applied" failing to match, while the bare
# "how many jobs i have applied" (asked moments later) worked instantly.
# Stripped here, at the single shared normalization point every shortcut/
# regex/semantic check goes through, so every one of them benefits
# without needing its own separate fix. Checked against every existing
# exact-phrase entry first - none of them start with these words, so
# this can't silently break an existing match.

_LEADING_FILLER_RE = re.compile(
    r"^(?:can\s+you\s+|could\s+you\s+|would\s+you\s+|please\s+|pls\s+)*"
    r"(?:tell\s+me\s+|let\s+me\s+know\s+)?"
)


def _normalize_shortcut(message):

    text = re.sub(r"[^a-z0-9 ]+", "", (message or "").lower())

    text = re.sub(r"\s+", " ", text).strip()

    return _LEADING_FILLER_RE.sub("", text).strip()


def _handle_student_shortcut(profile, user, message):
    """Runs a button's tool directly. Returns a reply dict, or None to
    carry on with the normal AI flow (not a button text, or the tool
    raised)."""

    normalized = _normalize_shortcut(message)

    entry = _STUDENT_SHORTCUTS.get(normalized)

    if not entry and normalized in _NEW_JOBS_PHRASES:

        entry = ("find_matching_jobs", {"recent_only": True})

    if not entry and _PROFILE_MATCH_RE.match(normalized):

        entry = ("find_matching_jobs", {})

    if not entry and _wants_all_jobs(normalized):

        entry = ("list_open_jobs", {})

    if not entry and (normalized in _APPLICATION_STATUS_PHRASES or _MY_APPLICATIONS_RE.match(normalized)):

        entry = ("get_application_status", {})

    if not entry:

        interview_args = _interview_check_args(normalized)

        if interview_args is not None:

            entry = ("get_upcoming_interviews", interview_args)

    if not entry and _RESUME_SCORE_RE.match(normalized):

        entry = ("get_resume_feedback", {})

    if not entry and _SKILL_SUGGESTION_RE.match(normalized):

        entry = ("get_skill_suggestions", {})

    if not entry and _SAVED_JOBS_RE.match(normalized):

        entry = ("get_saved_jobs", {})

    if not entry and _IMPROVE_RESUME_RE.match(normalized):

        entry = ("get_resume_feedback", {})

    if not entry and _PLAIN_JOBS_RE.match(normalized):

        # "show me jobs" / "show jobs" / "find jobs" / "get jobs" / bare
        # "jobs" - checked LAST so anything more specific (new jobs, all
        # jobs, jobs matching my profile) is still caught first by the
        # checks above. This is an extremely common, plain way to ask,
        # and it used to fall through to a full AI call for no reason -
        # meaning it needed a live Groq call, and a live Groq call means
        # it's exposed to the shared account's tight quota, for a
        # question that has no reason to ever fail that way.
        #
        # Defaults to EVERY open job (same as list_open_jobs / "show all
        # jobs"), matching what the Jobs tab itself shows - a plain
        # "show jobs" reads as "show me the jobs" in general, not
        # specifically "find jobs that match my profile". That more
        # personalised search is still one explicit phrase away: "find
        # jobs for me" (the exact shortcut above) and "jobs that match
        # my profile" (_PROFILE_MATCH_RE) both still give the filtered,
        # profile-matched answer, unchanged. "show my jobs" is
        # deliberately NOT included here, since that phrasing could
        # just as easily mean "my applications".

        entry = ("list_open_jobs", {})

    if not entry:

        prep_role = _extract_interview_prep_role(message)

        if prep_role:

            prep_executor = TOOL_EXECUTORS.get("get_interview_prep")

            try:

                prep_result = prep_executor(profile, user, {"job_title": prep_role})

            except Exception as e:

                print("Chatbot shortcut error: get_interview_prep", e)

                prep_result = None

            if prep_result is not None and "job_title" in prep_result:

                # A real application/interview WAS found for this role -
                # the tool's own summary already has the real skills and
                # description in it, so this is safe to answer directly,
                # zero further AI calls.

                return _build_tool_payload(
                    _friendly_fast_text("get_interview_prep", prep_result),
                    [(None, "get_interview_prep", prep_result)],
                )

            # Nothing found for this role - do NOT return the bare
            # "not found" message here. Falling through to the normal AI
            # flow instead lets the "give genuinely useful general
            # advice" instruction apply, the same as asking this
            # un-shortcut-matched would already do.

    if not entry:

        # Last resort before falling through to the AI: semantic
        # matching against every phrase already known to the exact
        # dicts/regexes above - catches a paraphrase or word-order
        # variant of a KNOWN question type without needing it hand-added.

        entry = _student_semantic_matcher.match(message)

    if not entry:

        return None

    tool_name, args = entry

    executor = TOOL_EXECUTORS.get(tool_name)

    if not executor:

        return None

    started = time.monotonic()

    try:

        result = executor(profile, user, dict(args))

    except Exception as e:

        print("Chatbot shortcut error:", tool_name, e)

        return None

    print(f"[chatbot] shortcut {tool_name} took {time.monotonic() - started:.2f}s")

    return _build_tool_payload(
        _friendly_fast_text(tool_name, result),
        [(None, tool_name, result)],
    )


# The company portal had NO equivalent of the student shortcuts above -
# every company question, however simple ("who are the candidates?", "show
# my interviews"), needed a full live AI call with no fast path at all,
# unlike the student side. Mirrors _STUDENT_SHORTCUTS/_handle_student_shortcut
# exactly: common, plain company questions answered instantly, zero AI calls,
# so they can never fail from the shared account's tight quota.

# A general "what have we posted" question - needs no specific job
# name at all, unlike every other existing company shortcut/tool here.
_COMPANY_JOBS_POSTED_RE = re.compile(
    r"^(?:what|which)\s+jobs?\s+(?:have\s+we\s+|did\s+we\s+|have\s+i\s+|did\s+i\s+)?post(?:ed)?\??$"
    r"|^(?:show|list|see|display)\s+(?:me\s+)?(?:our\s+|my\s+)?(?:posted\s+)?jobs?(?:\s+posted)?$"
    r"|^any\s+jobs?\s+posted\??$"
    r"|^jobs?\s+(?:we\s+|i\s+)?posted$"
    r"|^(?:our|my)\s+(?:posted\s+)?jobs?$"
)


_COMPANY_SHORTCUTS = {
    "who are the candidates": ("get_company_applications", {}),
    "who are my candidates": ("get_company_applications", {}),
    "show me candidates": ("get_company_applications", {}),
    "show candidates": ("get_company_applications", {}),
    "show me the candidates": ("get_company_applications", {}),
    "show my candidates": ("get_company_applications", {}),
    "show applications": ("get_company_applications", {}),
    "show my applications": ("get_company_applications", {}),
    "show me applications": ("get_company_applications", {}),
    "who applied": ("get_company_applications", {}),
    "recent applications": ("get_company_applications", {}),
    "show recent applications": ("get_company_applications", {}),

    "show interviews": ("get_company_interviews", {}),
    "show my interviews": ("get_company_interviews", {}),
    "show me interviews": ("get_company_interviews", {}),
    "upcoming interviews": ("get_company_interviews", {}),
    "show upcoming interviews": ("get_company_interviews", {}),
    "show my upcoming interviews": ("get_company_interviews", {}),

    "show my jobs": ("get_active_job_postings", {}),
    "show active jobs": ("get_active_job_postings", {}),
    "show my active jobs": ("get_active_job_postings", {}),
    "my job postings": ("get_active_job_postings", {}),
    "show job postings": ("get_active_job_postings", {}),
    "show my job postings": ("get_active_job_postings", {}),

    "show all my jobs": ("list_all_job_postings", {}),
    "show all jobs": ("list_all_job_postings", {}),
    "show all job postings": ("list_all_job_postings", {}),
    "all my jobs": ("list_all_job_postings", {}),
    "list my jobs": ("list_all_job_postings", {}),
    "list all my jobs": ("list_all_job_postings", {}),

    "show analytics": ("get_company_analytics_summary", {}),
    "show my analytics": ("get_company_analytics_summary", {}),
    "show me analytics": ("get_company_analytics_summary", {}),
    "show my stats": ("get_company_analytics_summary", {}),
    "show company stats": ("get_company_analytics_summary", {}),
    "how many applications": ("get_company_analytics_summary", {}),

    "show my profile": ("get_company_profile_info", {}),
    "show company profile": ("get_company_profile_info", {}),
    "my company profile": ("get_company_profile_info", {}),
    "show my company profile": ("get_company_profile_info", {}),

    "same name candidates applied jobs": ("get_duplicate_candidate_names", {}),
    "same name candidates": ("get_duplicate_candidate_names", {}),
    "candidates with same name": ("get_duplicate_candidate_names", {}),
    "candidates with the same name": ("get_duplicate_candidate_names", {}),
    "duplicate candidates": ("get_duplicate_candidate_names", {}),
    "duplicate candidate names": ("get_duplicate_candidate_names", {}),
    "same name applicants": ("get_duplicate_candidate_names", {}),
    "any duplicate candidates": ("get_duplicate_candidate_names", {}),
    "show duplicate candidates": ("get_duplicate_candidate_names", {}),
}


def _last_bot_asked_which_job_for_candidates(history):
    """True if the bot's own last message was asking the recruiter
    which role to show top candidates for - so a bare reply naming a
    job ("Senior Frontend Developer") is the ANSWER to that question,
    not a new, separate request that needs its own live AI call to
    interpret. Loose keyword match (not an exact phrase), since the
    model writes this question in its own words each time - same
    approach as _last_bot_asked_for_skills."""

    text = _last_bot_text(history)

    return "candidates" in text and ("role" in text or "job" in text) and "?" in text


def _looks_like_a_job_reply(message):
    """'Senior Frontend Developer' / 'Software Tester' - a bare job
    name, not a new sentence/question. Same shape check as
    _looks_like_skill_list, just applied to a job-name reply."""

    return _looks_like_skill_list(message)


def _handle_company_shortcut(profile, user, message, history=None):
    """Same idea as _handle_student_shortcut: runs a common company
    question's tool directly, zero AI calls. Returns a reply dict, or
    None to carry on with the normal AI flow (not a recognised
    shortcut, or the tool raised)."""

    normalized = _normalize_shortcut(message)

    entry = _COMPANY_SHORTCUTS.get(normalized)

    if not entry and _COMPANY_JOBS_POSTED_RE.match(normalized):

        # A real report found general "what jobs have we posted" style
        # questions getting no instant answer at all, even though
        # get_active_job_postings needs no specific job name - every
        # existing company shortcut/tool here was built around a NAMED
        # job (candidates for X, description of X), leaving the plain
        # "show me everything we've posted" question with no fast path.

        entry = ("get_active_job_postings", {})

    if not entry and _last_bot_asked_which_job_for_candidates(history) and _looks_like_a_job_reply(message):

        # The bot just asked "which role?" - this bare reply IS the
        # job name, answered directly with zero AI calls instead of
        # needing another live call just to notice what its own
        # previous question was asking for.

        entry = ("get_top_candidates_for_job", {"job_title": message.strip()})

    if not entry:

        # Same last-resort semantic matching as the student handler -
        # see the SEMANTIC SHORTCUT MATCHING block above for why.

        entry = _company_semantic_matcher.match(message)

    if not entry:

        return None

    tool_name, args = entry

    executor = COMPANY_TOOL_EXECUTORS.get(tool_name)

    if not executor:

        return None

    started = time.monotonic()

    try:

        result = executor(profile, user, dict(args))

    except Exception as e:

        print("Chatbot company shortcut error:", tool_name, e)

        return None

    print(f"[chatbot] company shortcut {tool_name} took {time.monotonic() - started:.2f}s")

    return _build_tool_payload(
        _user_facing(result.get("summary", "Here's what I found.")),
        [(None, tool_name, result)],
    )


# Same idea as _COMPANY_SHORTCUTS/_handle_company_shortcut: the placement
# admin portal had NO fast path at all either - every question, however
# simple ("show all drives", "pending company approvals"), needed a full
# live AI call. These answer instantly, zero AI calls, so they can never
# fail from the shared account's tight quota.

# "how many students are applied for a job" (and similar grammar
# variants) - a generic application-count question, no specific job
# named, answered from get_placement_overview's total_applications,
# the same approach as _MY_APPLICATIONS_RE on the student side:
# catching the natural GRAMMAR rather than needing every individual
# wording added by hand as each new variant gets reported.

_HOW_MANY_APPLIED_RE = re.compile(
    r"^how\s+many\s+(students?|applicants?|people)\s+(are\s+|have\s+)?applied"
    r"(\s+(for|to))?(\s+(a\s+job|the\s+job|jobs?))?\??$"
)

# A real report found "how many students applied for Junior Python Full
# Stack Developer" answered with a platform-wide total, not that job's -
# because the only placement tool that existed had no job filter at all,
# so it was used regardless. Extracts the named job, routed directly to
# get_candidate_pipeline WITH that job_title, which now correctly scopes
# both the count and the candidate list to it.

_APPLIED_FOR_JOB_RE = re.compile(
    r"^how\s+many\s+(?:students?|applicants?|people)\s+(?:are\s+|have\s+)?applied\s+(?:for|to)\s+(?:the\s+|a\s+)?(?P<job>.+?)(?:\s+job)?\??$"
    r"|^(?:show|list)\s+(?:me\s+)?applicants?\s+for\s+(?:the\s+)?(?P<job2>.+?)(?:\s+job)?$"
    r"|^(?:show|list)\s+(?:me\s+)?candidates?\s+for\s+(?:the\s+)?(?P<job3>.+?)(?:\s+job)?$"
)


def _extract_applied_for_job(message):
    """The named job from a 'how many applied for X' style placement-
    admin message, or None."""

    normalized = _normalize_shortcut(message)

    match = _APPLIED_FOR_JOB_RE.match(normalized)

    if not match:

        return None

    return (
        match.group("job") or match.group("job2") or match.group("job3") or ""
    ).strip() or None


# General job-posting questions ("what are the jobs are posted", "how
# many jobs are posted") - need no specific company/status, unlike
# every exact-phrase entry below which was built around named filters.
_PLACEMENT_JOBS_POSTED_RE = re.compile(
    r"^(?:what|which)\s+(?:are\s+the\s+)?jobs?\s+(?:are\s+|have\s+been\s+|were\s+)?posted\??$"
    r"|^(?:show|list|see|display)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:active\s+|posted\s+)?jobs?$"
    r"|^how\s+many\s+(?:active\s+)?jobs?\s+(?:are\s+|have\s+been\s+|were\s+)?posted\??$"
    r"|^how\s+many\s+active\s+jobs?\s+(?:are\s+)?available\??$"
    r"|^how\s+many\s+jobs?\s+(?:are\s+there|in\s+total)\??$"
)


_PLACEMENT_SHORTCUTS = {
    "show all drives": ("get_placement_drives", {}),
    "show drives": ("get_placement_drives", {}),
    "show upcoming drives": ("get_placement_drives", {}),
    "show placement drives": ("get_placement_drives", {}),
    "upcoming drives": ("get_placement_drives", {}),
    "show all upcoming placement drives": ("get_placement_drives", {}),

    "show pending company approvals": ("get_pending_company_approvals", {}),
    "pending company approvals": ("get_pending_company_approvals", {}),
    "show pending approvals": ("get_pending_company_approvals", {}),
    "which companies need approval": ("get_pending_company_approvals", {}),
    "companies awaiting approval": ("get_pending_company_approvals", {}),

    "show unverified students": ("get_unverified_students", {}),
    "unverified students": ("get_unverified_students", {}),
    "which students need verification": ("get_unverified_students", {}),
    "show students not verified": ("get_unverified_students", {}),

    "show placement overview": ("get_placement_overview", {}),
    "placement overview": ("get_placement_overview", {}),
    "how are we doing": ("get_placement_overview", {}),
    "whats our placement rate": ("get_placement_overview", {}),
    "what is our placement rate": ("get_placement_overview", {}),
    "show placement stats": ("get_placement_overview", {}),

    "show placement report": ("get_placement_report", {}),
    "placement report": ("get_placement_report", {}),

    "show candidate pipeline": ("get_candidate_pipeline", {}),
    "candidate pipeline": ("get_candidate_pipeline", {}),
    "show the pipeline": ("get_candidate_pipeline", {}),

    "find jobs": ("find_jobs_platform_wide", {}),
    "show jobs": ("find_jobs_platform_wide", {}),
    "show me jobs": ("find_jobs_platform_wide", {}),
    "show all jobs": ("find_jobs_platform_wide", {}),
    "find jobs for me": ("find_jobs_platform_wide", {}),

    "company insights": ("get_company_insights", {}),
    "show company insights": ("get_company_insights", {}),
    "tell me about our companies": ("get_company_insights", {}),
    "show all companies": ("get_company_insights", {}),

    "give me students name": ("list_students", {}),
    "give me student names": ("list_students", {}),
    "show me students": ("list_students", {}),
    "show students": ("list_students", {}),
    "list students": ("list_students", {}),
    "show all students": ("list_students", {}),
    "students name": ("list_students", {}),
    "student names": ("list_students", {}),
}


# =====================================================
# SEMANTIC SHORTCUT MATCHING
#
# Every shortcut above (and the regexes near them) exists for one reason:
# a plain, common question should never need a live Groq call, so it can
# never fail from the shared account's tight quota. The exact-phrase
# dicts and regexes work well, but every new way a real person phrases
# the SAME question ("i saved any jobs" vs "any jobs i saved") has had
# to be found through a real bug report and hand-added - a losing game
# long-term, since there's always a phrasing not yet seen.
#
# This generalizes it: TF-IDF + cosine similarity (NOT a heavy embedding
# model - no PyTorch, no GPU, no multi-hundred-MB download, safe for a
# free-tier server) trained on the exact-phrase dicts that already exist
# above, so there is no new "truth" to maintain separately - every fix
# already made is automatically part of this too. At runtime, a message
# that doesn't exactly match anything is compared to every known example;
# close enough (by both an absolute similarity THRESHOLD and a MARGIN
# over the next-best, different-intent match) routes to that shortcut,
# otherwise it falls through to the normal AI flow exactly as before -
# this only ever adds coverage, never removes the existing fallback.
#
# Deliberately conservative: a wrong match here is worse than falling
# through to the AI (a confidently wrong instant answer beats nothing,
# but is still wrong), so the threshold/margin were tuned against a real
# adversarial test set - not just the positive cases - before being used
# for anything live. Only ever built from READ-ONLY shortcut entries, so
# it can never accidentally route a message to a write action.
# =====================================================

SEMANTIC_MATCH_THRESHOLD = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.70"))

SEMANTIC_MATCH_MARGIN = float(os.getenv("SEMANTIC_MATCH_MARGIN", "0.08"))

# Cosine similarity alone isn't enough: "what jobs did I apply to IN
# CHENNAI" scored a PERFECT 1.000 against the plain "what jobs did i
# apply to" in testing - TF-IDF doesn't notice that "chennai" is new,
# meaningful information the fixed-args shortcut has no way to act on.
# Same failure for "did i apply to SOFTWARE TESTER" (a specific job)
# and "is my resume ATS FRIENDLY" (a genuinely different, AI-requiring
# check) - both scored well above threshold against a more general
# known phrase. A word the query introduces that ISN'T in the matched
# training phrase (beyond ordinary filler) is exactly the signal that
# the question is MORE SPECIFIC than anything this shortcut can
# actually answer - so even a high-confidence match is rejected if it
# introduces any such word.

_SEMANTIC_FILLER_WORDS = {
    "please", "the", "a", "an", "to", "for", "of", "me", "my",
    "is", "are", "i", "any", "it", "above",
}


def _novel_and_missing_word_counts(query_words, phrase_words):
    """
    (novel, missing): words the QUERY adds beyond the matched training
    phrase, and significant words from the PHRASE the query leaves out -
    both checked, not just one. Novel words catch a MORE SPECIFIC
    question ("...in Chennai", "...for Software Tester") that the
    shortcut's fixed args can't actually answer. Missing words catch
    the opposite failure: a bare, ambiguous fragment like "did i
    apply" (no object at all) scoring deceptively high against a full
    phrase like "did i apply any jobs" purely because every one of its
    few words happens to already appear there - a real but incomplete
    question deserves the AI's judgment, not a confident guess.
    """

    query_set, phrase_set = set(query_words), set(phrase_words)

    novel = sum(
        1 for w in query_set
        if w not in phrase_set and w not in _SEMANTIC_FILLER_WORDS
    )

    missing = sum(
        1 for w in phrase_set
        if w not in query_set and w not in _SEMANTIC_FILLER_WORDS
    )

    return novel, missing


class _SemanticShortcutMatcher:
    """Fit once (at import time) on a role's known phrase -> (tool, args)
    examples; .match(message) returns (tool, args) or None at runtime.
    Fitting is near-instant (tens of short phrases), and matching a single
    message is a single sparse vector transform + cosine similarity - both
    negligible compared to a network round trip to Groq, let alone a
    rate-limited one."""

    def __init__(self, entries):  # entries: {phrase: (tool, args)}

        self.phrases = list(entries.keys())

        self.tools_and_args = list(entries.values())

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), analyzer="word")

        self.matrix = self.vectorizer.fit_transform(self.phrases)

    def match(self, message):

        normalized = _normalize_shortcut(message)

        if not normalized:

            return None

        query_words = normalized.split()

        query_vec = self.vectorizer.transform([normalized])

        similarities = cosine_similarity(query_vec, self.matrix)[0]

        # Pass 1: any training phrase with a PERFECT word overlap (after
        # stripping filler) - every significant query word is in it, and
        # every significant one of ITS words is in the query. This is
        # checked across EVERY phrase, regardless of raw TF-IDF score,
        # because that raw score can be misleading: a LONGER, differently
        # -worded phrase for the exact same tool ("check if my resume is
        # ats friendly") can outscore the one that's actually a perfect
        # match ("is my resume ats friendly") purely due to how TF-IDF
        # weights shared terms - checking only the top-ranked candidate
        # (or even several ranked candidates above a score threshold)
        # missed a real match whenever the correct phrase didn't happen to
        # be the highest-SCORING one. A perfect word-for-word match is its
        # own strong confidence signal and doesn't need the raw score to
        # additionally confirm it.

        perfect_matches = [
            i for i in range(len(self.phrases))
            if _novel_and_missing_word_counts(
                query_words, self.phrases[i].split()
            ) == (0, 0)
        ]

        if perfect_matches:

            chosen_idx = max(perfect_matches, key=lambda i: similarities[i])

        else:

            # Pass 2: no perfect word-overlap anywhere - fall back to the
            # plain similarity threshold for a genuinely fuzzy paraphrase,
            # still only accepted if it ALSO has zero novel/missing words
            # (the guard against a MORE SPECIFIC or a too-bare question
            # silently matching something it shouldn't).

            order = similarities.argsort()[::-1]

            if similarities[order[0]] < SEMANTIC_MATCH_THRESHOLD:

                return None

            chosen_idx = None

            for idx in order:

                if similarities[idx] < SEMANTIC_MATCH_THRESHOLD:

                    break

                novel, missing = _novel_and_missing_word_counts(
                    query_words, self.phrases[idx].split()
                )

                if novel == 0 and missing == 0:

                    chosen_idx = idx

                    break

            if chosen_idx is None:

                return None

        chosen_tool = self.tools_and_args[chosen_idx][0]

        order_all = similarities.argsort()[::-1]

        runner_up_idx = next(
            (i for i in order_all if i != chosen_idx), chosen_idx
        )

        runner_up_tool = self.tools_and_args[runner_up_idx][0]

        margin = similarities[chosen_idx] - similarities[runner_up_idx]

        if runner_up_tool != chosen_tool and margin < SEMANTIC_MATCH_MARGIN:

            # Ambiguous - the chosen match and the next-best DIFFERENT
            # tool aren't confidently far apart. Safer to let the
            # normal AI flow handle it.

            return None

        tool, args = self.tools_and_args[chosen_idx]

        return tool, dict(args)


def _build_semantic_examples(*sources):
    """Merges any number of {phrase: (tool, args)} / {phrase} (implying
    (tool, args) given separately) dicts into one flat training set,
    skipping anything already covered - the semantic matcher's whole
    point is to catch what the exact dicts DON'T, so there's no reason
    to duplicate entries that already match exactly."""

    merged = {}

    for source in sources:

        merged.update(source)

    return merged


_STUDENT_SEMANTIC_EXAMPLES = _build_semantic_examples(
    _STUDENT_SHORTCUTS,
    {phrase: ("find_matching_jobs", {"recent_only": True}) for phrase in _NEW_JOBS_PHRASES},
    {phrase: ("get_application_status", {}) for phrase in _APPLICATION_STATUS_PHRASES},
)

_COMPANY_SEMANTIC_EXAMPLES = dict(_COMPANY_SHORTCUTS)

_PLACEMENT_SEMANTIC_EXAMPLES = dict(_PLACEMENT_SHORTCUTS)

_student_semantic_matcher = _SemanticShortcutMatcher(_STUDENT_SEMANTIC_EXAMPLES)

_company_semantic_matcher = _SemanticShortcutMatcher(_COMPANY_SEMANTIC_EXAMPLES)

_placement_semantic_matcher = _SemanticShortcutMatcher(_PLACEMENT_SEMANTIC_EXAMPLES)


def _handle_placement_shortcut(profile, user, message):
    """Same idea as _handle_student_shortcut/_handle_company_shortcut:
    runs a common placement-admin question's tool directly, zero AI
    calls. Returns a reply dict, or None to carry on with the normal
    AI flow (not a recognised shortcut, or the tool raised)."""

    normalized = _normalize_shortcut(message)

    entry = _PLACEMENT_SHORTCUTS.get(normalized)

    if not entry and _HOW_MANY_APPLIED_RE.match(normalized):

        entry = ("get_placement_overview", {})

    if not entry:

        applied_job = _extract_applied_for_job(message)

        if applied_job:

            pipeline_executor = PLACEMENT_TOOL_EXECUTORS.get("get_candidate_pipeline")

            try:

                pipeline_result = pipeline_executor(profile, user, {"job_title": applied_job})

            except Exception as e:

                print("Chatbot placement shortcut error: get_candidate_pipeline", e)

                pipeline_result = None

            if pipeline_result is not None and pipeline_result.get("candidates"):

                # A real job match was found - safe to answer directly.
                # If nothing was found, fall through to the normal AI
                # flow instead (same safety pattern as interview prep
                # elsewhere in this file), so the admin still gets a
                # sensible clarifying response rather than a bare
                # "no applications found" with no further help.

                return _build_tool_payload(
                    _user_facing(pipeline_result.get("summary", "Here's what I found.")),
                    [(None, "get_candidate_pipeline", pipeline_result)],
                )

    if not entry and _PLACEMENT_JOBS_POSTED_RE.match(normalized):

        # A real report found "what are the jobs are posted" and "how
        # many jobs are posted" both failing - find_jobs_platform_wide
        # already existed and needs no specific company/status to
        # answer either one, but no phrasing routed to it at all.

        entry = ("find_jobs_platform_wide", {})

    if not entry:

        # Same last-resort semantic matching as the student/company
        # handlers - see the SEMANTIC SHORTCUT MATCHING block above.

        entry = _placement_semantic_matcher.match(message)

    if not entry:

        return None

    tool_name, args = entry

    executor = PLACEMENT_TOOL_EXECUTORS.get(tool_name)

    if not executor:

        return None

    started = time.monotonic()

    try:

        result = executor(profile, user, dict(args))

    except Exception as e:

        print("Chatbot placement shortcut error:", tool_name, e)

        return None

    print(f"[chatbot] placement shortcut {tool_name} took {time.monotonic() - started:.2f}s")

    return _build_tool_payload(
        _user_facing(result.get("summary", "Here's what I found.")),
        [(None, tool_name, result)],
    )


def _build_tool_payload(final_text, executed):
    """
    Merges the structured data from every executed tool into one response
    for the frontend. Lists (cards) always come straight from the tools'
    own return values - never from anything the model wrote.
    """

    result_payload = {"reply": final_text}

    refresh = []

    for call, name, result in executed:

        for key in _FORWARDED_LIST_KEYS:

            if key in result:

                existing = result_payload.get(key)

                if isinstance(existing, list) and isinstance(result[key], list):

                    result_payload[key] = existing + result[key]

                elif key not in result_payload:

                    result_payload[key] = result[key]

        # Resume/document download - forwarded as its own small object
        # (not a URL) so the frontend triggers a real authenticated blob
        # download button.

        if result.get("resume_id") and "resume_download" not in result_payload:

            result_payload["resume_download"] = {
                "resume_id": result["resume_id"],
                "filename": result.get("filename", "Resume"),
            }

        if result.get("score_report") and "mock_interview_report" not in result_payload:

            result_payload["mock_interview_report"] = result["score_report"]

        # "Apply to X? [buttons]" prompts (whether from apply_to_job or a
        # best-job recommendation) carry a hidden marker so a later
        # "write a cover letter and apply" with no job named still knows
        # which job that prompt was about.

        for marker_key in ("awaiting_cover_letter_job_id", "awaiting_apply_decision_job_id"):

            if result.get(marker_key) and marker_key not in result_payload:

                result_payload[marker_key] = result[marker_key]

        # Yes / No style buttons (e.g. the apply confirmation)

        for reply_text in result.get("quick_replies") or []:

            result_payload.setdefault("quick_replies", [])

            if reply_text not in result_payload["quick_replies"]:

                result_payload["quick_replies"].append(reply_text)

        if name in _REFRESH_AFTER and result.get("success"):

            for tab in _REFRESH_AFTER[name]:

                if tab not in refresh:

                    refresh.append(tab)

    # Only auto-navigate when there was a single action - with several
    # results at once there is no single "right" tab to open.

    if len(executed) == 1 and executed[0][2].get("navigate_to"):

        result_payload["navigate_to"] = executed[0][2]["navigate_to"]

    if refresh:

        result_payload["refresh"] = refresh

    # Suggested next steps - only when nothing else already offered buttons.

    if not result_payload.get("quick_replies"):

        chips = _next_step_chips(executed)

        if chips:

            result_payload["quick_replies"] = chips

    return result_payload


# ------------------------------- staying on topic -------------------------------
#
# This assistant is for placements and the job portal. A message that is clearly
# about something else ("i want to prepare lunch today") gets a short polite
# refusal and NOTHING else - no model call, no tool, no record created. It is a
# deliberately conservative list (a message containing ANY career word is never
# blocked), so a real question is never refused; anything unusual that isn't on
# the list is left to the prompt's strict scope rule, and the write tools below
# still refuse to act unless the user actually asked for the action.

_OFF_TOPIC_WORDS = {
    # cooking and meals
    "lunch", "dinner", "breakfast", "recipe", "recipes", "cook", "cooking",
    "cooked", "biryani", "pizza", "burger", "snack", "snacks", "hungry",
    # weather, entertainment, sports, chit-chat
    "weather", "forecast", "movie", "movies", "film", "films", "song",
    "songs", "lyrics", "netflix", "anime", "cartoon", "bollywood",
    "kollywood", "tollywood", "celebrity", "gossip", "cricket", "football",
    "ipl", "fifa", "joke", "jokes", "riddle", "riddles", "poem", "poems",
    "horoscope", "astrology",
    # relationships and politics
    "girlfriend", "boyfriend", "dating", "election", "elections",
    "politics", "politician",
    # financial/commodity prices - a real report found "today gold rate"
    # fell through to the generic technical error instead of the normal
    # off-topic redirect, since no category here covered it at all.
    "gold", "silver", "bitcoin", "crypto", "cryptocurrency", "sensex",
    "nifty", "stockmarket", "sharemarket",
}

_OFF_TOPIC_PHRASES = (
    "tell me a story", "bedtime story", "sing a song", "write a poem",
    "write me a poem", "write a story", "write a song", "capital of",
    "who invented", "who is the prime minister", "who is the president",
    "who won the", "how far is", "recipe for", "how to cook", "how to bake",
    "how to make tea", "how to make coffee",
)

_CAREER_WORDS = {
    "job", "jobs", "career", "careers", "interview", "interviews", "mock",
    "resume", "resumes", "cv", "apply", "applied", "applying", "application",
    "applications", "skill", "skills", "placement", "placements", "company",
    "companies", "drive", "drives", "hiring", "hire", "hired", "salary",
    "salaries", "offer", "offers", "candidate", "candidates", "cgpa",
    "eligible", "eligibility", "profile", "notification", "notifications",
    "portal", "ats", "cover", "letter", "internship", "internships",
    "fresher", "freshers", "aptitude", "employer", "recruiter", "recruiters",
    "shortlist", "shortlisted", "vacancy", "vacancies",
}

# words that make something a sentence, not a list of skills

_SENTENCE_WORDS = {
    "i", "want", "to", "my", "is", "am", "are", "the", "today", "please",
    "would", "like", "need", "how", "what", "when", "why", "can", "you", "me",
}

_OFF_TOPIC_REPLIES = {
    "student": (
        "That's outside what I can help with - I'm here for placements and "
        "your job search: jobs, applications, interviews, mock interviews, "
        "your resume and skills.",
        ["Find jobs for me", "Start a mock interview", "Help me improve my resume"],
    ),
    "company": (
        "That's outside what I can help with - I'm here for hiring on this "
        "portal: your job postings, applicants, interviews and analytics.",
        ["Show my applications", "Find candidates with Python skills"],
    ),
    "placement_admin": (
        "That's outside what I can help with - I'm here for placement "
        "management: students, companies, drives, applications and reports.",
        ["How are we doing overall?", "Show the candidate pipeline"],
    ),
}


def _is_clearly_off_topic(message):

    text = " ".join(re.findall(r"[a-z0-9']+", (message or "").lower()))

    words = set(text.split())

    if not words or words & _CAREER_WORDS:

        return False

    if words & _OFF_TOPIC_WORDS:

        return True

    return any(phrase in text for phrase in _OFF_TOPIC_PHRASES)


def _last_bot_text(history):
    """What the assistant said last (lower-case), or ''."""

    if not history:

        return ""

    last = history[-1]

    if isinstance(last, dict) and last.get("sender") == "bot":

        return (last.get("message") or "").lower()

    return ""


def _last_bot_asked_for_skills(history):

    text = _last_bot_text(history)

    return "skill" in text and "?" in text


def _looks_like_skill_list(message):
    """'Cooking, Baking' / 'Selenium, API Testing' - not 'i want to ...'."""

    words = re.findall(r"[a-z0-9+#.']+", (message or "").lower())

    return 0 < len(words) <= 6 and not (set(words) & _SENTENCE_WORDS)


def _off_topic_applies(message, history):
    """True when this message should get the polite refusal. Never true for
    someone mid cover-letter, or answering "which skills?" with a skill list."""

    if not _is_clearly_off_topic(message):

        return False

    if _awaiting_cover_letter_job(history):

        return False

    if _last_bot_asked_for_skills(history) and _looks_like_skill_list(message):

        return False

    return True


def _off_topic_reply(role):

    text, chips = _OFF_TOPIC_REPLIES.get(
        role,
        ("That's outside what I can help with - I only help with placements "
         "and the job portal.", []),
    )

    payload = {"reply": text + (" Want to try one of these?" if chips else "")}

    if chips:

        payload["quick_replies"] = list(chips)

    return payload


# An action that writes data must be something the user actually asked for. If the
# model calls one on a message that doesn't ask for it (it once raised a placement
# query because someone typed "i want to prepare lunch today"), it is NOT run.

_AFFIRMATIVE_RE = re.compile(
    r"^\s*(yes|yeah|yep|yup|ok|okay|sure|please|go ahead|do it|confirm|send it)\b",
    re.IGNORECASE,
)

_QUERY_INTENT_RE = re.compile(
    r"\b(quer(y|ies)|ticket|complain\w*|placement (team|officer|office|cell|"
    r"department|staff|coordinator)|(contact|ask|tell|message|inform) "
    r"(the )?placement|write to (the )?placement|report (a |an |this )?"
    r"(problem|issue|bug))\b",
    re.IGNORECASE,
)

_SLOT_INTENT_RE = re.compile(
    r"\binterview\b.*\b(slot|schedule|reschedule|book|arrange|date|time|request)\b"
    r"|\b(slot|schedule|reschedule|book|arrange)\b.*\binterview\b",
    re.IGNORECASE,
)

_SKILL_INTENT_RE = re.compile(
    r"\b(skills?|add|learn(t|ed)?|know|include|put|have)\b", re.IGNORECASE
)


_PROJECT_INTENT_RE = re.compile(
    r"\b(projects?|add|built|build|made|make|created?|working on|worked on)\b",
    re.IGNORECASE,
)

_INTENT_MISSING_REPLIES = {
    "raise_placement_query": (
        "I haven't sent anything to the placement team, because I wasn't sure "
        "that's what you wanted. If you'd like me to, tell me what to ask them - "
        "for example: \"Raise a query: my resume upload isn't working\"."
    ),
    "request_interview_slot": (
        "I haven't requested an interview slot. If you want one, say something "
        "like: \"Request an interview slot for my Software Tester interview\"."
    ),
    "update_my_skills": (
        "I haven't changed your skills. To add some, tell me which ones - for "
        "example: \"Add Selenium and API Testing to my skills\"."
    ),
    "update_my_projects": (
        "I haven't added anything to your projects. To add one, tell me "
        "about it - for example: \"Add a project called Travel Booking "
        "Website\"."
    ),
}


def _affirming_a_proposal(message, history, needles):
    """'yes' / 'ok please' right after the assistant offered to do it."""

    if not _AFFIRMATIVE_RE.match(message or ""):

        return False

    last = _last_bot_text(history)

    return any(needle in last for needle in needles)


def _write_intent_missing(name, message, history):
    """True if `name` is a write action the user did NOT ask for."""

    text = message or ""

    if name == "raise_placement_query":

        ok = bool(_QUERY_INTENT_RE.search(text)) or _affirming_a_proposal(
            text, history, ("placement team", "query")
        )

    elif name == "request_interview_slot":

        ok = bool(_SLOT_INTENT_RE.search(text)) or _affirming_a_proposal(
            text, history, ("slot",)
        )

    elif name == "update_my_skills":

        ok = bool(_SKILL_INTENT_RE.search(text)) or _last_bot_asked_for_skills(history)

    elif name == "update_my_projects":

        ok = bool(_PROJECT_INTENT_RE.search(text))

    else:

        return False

    return not ok


def generate_reply(user, message, history=None, page_context=None):
    """Public entry point. Gives each chat message its own AI time
    budget (see GROQ_REQUEST_BUDGET), then runs the real logic."""

    _start_request_clock()

    try:

        return _generate_reply_inner(user, message, history, page_context)

    finally:

        _stop_request_clock()


def _generate_reply_inner(user, message, history=None, page_context=None):
    """
    history: optional list of {"sender": "user"|"bot", "message": "..."}
    for short conversational continuity.

    page_context: optional dict from the frontend describing where the
    user currently is (e.g. {"page": "student/jobs", "job_id": 12}).

    Returns either a plain string (guests, placement_admin/super_admin,
    or any tool-less reply) or a dict {"reply": ..., plus extra keys
    like "matched_jobs"/"candidates"/"resume_download"/"navigate_to"/
    "refresh"} when a tool ran.
    """

    # ---------------- AI SECURITY (Requirement 31) ----------------
    # Recruiters legitimately ask about candidates, so the
    # "other students" probe filter only applies to non-company users.

    # Companies legitimately search/see their own candidates, and a
    # placement admin legitimately sees platform-wide student/company
    # data by design - the probe filter only protects a STUDENT from
    # seeing another student's private data.

    if (
        getattr(user, "role", None) not in ("company", "placement_admin")
        and _is_security_probe(message)
    ):

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

    elif role == "placement_admin":

        # No per-user profile object to scope actions to (placement
        # admin tools operate platform-wide) - pass user itself so the
        # tool-calling machinery still has a non-None actor_profile.

        actor_profile = user

        tool_schemas = PLACEMENT_TOOL_SCHEMAS

        tool_executors = PLACEMENT_TOOL_EXECUTORS

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

        # Abandoned sessions expire after 30 minutes, so the student
        # isn't stuck answering an old interview forever.

        if active_session and timezone.now() - active_session.created_at > timedelta(minutes=30):

            active_session.status = "cancelled"

            active_session.save()

            active_session = None

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

    # ---------------- OFF-TOPIC GUARD ----------------
    # Placed after the mock-interview check on purpose: an answer inside a
    # mock interview is never treated as off-topic.

    if _off_topic_applies(message, history):

        return _off_topic_reply(role)

    # ---------------- APPLY CONFIRMATION (Yes / No buttons) ----------------
    # Handled without the AI: "Yes, apply to X at Y" creates the
    # application, "No, cancel" drops it. The AI itself can never apply.

    if role == "company" and actor_profile:

        # Same idea as the student shortcuts below: a plain, common
        # company question ("who are the candidates?", "show my
        # interviews") answered directly, no AI call - the company
        # portal never had this fast path before.
        #
        # Wrapped in its own try/except: an unhandled exception ANYWHERE
        # inside the shortcut/semantic-matching machinery used to
        # propagate all the way up and crash the whole Django view with
        # a raw 500 error page (confirmed from a real report - the
        # browser console showed Django's own error page, not the
        # normal graceful "trouble reaching the assistant" message).
        # Falling through to the normal AI flow on any such failure is
        # strictly safer than a 500, and costs nothing extra when
        # nothing actually goes wrong.

        try:

            company_shortcut_reply = _handle_company_shortcut(
                actor_profile, user, message, history
            )

        except Exception as e:

            print("Chatbot company shortcut crashed:", e)

            company_shortcut_reply = None

        if company_shortcut_reply is not None:

            return company_shortcut_reply

    if role == "placement_admin" and actor_profile:

        # Same idea again: a plain, common placement-admin question
        # ("show all drives", "pending company approvals") answered
        # directly, no AI call - this portal never had this fast
        # path either. Same crash-safety wrapping as above.

        try:

            placement_shortcut_reply = _handle_placement_shortcut(
                actor_profile, user, message
            )

        except Exception as e:

            print("Chatbot placement shortcut crashed:", e)

            placement_shortcut_reply = None

        if placement_shortcut_reply is not None:

            return placement_shortcut_reply

    if role == "student" and actor_profile:

        # A tap on one of the chat's own buttons ("Find jobs for me",
        # "Show my notifications", ...) - answered directly, no AI call.
        # Same crash-safety wrapping as above - this is the exact path
        # a real report traced a raw Django 500 error back to.

        try:

            shortcut_reply = _handle_student_shortcut(actor_profile, user, message)

        except Exception as e:

            print("Chatbot student shortcut crashed:", e)

            shortcut_reply = None

        if shortcut_reply is not None:

            return shortcut_reply

        confirmation_reply = _handle_apply_confirmation(
            actor_profile, user, message
        )

        if confirmation_reply is not None:

            return confirmation_reply

        # "Add a cover letter for X at Y" (the third button under a job
        # recommendation) - asks the student to type it next.

        cover_request_reply = _handle_cover_letter_request(
            actor_profile, user, message
        )

        if cover_request_reply is not None:

            return cover_request_reply

        # "Write a cover letter for me and apply to X" (with or without a
        # job named) - generates the letter and applies immediately. Must
        # be checked BEFORE the pending-manual-text handler below, so
        # changing your mind mid-typing doesn't get saved as literal text.

        ai_cover_reply = _handle_ai_cover_letter_apply(
            actor_profile, user, message, history
        )

        if ai_cover_reply is not None:

            return ai_cover_reply

        # The assistant just asked "type your cover letter" - this message
        # IS that cover letter (unless it's a cancel or a fresh pointer).

        pending_cover_reply = _handle_pending_cover_letter_text(
            actor_profile, user, message, history
        )

        if pending_cover_reply is not None:

            return pending_cover_reply

        # "apply above job" / "yes apply" - resolved from the jobs just shown

        reference_reply = _handle_apply_reference(
            actor_profile, user, message, history
        )

        if reference_reply is not None:

            return reference_reply

        # "teacher job i want to apply" - a job NAMED in the message

        named_reply = _handle_named_apply(actor_profile, user, message, history)

        if named_reply is not None:

            return named_reply

    # ---------------- SHORTLIST / REJECT CONFIRMATION (Yes / No) ----------------
    # Same safety pattern as the student apply flow: the AI can only ask
    # "Shortlist X for Y? Tap Yes" - the actual status change happens here,
    # deterministically, never from the AI's own judgment.

    if role == "company" and actor_profile:

        candidate_action_reply = _handle_candidate_action_confirmation(
            actor_profile, user, message
        )

        if candidate_action_reply is not None:

            return candidate_action_reply

    context = build_context(user)

    knowledge = get_knowledge_base_snippets()

    system_prompt = SYSTEM_TEMPLATE.format(
        # India Standard Time specifically - see _india_now()'s own
        # comment for why timezone.now() alone was silently wrong here
        # (raw UTC, not even the server's own configured timezone).
        current_datetime=_india_now().strftime("%A, %b %d, %Y, %I:%M %p") + " IST",
        context_json=json.dumps(context, default=str),
        knowledge_json=json.dumps(knowledge, default=str),
    )

    setting = get_active_chatbot_setting()

    if setting and setting.system_prompt:

        system_prompt += (
            "\n\nADDITIONAL INSTRUCTIONS FROM PLACEMENT ADMIN:\n"
            + setting.system_prompt
        )

    if role == "student":

        shown_now = _shown_jobs_from_history(history)

        if shown_now:

            system_prompt += (
                "\n\nJOBS SHOWN IN YOUR PREVIOUS MESSAGE (cards): "
                + "; ".join(
                    f"{i}. {j.title} at "
                    f"{j.company.company_name if j.company else 'Company'}"
                    for i, j in enumerate(shown_now, start=1)
                )
                + ". When the student says 'above', 'that job', 'this "
                "one' or 'the first one' they mean these - never a job "
                "from earlier in the conversation."
            )

    page_desc = _describe_page(page_context)

    if page_desc:

        system_prompt += (
            "\n\nCURRENT PAGE: " + page_desc +
            " If the student says 'this job', 'this role' or 'apply here', "
            "they mean the job named above."
        )

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # A student's baseline request (system prompt + tool schemas alone) is
    # already close to or over Groq's free-tier 8000-tokens-per-minute cap
    # on the smallest fallback model - confirmed by real Render logs
    # showing "Requested 8091, Limit 8000" on ordinary requests. History
    # was widened from 6 to 12 turns for a more natural, remembers-more
    # conversation, but every extra turn sent is real tokens added on top
    # of that already-tight budget. Reverted back to 6 specifically
    # because the account is staying on the free tier - this is the one
    # safe, easy token saving available without touching the prompt or
    # tool descriptions themselves, which encode specific, hard-won
    # routing fixes that would be risky to trim carelessly.

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

            return _clean_reply(_call_groq_plain(messages))

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

        return _clean_reply(choice_message.content or "")

    # ---------------------------- agent loop ----------------------------
    # Run the tools the model asked for, show it the results, and let it
    # decide whether it needs another lookup or is ready to answer - up to
    # _MAX_TOOL_ROUNDS times. The same call is never run twice, a write only
    # ever prepares a confirmation and ends the loop, and every model call
    # still shares the one time budget for this message.

    all_executed = []

    seen_calls = set()

    model_text = None

    for _round in range(_MAX_TOOL_ROUNDS):

        fresh_calls = []

        for call in tool_calls:

            signature = _call_signature(call)

            if signature not in seen_calls:

                seen_calls.add(signature)

                fresh_calls.append(call)

        if not fresh_calls:

            break

        # A write the user didn't ask for is not run - the model is told so
        # and the reply explains what to say if they DO want it.

        allowed_calls = []

        blocked_calls = []

        for call in fresh_calls:

            if _write_intent_missing(call.function.name, message, history):

                blocked_calls.append(call)

            else:

                allowed_calls.append(call)

        executed = (
            _execute_tool_calls(allowed_calls, tool_executors, actor_profile, user)
            if allowed_calls else []
        )

        for call in blocked_calls:

            print("[chatbot] not run - the user didn't ask for it:", call.function.name)

            executed.append((
                call,
                call.function.name,
                {
                    "failed": True,
                    "success": False,
                    "summary": _INTENT_MISSING_REPLIES[call.function.name],
                },
            ))

        # A single tool that couldn't run, before anything else worked:
        # same plain message as before.

        if len(executed) == 1 and executed[0][2].get("failed") and not all_executed:

            return executed[0][2]["summary"]

        all_executed.extend(executed)

        _append_tool_round(messages, choice_message, executed)

        if _round_is_final(all_executed, message):

            break

        # Out of rounds: go straight to the final text pass rather than
        # asking for more tool calls that would only be thrown away.

        if _round == _MAX_TOOL_ROUNDS - 1:

            break

        try:

            response = _call_groq_with_tools(messages, tool_schemas)

        except Exception as e:

            print("Chatbot follow-up error:", e)

            break

        choice_message = response.choices[0].message

        tool_calls = getattr(choice_message, "tool_calls", None)

        if not tool_calls:

            model_text = _clean_reply(choice_message.content or "")

            break

    # These are shown to the user word for word, so any that were written
    # for the AI ("...the student's skills") are turned into second person.

    write_summaries = [
        _user_facing(result.get("summary", "Done."))
        for _call, name, result in all_executed
        if name in _WRITE_ACTION_TOOLS
    ]

    read_items = [
        item for item in all_executed
        if item[1] not in _WRITE_ACTION_TOOLS
    ]

    first_name = all_executed[0][1]

    first_result = all_executed[0][2]

    if (
        len(all_executed) == 1
        and first_name == "start_mock_interview"
        and first_result.get("question")
    ):

        # The interviewer question is already exactly what should be
        # shown - skipping another model pass means it's never
        # paraphrased, shortened, or mixed with commentary.

        final_text = first_result["question"]

    elif not read_items:

        final_text = "\n\n".join(write_summaries) or "Done."

    elif not write_summaries and model_text:

        # The model looked at the results and answered in its own words.

        final_text = model_text

    elif (
        not write_summaries
        and _can_skip_text_pass(all_executed)
        and _is_simple_request(message)
    ):

        final_text = _fast_reply_text(all_executed)

    else:

        try:

            # tool_choice="none": this last pass only writes the reply text
            # (the loop ended, or ran out of rounds).

            final_response = _call_groq_with_tools(
                messages, tool_schemas, tool_choice="none"
            )

            final_text = _clean_reply(final_response.choices[0].message.content or "")

        except Exception as e:

            print("Chatbot follow-up error:", e)

            final_text = ""

        if not final_text:

            final_text = " ".join(
                _user_facing(result.get("summary", "Here's what I found."))
                for _call, _name, result in read_items
            )

        if write_summaries:

            final_text = final_text + "\n\n" + "\n\n".join(write_summaries)

    return _build_tool_payload(final_text, all_executed)
