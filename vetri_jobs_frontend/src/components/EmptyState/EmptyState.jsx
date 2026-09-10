import React from "react";

import "./EmptyState.css";




// Lightweight inline SVGs — no external image files or network calls.
const ILLUSTRATIONS = {

    search: (
        <svg viewBox="0 0 160 120" fill="none">
            <circle cx="80" cy="55" r="42" fill="var(--empty-state-bg, #eef2ff)"/>
            <circle cx="72" cy="48" r="22" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="5" fill="white"/>
            <line x1="88" y1="64" x2="106" y2="82" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="6" strokeLinecap="round"/>
            <line x1="62" y1="48" x2="82" y2="48" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinecap="round" opacity=".5"/>
            <line x1="62" y1="56" x2="76" y2="56" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinecap="round" opacity=".5"/>
        </svg>
    ),

    folder: (
        <svg viewBox="0 0 160 120" fill="none">
            <circle cx="80" cy="60" r="46" fill="var(--empty-state-bg, #eef2ff)"/>
            <path d="M40 50h26l8 10h46a6 6 0 0 1 6 6v34a6 6 0 0 1-6 6H40a6 6 0 0 1-6-6V56a6 6 0 0 1 6-6Z"
            fill="white" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4"/>
            <path d="M34 60h92" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" opacity=".35"/>
        </svg>
    ),

    calendar: (
        <svg viewBox="0 0 160 120" fill="none">
            <circle cx="80" cy="60" r="46" fill="var(--empty-state-bg, #eef2ff)"/>
            <rect x="44" y="42" width="72" height="58" rx="8" fill="white" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4"/>
            <path d="M44 58h72" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4"/>
            <line x1="62" y1="34" x2="62" y2="50" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinecap="round"/>
            <line x1="98" y1="34" x2="98" y2="50" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinecap="round"/>
            <circle cx="80" cy="78" r="6" fill="var(--empty-state-accent, #4338ca)" opacity=".5"/>
        </svg>
    ),

    bell: (
        <svg viewBox="0 0 160 120" fill="none">
            <circle cx="80" cy="60" r="46" fill="var(--empty-state-bg, #eef2ff)"/>
            <path d="M80 36c-14 0-22 10-22 24v10l-8 12h60l-8-12V60c0-14-8-24-22-24Z"
            fill="white" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinejoin="round"/>
            <path d="M70 88a10 10 0 0 0 20 0" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinecap="round"/>
        </svg>
    ),

    inbox: (
        <svg viewBox="0 0 160 120" fill="none">
            <circle cx="80" cy="60" r="46" fill="var(--empty-state-bg, #eef2ff)"/>
            <path d="M40 52h20l8 14h24l8-14h20v34a6 6 0 0 1-6 6H46a6 6 0 0 1-6-6V52Z"
            fill="white" stroke="var(--empty-state-accent, #4338ca)" strokeWidth="4" strokeLinejoin="round"/>
        </svg>
    ),

};




// title: short heading. message: optional supporting line.
// icon: one of "search" | "folder" | "calendar" | "bell" | "inbox" (default "inbox").
// action: optional {label, onClick} for a small button (e.g. "Post a Job").
const EmptyState = ({
    title = "Nothing here yet",
    message,
    icon = "inbox",
    action,
})=>{

    return(

        <div className="empty-state">

            <div className="empty-state-illustration">
                {ILLUSTRATIONS[icon] || ILLUSTRATIONS.inbox}
            </div>

            <h3>{title}</h3>

            {
            message &&
            <p>{message}</p>
            }

            {
            action &&
            <button className="empty-state-action" onClick={action.onClick}>
                {action.label}
            </button>
            }

        </div>

    );

};


export default EmptyState;
