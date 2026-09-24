// src/api/chatbotHelpers.js
//
// Drop-in helpers for the chatbot frontend. Nothing here imports your
// axios instance or components, so no paths need changing - you pass
// what's needed in.

import { useEffect, useRef } from "react";


// ---------------------------------------------------------------------
// 1) PROACTIVE ALERTS
//    Polls GET /chatbot/proactive/ and hands NEW alerts to `onAlerts`.
//    Each alert has a `key`. Shown keys are remembered IN MEMORY per user,
//    so navigating between pages never repeats an alert, but a full page
//    reload shows the current alerts again (the widget's chat is cleared
//    on reload too, so a reminder is never silently lost).
//
//    useProactiveAlerts({
//      api,                       // your axios instance
//      userId: user?.id,
//      enabled: isLoggedIn && user?.role === "student",
//      onAlerts: (alerts) => { ...add bot messages + set badge... },
//    });
// ---------------------------------------------------------------------

const shownAlertKeys = new Map();   // "scope:userId" -> Set of alert keys

// `scope` lets two chat screens (e.g. the floating widget and the full-page
// AI Assistant) each show the alerts, instead of whichever polls first
// "using them up" so the other never sees them.
export function useProactiveAlerts({ api, userId, enabled, onAlerts, scope = "default", intervalMs = 60000 }) {
  // keep the latest callback without restarting the interval
  const cb = useRef(onAlerts);
  useEffect(() => { cb.current = onAlerts; }, [onAlerts]);

  useEffect(() => {
    if (!enabled || !userId) return undefined;

    const mapKey = `${scope}:${userId}`;
    if (!shownAlertKeys.has(mapKey)) shownAlertKeys.set(mapKey, new Set());
    const shown = shownAlertKeys.get(mapKey);
    let stopped = false;

    const check = async () => {
      if (document.hidden) return;            // don't poll from background tabs
      try {
        const res = await api.get("/chatbot/proactive/");
        const fresh = (res.data?.alerts || []).filter((a) => !shown.has(a.key));
        if (stopped || fresh.length === 0) return;

        fresh.forEach((a) => shown.add(a.key));
        cb.current(fresh);
      } catch (e) {
        // never break the chat because of a background poll
      }
    };

    check();
    const id = setInterval(check, intervalMs);
    return () => { stopped = true; clearInterval(id); };
  }, [api, userId, enabled, scope, intervalMs]);
}


// ---------------------------------------------------------------------
// 2) PAGE CONTEXT
//    Tells the backend where the student is, so "apply to this job" works.
//    Call with the current pathname, e.g. getPageContext(location.pathname)
//    and send it as `page_context` in the chat POST body.
// ---------------------------------------------------------------------

export function getPageContext(pathname = "") {
  const jobMatch = pathname.match(/\/student\/jobs\/(\d+)/);
  return {
    page: pathname.split("/").filter(Boolean).slice(0, 2).join("/"),
    ...(jobMatch ? { job_id: Number(jobMatch[1]) } : {}),
  };
}


// ---------------------------------------------------------------------
// 3) TAB REFRESH
//    After every chatbot response, call emitChatbotRefresh(response.data).
//    If the backend sent a `refresh` list (e.g. ["applications","dashboard"]),
//    pages listening for those keys reload their data.
//
//    In a page:   useChatbotRefresh("applications", loadApplications);
// ---------------------------------------------------------------------

export function emitChatbotRefresh(data) {
  if (data && Array.isArray(data.refresh) && data.refresh.length) {
    window.dispatchEvent(new CustomEvent("chatbot:refresh", { detail: data.refresh }));
  }
}

export function useChatbotRefresh(key, reload) {
  const fn = useRef(reload);
  useEffect(() => { fn.current = reload; }, [reload]);

  useEffect(() => {
    const handler = (e) => {
      if (Array.isArray(e.detail) && e.detail.includes(key)) fn.current();
    };
    window.addEventListener("chatbot:refresh", handler);
    return () => window.removeEventListener("chatbot:refresh", handler);
  }, [key]);
}


// ---------------------------------------------------------------------
// 4) FRIENDLY ERRORS
//    The chat endpoint is now rate limited (HTTP 429). Use this in your
//    catch block so students see a clear message instead of a generic
//    "Unable to connect with assistant".
// ---------------------------------------------------------------------

export function chatErrorMessage(err) {
  const status = err?.response?.status;
  if (status === 429) {
    return "You're sending messages a little too fast. Please wait a few seconds and try again.";
  }
  if (status === 401) {
    return "Your session has expired. Please log in again.";
  }
  return "Unable to connect with assistant. Please try again in a moment.";
}
