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

from datetime import timedelta

from django.utils import timezone

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

HOW TO TALK: you are a warm, sharp career mentor having a real conversation,
not a search box. Answer the question that was actually asked, in natural
sentences, the way a knowledgeable person would say it out loud. Use what was
said earlier in this conversation - "it", "that one", "the second job" mean
what they meant a moment ago. Be direct and concrete: use the real names,
numbers and dates from the data. Keep replies short unless the question needs
depth. Never open with filler ("Sure!", "Great question!") and never answer
with just a label like "Here are your applications." - say something useful
about what the data shows: what stands out, what needs attention.

ASK WHEN IT MATTERS: if a request is ambiguous, or you are missing something
you truly need (which job? which company? which date?), ask ONE short
clarifying question - offering two or three concrete options when that helps -
instead of guessing or giving a vague answer. Never ask permission for a
read-only lookup; just do it. When a natural next step would genuinely help,
end with one short suggestion or question (not every time, and never more
than one).

WORK LIKE AN AGENT: work out what the person is really trying to achieve, then
use your tools to get the facts you need - and use several in a row when one
answer depends on another (for example: find jobs, then get the details of the
best one, then say what is missing). Lookups need no permission. Anything that
changes data (applying, adding skills, shortlisting, rejecting, raising a query)
is only ever PREPARED by you and confirmed by the user tapping a button - say
clearly what you are about to do and why, and never claim it is done. If a step
fails, say what failed and what you will do instead. Never invent data: if you
don't have it, say so and use a tool or ask.

TOPIC SCOPE (strict): you help with placements and careers ONLY - job search,
applications, interviews and mock interviews, resumes, skills, career guidance,
placement drives, the user's own portal data (profile, applications,
notifications), and (for a company) hiring, candidates and analytics. That
includes teaching what a student needs for their search: interview questions and how to answer them,
technical topics they will be asked about in interviews, resume and cover letter
writing, salary and offer questions, and study plans for a role.
EVERYTHING ELSE is off-topic: cooking and meals (lunch, recipes), health,
movies, songs, games, sports, weather, news, politics, shopping, travel,
relationships, jokes, stories, homework unrelated to career prep, and general
knowledge. For an off-topic message reply with ONE short friendly sentence
saying you can only help with placements and this job portal, and offer two or
three things you can do. Do not answer the off-topic question itself, not even
briefly. Never call a tool, raise a query, add a skill or take any action because
of an off-topic message, and never treat an off-topic message as the answer to a
question you just asked.

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
job postings, analytics, or their own company profile. For a
placement admin, this includes overall placement stats, pending
company approvals, unverified students, placement drives, one
company's history, the placement report, or the platform-wide
candidate pipeline - these tools are read-only for now, so if asked
to approve a company, verify a student, or send a notification,
explain that action isn't available in chat yet and point them to
the matching admin page. Only call
apply_to_job when a student clearly, explicitly asks to apply to a
specific named job, and only call update_my_skills when they clearly,
explicitly ask to add/update a skill - never as a side effect of a
general question or a casual mention of a skill in conversation.
When a job in a find_matching_jobs/check_job_eligibility/get_saved_jobs
result has already_applied set to true, tell the student they've
already applied to it instead of inviting them to apply again.

AI-WRITTEN COVER LETTERS: if a student asks you to write their cover
letter and apply, or to auto-generate one, do NOT draft it yourself in a
chat reply and do NOT call apply_to_job for this - you have no way to
pass free text into it. Instead tell them to say something like "write a
cover letter for me and apply to <job>" (or point out the "Write a cover
letter for me and apply" button under a job recommendation), which
triggers the real letter-writing and application together.

NEVER CLAIM AN ACTION SUCCEEDED WITHOUT CALLING THE TOOL (critical):
you must NEVER say an application was submitted, a query was raised,
an interview slot was requested, a skill was added, or a candidate was
shortlisted/rejected unless you ACTUALLY called the matching tool
(apply_to_job, raise_placement_query, request_interview_slot,
update_my_skills, shortlist_candidate, reject_candidate) in this exact
turn and it returned success. Saying "done"/"submitted"/"added"/
"shortlisted"/"rejected" in plain text without calling the tool is
strictly forbidden, even if the request sounds simple or you're
confident what the user wants - always call the real tool instead of
describing the action as if it happened. shortlist_candidate and
reject_candidate never change anything by themselves either - like
apply_to_job, they only ask the recruiter to confirm with Yes/No
buttons; the status changes only after the recruiter taps Yes.
If the student refers to a job by a pronoun ("apply to that job",
"the above one", "yes apply"), look at the most recent job list you
showed them in this conversation to resolve the exact job_title, then
call apply_to_job with that resolved title - do not guess and do not
skip the tool call because the title wasn't spelled out this turn.

