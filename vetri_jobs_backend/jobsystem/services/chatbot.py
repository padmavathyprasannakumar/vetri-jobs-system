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

    # 4) New jobs from the last 3 days that the student hasn't applied to
    applied_ids = Application.objects.filter(
        student=profile
    ).values_list("job_id", flat=True)

    new_jobs = Job.objects.filter(
        status="active", is_active=True,
        created_at__gte=now - timedelta(days=3),
    ).exclude(id__in=applied_ids).count()

    if new_jobs:

        alerts.append({
            "key": f"newjobs:{new_jobs}:{now:%Y%m%d}",
            "type": "new_jobs",
            "text": (
                f"{new_jobs} new job(s) were posted in the last 3 days "
                "that you haven't applied to."
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

MORE THAN ONE REQUEST: if the student asks for several things at once (for
example "show my applications and my interviews"), call all the matching
tools in the same turn (up to 3) instead of only the first one.

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

    ranked = ranked[:limit]

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

    result = {
        "matched_jobs": matched_jobs,
        "navigate_to": "/student/jobs",
        "summary": (
            f"Found {len(matched_jobs)} newly posted job(s) the student hasn't applied to yet."
            if recent_only else
            (
                f"Top match for the student: {matched_jobs[0]['title']} "
                f"at {matched_jobs[0]['company']}."
                if limit < 5 else
                f"Found {len(matched_jobs)} jobs matching the student's profile."
            )
        ),
    }

    # A single recommended job gets one-tap Yes / No buttons, so "would you
    # like to apply?" can be answered right away.

    if limit == 1 and not matched_jobs[0]["already_applied"]:

        _best_job = ranked[0][0]

        result["quick_replies"] = [
            _apply_chip_text(_best_job),
            _cover_letter_chip_text(_best_job),
            _ai_cover_chip_text(_best_job),
            "No, cancel",
        ]

        result["awaiting_apply_decision_job_id"] = _best_job.id

    return result


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
    """Message explaining why the student can't apply, or None."""

    from jobsystem.models import Application
    from jobsystem.services.eligibility import check_eligibility

    company_name = job.company.company_name if job.company else "the company"

    if Application.objects.filter(student=profile, job=job).exists():

        return f"You've already applied to {job.title} at {company_name}."

    try:

        eligibility = check_eligibility(profile, job)

    except Exception:

        eligibility = {"eligible": True}

    if not eligibility.get("eligible", True):

        why = eligibility.get("reasons") or eligibility.get("reason") or ""

        if isinstance(why, (list, tuple)):

            why = "; ".join(str(w) for w in why)

        return (
            f"You're not eligible to apply to {job.title} at "
            f"{company_name} based on your current profile."
            + (f" Reason: {why}" if why else "")
        )

    return None


def _do_apply(profile, user, job, cover_letter=""):
    """The one place an application is actually created from chat."""

    from jobsystem.models import Application

    company_name = job.company.company_name if job.company else "the company"

    blocker = _apply_blocker(profile, job)

    if blocker:

        return {"success": False, "summary": blocker}

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

        return {"reply": blocker}

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

def _prepare_apply(profile, job):
    """Confirmation question + Yes/No buttons for one job (writes nothing)."""

    company_name = job.company.company_name if job.company else "the company"

    blocker = _apply_blocker(profile, job)

    if blocker:

        return {"success": False, "summary": blocker}

    confirm_text = _apply_chip_text(job)

    return {
        "success": False,
        "needs_confirmation": True,
        "job_id": job.id,
        "job_title": job.title,
        "company": company_name,
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

    payload = {"reply": result["summary"]}

    if result.get("quick_replies"):

        payload["quick_replies"] = result["quick_replies"]

    return payload


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

        return {"reply": blocker}

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

    return {
        "applications": applications,
        "has_interview_scheduled": has_interview_scheduled,
        "navigate_to": "/student/applications",
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

    return {
        "has_resume": True,
        "resume_score": resume.resume_score,
        "skills_detected": resume.skills,
        "missing_information": resume.missing_information,
        "suggested_job_categories": resume.job_categories,
        "navigate_to": "/student/resume",
        "summary": (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100."
        ),
    }


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

    return {
        "has_resume": True,
        "resume_score": resume.resume_score,
        "issues": result.get("issues", []),
        "suggestions": result.get("suggestions", []),
        "rewritten_bullets": result.get("rewritten_bullets", []),
        "summary": (
            f"Official resume score (same as the Resume page): "
            f"{resume.resume_score}/100. ATS check found "
            f"{len(result.get('issues', []))} issue(s) to fix."
        ),
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
            "description": (
                "Get the student's official resume score (the same "
                "score shown on the Resume page) and suggestions for "
                "improving it. Use for any question about the resume "
                "score."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_ats_friendliness",
            "description": (
                "Check the student's resume for ATS (Applicant "
                "Tracking System) problems and get concrete fix "
                "suggestions, optionally against a specific target "
                "job role. Returns the official resume score plus "
                "ATS issues/suggestions - it does not produce a "
                "separate score."
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
    "get_career_plan": _tool_get_career_plan,
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

    return {
        "companies": data,
        "navigate_to": "/placement/companies",
        "summary": (
            f"{len(data)} compan{'y' if len(data) == 1 else 'ies'} "
            "awaiting approval."
            if data else
            "No companies are awaiting approval right now."
        ),
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

    return {
        "students": data,
        "navigate_to": "/placement/students",
        "summary": (
            f"{len(data)} student(s) not yet verified."
            if data else
            "All students are verified."
        ),
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

    return {
        "drives": data,
        "navigate_to": "/placement/drives",
        "summary": (
            f"{len(data)} {status_filter} placement drive(s)."
            if data else
            f"No {status_filter} placement drives."
        ),
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

    return {
        "candidates": candidates,
        "navigate_to": "/placement/candidates/pipeline",
        "summary": (
            f"{stats['total_applicants']} total applicant(s), "
            f"{stats['shortlisted']} shortlisted, "
            f"{stats['interviews_scheduled']} in interview stage, "
            f"{stats['final_selected']} selected."
        ),
    }


PLACEMENT_TOOL_SCHEMAS = [
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


def _call_groq_with_tools(messages, tools, tool_choice="auto"):

    last_error = None

    for model_name in GROQ_MODEL_FALLBACKS:

        try:

            return client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
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
    "companies", "students",
)


# Tools that create/modify a real database record (or, for
# apply_to_job, ask the student to confirm one). Their own "summary" is
# used as the reply text - never a model paraphrase - so what the student
# reads always matches exactly what happened.

_WRITE_ACTION_TOOLS = {
    "apply_to_job", "request_interview_slot",
    "raise_placement_query", "update_my_skills",
    "shortlist_candidate", "reject_candidate",
}


# Tabs the frontend should reload after a successful chatbot action.

_REFRESH_AFTER = {
    "update_my_skills": ["profile", "dashboard", "jobs"],
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

            try:

                result = executor(actor_profile, user, args)

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

    return result_payload


def generate_reply(user, message, history=None, page_context=None):
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

    # ---------------- APPLY CONFIRMATION (Yes / No buttons) ----------------
    # Handled without the AI: "Yes, apply to X at Y" creates the
    # application, "No, cancel" drops it. The AI itself can never apply.

    if role == "student" and actor_profile:

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

    executed = _execute_tool_calls(
        tool_calls, tool_executors, actor_profile, user
    )

    # A single tool that couldn't run: same plain message as before.

    if len(executed) == 1 and executed[0][2].get("failed"):

        return executed[0][2]["summary"]

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
            # is appended to the reply automatically below.

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

    write_summaries = [
        result.get("summary", "Done.")
        for _call, name, result in executed
        if name in _WRITE_ACTION_TOOLS
    ]

    read_items = [
        item for item in executed
        if item[1] not in _WRITE_ACTION_TOOLS
    ]

    first_name = executed[0][1]

    first_result = executed[0][2]

    if (
        len(executed) == 1
        and first_name == "start_mock_interview"
        and first_result.get("question")
    ):

        # The interviewer question is already exactly what should be
        # shown - skipping the second Groq pass means it's never
        # paraphrased, shortened, or mixed with commentary.

        final_text = first_result["question"]

    elif not read_items:

        final_text = "\n\n".join(write_summaries) or "Done."

    else:

        try:

            # tool_choice="none": this second pass must only write the
            # reply text, never call another tool.

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

    return _build_tool_payload(final_text, executed)
