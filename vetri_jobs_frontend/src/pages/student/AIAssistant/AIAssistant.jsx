import React, {

    useState,

    useRef,

    useEffect

} from "react";


import {

    useNavigate,

    useLocation

} from "react-router-dom";


import {

    sendChatMessage

} from "../../../api/chatbotApi";


import {

    downloadResume

} from "../../../api/studentApi";


import {

    getSiteBranding

} from "../../../api/brandingApi";


import api from "../../../api/axios";


import {

    useProactiveAlerts,

    getPageContext,

    emitChatbotRefresh,

    chatErrorMessage

} from "../../../api/chatbotHelpers";


import {

    useAuth

} from "../../../context/AuthContext";


import {

    FaRobot,

    FaPaperclip,

    FaPaperPlane,

    FaSearch,

    FaFileAlt,

    FaChalkboardTeacher,

    FaLightbulb,

    FaPlus

} from "react-icons/fa";


import "./AIAssistant.css";




const QUICK_ACTIONS = [

    { icon:<FaSearch/>, label:"Find jobs for me", text:"Find jobs for me" },

    { icon:<FaFileAlt/>, label:"Improve my resume", text:"Help me improve my resume" },

    { icon:<FaChalkboardTeacher/>, label:"Prepare for interview", text:"How can I prepare for my interview?" },

    { icon:<FaLightbulb/>, label:"Suggest skills to learn", text:"What skills should I improve?" },

];




const GREETING = {

    sender:"bot",

    text:"Hi! 👋 I can help you with:\n\n• Find suitable jobs\n• Improve your resume\n• Prepare for interviews\n• Suggest skills to learn\n• Career guidance\n\nWhat would you like to do today?"

};




// The conversation is kept in sessionStorage so it survives the
// automatic page changes (e.g. "show my interviews" opens the
// Interviews tab, which unmounts this page). Without this the whole
// chat - including the answer - vanished the moment it navigated.

const getStorageKey = (user)=>

    `ai_assistant_chat_${user?.id ?? user?.email ?? "guest"}`;


const loadSavedMessages = (key)=>{

    try{

        const raw = sessionStorage.getItem(key);

        if(raw){

            const saved = JSON.parse(raw);

            if(Array.isArray(saved) && saved.length) return saved;

        }

    }

    catch(e){

        // fall through to the greeting

    }

    return [GREETING];

};




const AIAssistant = ()=>{


const navigate = useNavigate();


const location = useLocation();


const { user } = useAuth();


const storageKey = getStorageKey(user);


const bodyRef = useRef(null);


const fileInputRef = useRef(null);


const [branding,setBranding] = useState({ chatbot_avatar_image_url:null });


const [messages,setMessages] = useState(()=>loadSavedMessages(storageKey));


// Always holds the latest message list, so a message can be saved to
// sessionStorage immediately - before an automatic navigation
// unmounts this page and would otherwise drop it.

const messagesRef = useRef(messages);


const commitMessages = (next)=>{

    messagesRef.current = next;

    setMessages(next);

    try{

        sessionStorage.setItem(storageKey, JSON.stringify(next.slice(-60)));

    }
    catch(e){

        // storage full/unavailable - the chat still works, just isn't saved

    }

};


const pushMessages = (newMessages)=>

    commitMessages([...messagesRef.current, ...newMessages]);


const [message,setMessage] = useState("");


const [attachedFile,setAttachedFile] = useState(null);


const [loading,setLoading] = useState(false);


const [downloadingIndex,setDownloadingIndex] = useState(null);




useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);


useEffect(()=>{

if(bodyRef.current){

bodyRef.current.scrollTop = bodyRef.current.scrollHeight;

}

},[messages,loading]);




// ===============================
// PROACTIVE ALERTS
// The assistant speaks first (interview reminders, unread
// notifications, new jobs, missing resume, incomplete profile).
// ===============================

useProactiveAlerts({

    api,

    userId: user?.id ?? user?.email ?? user?.username,

    enabled: !!user && user?.role === "student",

    scope: "page",

    onAlerts: (alerts)=>{

        pushMessages(

            alerts.map(a=>({

                sender:"bot",

                text: a.text,

                quickReplies: a.actions && a.actions.length ? a.actions : null

            }))

        );

    }

});




const handleFileSelected = (e)=>{

const file = e.target.files[0];

if(!file) return;

setAttachedFile(file);

e.target.value = "";

};




// ===============================
// IN-CHAT RESUME DOWNLOAD
// ===============================

const handleDownloadResume = async(resumeId, filename, index)=>{

setDownloadingIndex(index);

try{

const response = await downloadResume(resumeId);

const blobUrl = window.URL.createObjectURL(new Blob([response.data]));

const link = document.createElement("a");

link.href = blobUrl;

link.download = filename || "resume";

document.body.appendChild(link);

link.click();

link.remove();

window.URL.revokeObjectURL(blobUrl);

}
catch(error){

pushMessages([{

sender:"bot",

text:"Sorry, I couldn't download that file just now. Try again from the Resume page."

}]);

}
finally{

setDownloadingIndex(null);

}

};