APPLYING TO A JOB (confirmation required): apply_to_job never submits an
application itself - it only asks the student "Apply to X at Y?" and shows
Yes / No buttons. The application is submitted by the system only after the
student taps Yes. So after calling apply_to_job do not say the application
was sent, and never claim it was submitted yourself; the tool's own question
is the reply. When calling it, pass ONLY the job title in job_title (for
example "Software Tester") and the company separately in company_name - never
join them as "Software Tester - TechNova". If the student says "yes apply",
"apply above job" or similar right after you showed a job, use that job's
title and company from the card you just showed.

PLAIN TEXT ONLY: the chat window does not render markdown, so never use
**bold**, # headings or markdown links - write plain sentences.

NAMED JOB + WANTS TO APPLY: if the student names a specific job and says they
want to apply ("teacher job i want to apply", "apply to Software Tester"),
call apply_to_job for THAT job. Never answer with check_job_eligibility or
a general list of jobs instead - they asked about one job, so the answer
must be about that job: the confirmation, or exactly why they can't apply,
followed by the jobs they can apply to.

ANSWER WITH THE REAL DETAIL, NOT A COUNT: when a tool returns a list of
issues, suggestions, missing information, or similar findings, your reply
must actually name them - a few sentences or a short list - never just
"found 3 issues" with nothing else. A count alone forces the student to ask
a follow-up you can't yet answer, since the real detail was never written
down anywhere. Before calling an analysis tool (resume/ATS check, job
eligibility, etc.) again, check whether you already gave the real detail
earlier in this SAME conversation - if so, answer the follow-up directly
from what you already said, instead of quietly re-running the whole
analysis again (each run is a real cost, takes real time, and can return
a slightly different result each time, which only confuses the student).
Only re-run it if something genuinely changed (a new resume was uploaded,
a different role was named) or the student explicitly asks you to re-check.

THREE DIFFERENT JOB QUESTIONS - never mix them up:
- "New / latest / recently posted jobs" = a plain list of what was recently
  uploaded (find_matching_jobs with recent_only true). Do not analyse their
  profile or list what they are missing.
- "Jobs for me / that match my profile / suitable for me" = the profile-matched
  answer (find_matching_jobs, recent_only false): what they can apply to, and
  what blocks the rest.
- "Show all jobs / the list of jobs / the jobs tab / what jobs are open / even
  the ones I'm not eligible for" = EVERY open job (list_open_jobs). Show them
  all; the cards say which are applied, eligible or not eligible. Never answer
  this with only the jobs they qualify for.