const handleSend = async(overrideText)=>{

const isOverride = typeof overrideText === "string";

const textToSend = isOverride ? overrideText : message;

if(!textToSend.trim() && !attachedFile) return;

if(loading) return;

pushMessages([

{ sender:"user", text:textToSend, attachment: attachedFile?.name || null }

]);

const pendingFile = attachedFile;

if(!isOverride) setMessage("");

setAttachedFile(null);

setLoading(true);

try{

const response = await sendChatMessage(

textToSend,

pendingFile,

getPageContext(location.pathname)

);

const data = response.data || {};

// Saved to sessionStorage right here, BEFORE any automatic
// navigation below unmounts this page.

pushMessages([

{

sender:"bot",

text: data.reply || "Sorry, I couldn't understand that.",

matchedJobs: data.matched_jobs || null,

// Yes / No style buttons (e.g. "Apply to X at Y?")

quickReplies: data.quick_replies && data.quick_replies.length ? data.quick_replies : null,

interviews: data.interviews || null,

applications: data.applications || null,

notifications: data.notifications || null,

drives: data.drives || null,

resumeDownload: data.resume_download || null,

mockInterviewReport: data.mock_interview_report || null

}

]);

// Tell any other mounted screens to reload their data
// (e.g. after applying to a job or adding a skill).

emitChatbotRefresh(data);

// Auto-navigate to the matching tab when the bot's action says
// to. The conversation is saved above, so it is still here when
// the student comes back to this page.

if(data.navigate_to){

navigate(data.navigate_to);

}

}
catch(error){

pushMessages([

{ sender:"bot", text: chatErrorMessage(error) }

]);

}
finally{

setLoading(false);

}

};




// Clicking a quick-reply chip sends its text and removes that row
// of chips so it can't be reused.

const handleQuickReply = (index, text)=>{

commitMessages(

messagesRef.current.map((m,i)=>

i===index ? { ...m, quickReplies:null } : m

)

);

handleSend(text);

};




const handleNewChat = ()=>{

commitMessages([GREETING]);

};




// Quick-action grid only while the student hasn't said anything yet
// (alerts from the assistant no longer hide it).

const hasUserMessage = messages.some(m=>m.sender==="user");