MORE THAN ONE REQUEST: if the student asks for several things at once (for
example "show my applications and my interviews"), call all the matching
tools in the same turn (up to 3) instead of only the first one. When one
answer depends on another (for example "find the best job and tell me what
I'm missing for it"), call the tools one after another: look at the first
result, then call the next tool with what you learned.

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
as the real buttons on those cards. Do not re-list them item by
item in text. Instead say something useful ABOUT them in one to three short
sentences - how many there are, which one stands out (the best match, the one
with an interview coming up, the one that needs attention) and what the person
could do next. The cards carry the detail; you add the insight.

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

INTERVIEW STATUS QUESTIONS (important): "any interview updates", "do I have
interviews", "when is my interview" and similar are asking about REAL
scheduled interviews, not application labels - always call
get_upcoming_interviews (or trust upcoming_interviews/interviews_this_week
in CURRENT USER DATA below, since it is rebuilt fresh every message) for
these. NEVER conclude "no interviews scheduled" just because
get_application_status didn't attach interview details to an application -
a candidate can have a real, upcoming interview even while their
application status says "Selected" or "Shortlisted", so check the
authoritative source before saying there is nothing scheduled.

NEVER ANSWER A DATA REQUEST WITHOUT CALLING THE TOOL (critical): if the
student asks to see or check something real - "show me my applications",
"show my interview status", "any interview updates", "show my
notifications", "show saved jobs" and similar - you must call the
matching tool THIS turn and build your reply from its actual result.
Never write a vague acknowledgment like "Here are your current
applications." or "Here's your interview status." with no real names,
dates, or numbers in it - that sentence is worthless without the tool
call behind it, and the student can tell. This applies even when the
request is phrased as a follow-up ("and show me my interview status",
"now show my applications") right after another question - a follow-up
phrasing is not a reason to skip the tool call or assume the earlier
answer already covered it; each such request needs its own fresh tool
call, since applications, interviews, and notifications change over
time and the student is asking to see the CURRENT state, not a repeat
of something said earlier in this conversation.

LIVE DATA OVER CHAT HISTORY (important): the CURRENT USER DATA JSON
below is rebuilt fresh from the real database on every single message -
it is always more current than anything said earlier in this
conversation. If an interview you mentioned in an earlier reply is no
longer listed in upcoming_interviews/interviews_this_week here, it has
already happened - do not keep repeating its date/time as if it's still
upcoming just because you said so previously in this chat. Always trust
this fresh data over your own prior messages. This also applies to the
resume score - if an earlier reply in this chat mentioned a different
resume score, ignore it and use the current official score below.

CAREER PLAN: when get_career_plan runs, do not just list resume score,
missing skills, job matches, and application status as separate,
disconnected facts - build ONE prioritized action plan that actually
cross-references them. For example, if the resume score is low AND a
missing skill also appears as a requirement on one of the top job
matches, call that out explicitly as the highest priority, since
fixing it helps both at once. A sensible default order: (1) resume
fixes if the score is weak, (2) the single most-recommended skill to
learn next, (3) which specific matched job to prioritize applying to
and why, (4) interview prep if next_interview is present. Keep it to
4-6 concrete, numbered steps - not a wall of text repeating every
field in the data.

RESUME SCORE (critical): the student's resume has exactly ONE official
score - the resume_score saved by the AI analysis on the Resume page.
It appears in CURRENT USER DATA under resume.score, and as
resume_score or resume.score in the get_resume_feedback,
check_ats_friendliness and get_career_plan results. Always quote that
exact number. Never calculate, estimate, adjust or invent a different
resume score or percentage yourself, and never present an ATS check
as a separate score - it only provides issues and suggestions. If the
student wants a new score after editing their resume, tell them to
upload the new version or click "Analyse Resume" on the Resume page.

BEST-JOB QUESTIONS (important): when the student asks which job is
best / most preferred / most suitable for them, or which one to apply
to first, do NOT just list everything. Call find_matching_jobs with
limit=1 (or limit=3 for "top jobs"), then reply by naming the single
best job and giving 1-2 sentences of specific reasons taken from the
tool result's reasons/match_score (e.g. which of their skills match).
If two jobs have the same match score, say so honestly and mention
what differs. Do not set recent_only for these questions unless the
student says "new". Keep it short - the job card below already shows
the details.

MATCH SCORE VS ELIGIBILITY (important): these are two separate,
unrelated checks - a student can have a high match_score (their SKILLS
overlap with the job) while still being INELIGIBLE (they fail a hard
requirement like minimum CGPA, department, graduation year, or age).
A good match percentage never overrides an eligibility failure. If a
student asks why they can't apply despite a good match, explain this
distinction plainly and point to the specific eligibility reason
given (e.g. "your 52% match means your skills fit well, but this role
separately requires a 7.0+ CGPA and you have 6.98 - that's a fixed
requirement the skill match doesn't change").

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

CURRENT DATE AND TIME: {current_datetime}. Always compare any
date/time you mention (interviews, deadlines, drives) against this
exact moment before describing it. If it's earlier today or on an
earlier date, it has ALREADY HAPPENED - say so plainly (e.g. "Your
interview was earlier today at 7:01 AM - I hope it went well! Want
to share how it went, or look at other matching jobs?") instead of
presenting it as upcoming with forward-looking prep advice. If it's
later today, say it's today and roughly how soon (e.g. "in about 3
hours"). Only treat something as genuinely upcoming if its date/time
is after this current moment.

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

    jobs = Job.objects.filter(
        status="active", is_active=True
    ).select_related("company").order_by("-created_at")[:40]

    ranked_all = rank_jobs_for_student(profile, jobs)

    if not ranked_all:

        return {
            "kind": "all_jobs",
            "matched_jobs": [],
            "total_open": 0,
            "summary": "There are no open jobs right now.",
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
            f"{total} open job{'s' if total != 1 else ''}: you can apply to "
            f"{can_apply}, you've already applied to {applied_count}, and "
            f"{blocked_count} need something your profile doesn't have yet"
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
        "navigate_to": f"/student/jobs/{job.id}",
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
                "date": upcoming_iv.interview_date.strftime("%b %d, %Y"),
                "time": upcoming_iv.interview_date.strftime("%I:%M %p"),
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
        "navigate_to": "/student/interviews",
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

        qs = qs.filter(application__job__title__icontains=job_title)

    interview = qs.first()

    if interview:

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

    apps_qs = Application.objects.filter(
        student=profile
    ).select_related("job", "job__company").order_by("-applied_date")

    if job_title:

        apps_qs = apps_qs.filter(job__title__icontains=job_title)

    application = apps_qs.first()

    if application:

        job = application.job

        skills_required = [
            s.strip() for s in (job.skills_required or "").split(",")
            if s.strip()
        ]

        company_name = job.company.company_name if job.company else "Company"

        return {
            "job_title": job.title,
            "company": company_name,
            "interview_scheduled": False,
            "application_status": application.get_status_display(),
            "skills_required": skills_required,
            "job_description": getattr(job, "description", "") or "",
            "summary": (
                f"No interview is scheduled yet for {job.title} at "
                f"{company_name} (application status: "
                f"{application.get_status_display()}), but here's what "
                "to prepare based on the role's real requirements."
            ),
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

        return {
            "has_resume": True,
            "resume_score": resume.resume_score,
            "summary": (
                "I couldn't run the ATS check just now - the AI service "
                f"is temporarily busy. Your official resume score is "
                f"still {resume.resume_score}/100 either way. Please "
                "try the ATS check again in a minute."
            ),
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
            "date": upcoming_interview.interview_date.strftime("%b %d, %Y"),
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
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
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
                "skills, description) to generate genuinely tailored "
                "preparation suggestions or practice questions - not "
                "generic advice. Use when the student asks how to "
                "prepare for an interview OR to prepare for/study for "
                "a job they've applied to, even with no interview "
                "scheduled yet - it falls back to the real application "
                "in that case, so never refuse this just because "
                "nothing is booked yet."
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
            "date": iv.interview_date.strftime("%b %d, %Y"),
            "time": iv.interview_date.strftime("%I:%M %p"),
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
]


COMPANY_TOOL_EXECUTORS = {
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
    as get_job_description on the company side.
    """

    from django.db.models import Q
    from jobsystem.models import Job

    company_name = (args.get("company_name") or "").strip()

    status_filter = (args.get("status") or "").strip().lower()

    jobs_qs = Job.objects.select_related("company")

    if company_name:

        jobs_qs = jobs_qs.filter(
            company__company_name__icontains=company_name
        )

    if status_filter in {"active", "pending", "closed", "rejected"}:

        jobs_qs = jobs_qs.filter(status=status_filter)

    jobs = list(jobs_qs.order_by("-created_at")[:15])

    if not jobs:

        if company_name:

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

        data.append({
            "title": job.title,
            "company": company,
            "status": status_label,
            "location": job.location or "",
            "salary": job.salary or "",
            "skills_required": job.skills_required or "",
        })

        lines.append(
            f"- {job.title} at {company} ({status_label}) - "
            f"{job.location or 'location not set'}, "
            f"{job.salary or 'salary not disclosed'}"
        )

    summary = f"{len(data)} job posting(s):\n\n" + "\n".join(lines[:8])

    return {
        "jobs": data,
        "navigate_to": "/placement/jobs",
        "summary": summary,
    }


def _tool_get_candidate_pipeline(profile, user, args):

    from jobsystem.models import Application

    apps = Application.objects.select_related(
        "student", "job", "job__company"
    ).order_by("-applied_date")[:15]

    candidates = [
        {
            "name": a.student.full_name,
            "job_title": a.job.title,
            "company": a.job.company.company_name if a.job.company else "",
            "status": a.get_status_display(),
        }
        for a in apps
    ]

    stats = {
        "total_applicants": Application.objects.count(),
        "shortlisted": Application.objects.filter(status="shortlisted").count(),
        "interviews_scheduled": Application.objects.filter(status="interview").count(),
        "final_selected": Application.objects.filter(status="selected").count(),
    }

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


PLACEMENT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "find_jobs_platform_wide",
            "description": (
                "Find job postings ACROSS THE WHOLE PLATFORM (every "
                "company, not one). Use for 'find jobs'/'jobs at "
                "<company>'/'show me jobs' style questions from the "
                "placement admin - this is the 'Find Jobs' capability "
                "advertised on this page."
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
            "name": "get_unverified_students",
            "description": (
                "Get students who haven't been verified yet. Use "
                "when asked which students still need verification."
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
                "Get the platform-wide candidate pipeline: recent "
                "applicants across every company, their job, and "
                "their current stage, plus pipeline stage counts. Use "
                "for 'show the candidate pipeline' or similar "
                "platform-wide (not one company's) requests."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


PLACEMENT_TOOL_EXECUTORS = {
    "get_company_insights": _tool_get_company_insights,
    "find_jobs_platform_wide": _tool_find_jobs_platform_wide,
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
}


def _can_skip_text_pass(executed):
    """True when every executed tool is a card-rendered list tool whose own
    summary is a fine reply (no AI re-wording needed)."""

    if not executed:

        return False

    for call, name, result in executed:

        if name not in _FAST_REPLY_TOOLS or result.get("failed"):

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
    "every", "whole", "complete", "full",
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

_MY_APPLICATIONS_RE = re.compile(
    r"^(?:what|which)\s+(?:are\s+the\s+)?jobs?\s+(?:did\s+i\s+|have\s+i\s+|i\s+)?"
    r"appl(?:y|ied)(?:\s+(?:to|for))?(?:\s+(?:recently|lately|so\s+far))?$"
    r"|^(?:i\s+|did\s+i\s+|have\s+i\s+)(?:already\s+)?appl(?:y|ied)\s+(?:to\s+)?(?:any\s+)?jobs?"
    r"(?:\s+(?:recently|lately|so\s+far))?$"
    r"|^any\s+jobs?\s+(?:did\s+i\s+|have\s+i\s+|i\s+)appl(?:y|ied)(?:\s+(?:to|for))?"
    r"(?:\s+(?:recently|lately|so\s+far))?$"
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

_IMPROVE_RESUME_RE = re.compile(
    r"^(?:i\s+want\s+to\s+|how\s+(?:to|do\s+i|can\s+i)\s+|please\s+)?"
    r"(?:buil\w*|improve\w*|increase\w*|raise\w*|boost\w*|get)\s+"
    r"(?:my\s+)?resume(?:s)?\s*"
    r"(?:score)?\s*"
    r"(?:is\s+|to\s+be\s+|to\s+|be\s+)?"
    r"(?:more\s+than|above|over|higher(?:\s+than)?|better(?:\s+than)?)?\s*\d*%?$"
)


_PLAIN_JOBS_RE = re.compile(
    r"^(?:please )?(?:show|find|get|give|see|display)"
    r"(?: me)?(?: the)?(?: available)? jobs?(?: for me)?(?: please)?$"
    r"|^jobs(?: for me)?$"
)


_STUDENT_SHORTCUTS = {
    "find jobs for me": ("find_matching_jobs", {}),
    "show me new jobs": ("find_matching_jobs", {"recent_only": True}),
    "show my notifications": ("get_notifications", {}),
    "update my profile": ("get_my_profile", {}),
    "show my profile": ("get_my_profile", {}),
}


def _normalize_shortcut(message):

    text = re.sub(r"[^a-z0-9 ]+", "", (message or "").lower())

    return re.sub(r"\s+", " ", text).strip()


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

    if not entry and _last_bot_asked_which_job_for_candidates(history) and _looks_like_a_job_reply(message):

        # The bot just asked "which role?" - this bare reply IS the
        # job name, answered directly with zero AI calls instead of
        # needing another live call just to notice what its own
        # previous question was asking for.

        entry = ("get_top_candidates_for_job", {"job_title": message.strip()})

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
}


def _handle_placement_shortcut(profile, user, message):
    """Same idea as _handle_student_shortcut/_handle_company_shortcut:
    runs a common placement-admin question's tool directly, zero AI
    calls. Returns a reply dict, or None to carry on with the normal
    AI flow (not a recognised shortcut, or the tool raised)."""

    normalized = _normalize_shortcut(message)

    entry = _PLACEMENT_SHORTCUTS.get(normalized)

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

        company_shortcut_reply = _handle_company_shortcut(
            actor_profile, user, message, history
        )

        if company_shortcut_reply is not None:

            return company_shortcut_reply

    if role == "placement_admin" and actor_profile:

        # Same idea again: a plain, common placement-admin question
        # ("show all drives", "pending company approvals") answered
        # directly, no AI call - this portal never had this fast
        # path either.

        placement_shortcut_reply = _handle_placement_shortcut(
            actor_profile, user, message
        )

        if placement_shortcut_reply is not None:

            return placement_shortcut_reply

    if role == "student" and actor_profile:

        # A tap on one of the chat's own buttons ("Find jobs for me",
        # "Show my notifications", ...) - answered directly, no AI call.

        shortcut_reply = _handle_student_shortcut(actor_profile, user, message)

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
        current_datetime=timezone.now().strftime("%A, %b %d, %Y, %I:%M %p"),
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