return(


<div className="ai-assistant-page">


<div className="ai-assistant-page-header">

<div className="ai-assistant-page-avatar">

{
branding.chatbot_avatar_image_url ?
<img src={branding.chatbot_avatar_image_url} alt="AI"/>
:
<FaRobot/>
}

</div>

<div>

<h1>AI Career Assistant</h1>

<p>Your personal career companion</p>

</div>

<button

className="ai-new-chat-btn"

onClick={handleNewChat}

>

<FaPlus/> New Chat

</button>

</div>


<div className="ai-assistant-chat-card">


<div className="ai-assistant-body" ref={bodyRef}>

{
messages.map((item,index)=>(

<div key={index} className={"ai-chat-message " + item.sender}>

{
item.attachment &&

<div className="ai-chat-attachment"><FaPaperclip/> {item.attachment}</div>
}

{item.text}


{/* QUICK-REPLY CHIPS (from proactive alerts) */}

{
item.quickReplies && item.quickReplies.length > 0 &&

<div className="ai-quick-replies">

{
item.quickReplies.map(q=>(

<button

key={q}

type="button"

className="ai-quick-reply"

disabled={loading}

onClick={()=>handleQuickReply(index,q)}

>

{q}

</button>

))
}

</div>
}


{/* AGENT-STYLE JOB MATCH CARDS */}

{
item.matchedJobs && item.matchedJobs.length > 0 &&

<div className="ai-chat-job-cards">

{
item.matchedJobs.map(job=>(

<div className="ai-chat-job-card" key={job.id}>


<div className="ai-chat-job-card-top">

<strong>{job.title}</strong>

{
job.match_score !== null && job.match_score !== undefined &&

<span className="ai-chat-job-card-score">

{job.match_score}% match

</span>
}

</div>


<p className="ai-chat-job-card-sub">

{job.company}
{job.location ? ` \u2022 ${job.location}` : ""}

</p>


<div className="ai-chat-job-card-actions">

{
job.already_applied ?

<span className="ai-chat-job-card-score">✓ Already Applied</span>

:

<button

className="ai-chat-job-card-apply"

onClick={()=>navigate(job.apply_url)}

>

Apply

</button>
}


<button

className="ai-chat-job-card-view"

onClick={()=>navigate(job.details_url)}

>

View details

</button>

</div>


</div>

))
}

</div>
}


{/* UPCOMING INTERVIEWS */}

{
item.interviews && item.interviews.length > 0 &&

<div className="ai-chat-job-cards">

{
item.interviews.map((iv,idx)=>(

<div className="ai-chat-job-card" key={idx}>

<div className="ai-chat-job-card-top">

<strong>{iv.job_title}</strong>

</div>

<p className="ai-chat-job-card-sub">

{iv.company}
{iv.date ? ` \u2022 ${iv.date}` : ""}
{iv.time ? ` at ${iv.time}` : ""}
{iv.mode ? ` \u2022 ${iv.mode}` : ""}

</p>

</div>

))
}

</div>
}


{/* APPLICATIONS */}

{
item.applications && item.applications.length > 0 &&

<div className="ai-chat-job-cards">

{
item.applications.map((a,idx)=>(

<div className="ai-chat-job-card" key={idx}>

<div className="ai-chat-job-card-top">

<strong>{a.job_title}</strong>

{
a.status &&

<span className="ai-chat-job-card-score">{a.status}</span>
}

</div>

<p className="ai-chat-job-card-sub">

{a.company}
{a.interview ? ` \u2022 Interview ${a.interview.date} at ${a.interview.time}` : ""}

</p>

</div>

))
}

</div>
}


{/* PLACEMENT DRIVES */}

{
item.drives && item.drives.length > 0 &&

<div className="ai-chat-job-cards">

{
item.drives.map((d,idx)=>(

<div className="ai-chat-job-card" key={idx}>

<div className="ai-chat-job-card-top">

<strong>{d.title}</strong>

</div>

<p className="ai-chat-job-card-sub">

{d.company}
{d.date ? ` \u2022 ${d.date}` : ""}

</p>

</div>

))
}

</div>
}


{/* NOTIFICATIONS */}

{
item.notifications && item.notifications.length > 0 &&

<div className="ai-chat-job-cards">

{
item.notifications.map((n,idx)=>(

<div className="ai-chat-job-card" key={idx}>

<div className="ai-chat-job-card-top">

<strong>{n.title || "Notification"}</strong>

{
!n.is_read &&

<span className="ai-chat-job-card-score">New</span>
}

</div>

<p className="ai-chat-job-card-sub">{n.message}</p>

</div>

))
}

</div>
}


{/* IN-CHAT RESUME DOWNLOAD */}

{
item.resumeDownload &&

<div className="ai-chat-job-cards">

<div className="ai-chat-job-card">

<div className="ai-chat-job-card-top">

<strong>{item.resumeDownload.filename}</strong>

</div>

<div className="ai-chat-job-card-actions">

<button

type="button"

className="ai-chat-job-card-apply"

disabled={downloadingIndex===index}

onClick={()=>handleDownloadResume(

item.resumeDownload.resume_id,

item.resumeDownload.filename,

index

)}

>

{downloadingIndex===index ? "Downloading..." : "Download"}

</button>

</div>

</div>

</div>
}


{/* MOCK INTERVIEW SCORE REPORT */}

{
item.mockInterviewReport &&

<div className="ai-chat-job-cards">

<div className="ai-chat-job-card">

{
item.mockInterviewReport.overall_score !== null &&
item.mockInterviewReport.overall_score !== undefined &&

<div className="ai-chat-job-card-top">

<strong>Overall {item.mockInterviewReport.overall_score}/100</strong>

<span className="ai-chat-job-card-score">

Communication {item.mockInterviewReport.communication_score ?? "-"}
{" \u2022 "}
Technical {item.mockInterviewReport.technical_score ?? "-"}

</span>

</div>
}

{
item.mockInterviewReport.strengths?.length > 0 &&

<p className="ai-chat-job-card-sub">

<strong>Strengths:</strong> {item.mockInterviewReport.strengths.join("; ")}

</p>
}

{
item.mockInterviewReport.areas_to_improve?.length > 0 &&

<p className="ai-chat-job-card-sub">

<strong>To improve:</strong> {item.mockInterviewReport.areas_to_improve.join("; ")}

</p>
}

</div>

</div>
}


</div>

))
}


{
loading &&

<div className="ai-chat-message bot typing">

<span></span><span></span><span></span>

</div>
}

</div>


{
!hasUserMessage &&

<div className="ai-quick-actions-grid">

{
QUICK_ACTIONS.map((action,index)=>(

<button key={index} className="ai-quick-action-card" onClick={()=>handleSend(action.text)}>

<span className="ai-quick-action-icon">{action.icon}</span>

{action.label}

</button>

))
}

</div>
}


{
attachedFile &&

<div className="ai-assistant-attachment-preview">

<FaPaperclip/> {attachedFile.name}

<button onClick={()=>setAttachedFile(null)}>✕</button>

</div>
}


<div className="ai-assistant-input">

<input

type="file"

ref={fileInputRef}

style={{display:"none"}}

accept=".pdf,.doc,.docx"

onChange={handleFileSelected}

/>

<button

type="button"

className="ai-assistant-attach-btn"

onClick={()=>fileInputRef.current?.click()}

title="Attach resume"

>

<FaPaperclip/>

</button>

<input

value={message}

onChange={(e)=>setMessage(e.target.value)}

onKeyDown={(e)=>{ if(e.key==="Enter") handleSend(); }}

placeholder="Ask something..."

/>

<button

className="ai-assistant-send-btn"

onClick={()=>handleSend()}

disabled={loading || (!message.trim() && !attachedFile)}

>

<FaPaperPlane/>

</button>

</div>


</div>


</div>


);



};




export default AIAssistant;
