import React, {

    useState,

    useRef,

    useEffect

} from "react";


import {

    sendChatMessage,

    getChatHistory

} from "../../../api/chatbotApi";


import {

    FaRobot,

    FaPaperclip,

    FaPaperPlane,

    FaPlus,

    FaSearch,

    FaCalendarAlt,

    FaBuilding,

    FaFileAlt,

    FaPen,

    FaGraduationCap

} from "react-icons/fa";


import "./PlacementChatbot.css";




const CAPABILITIES = [

    { icon:<FaSearch/>, label:"Find Jobs", desc:"Search relevant opportunities" },

    { icon:<FaCalendarAlt/>, label:"Drive Information", desc:"Get details about placement drives" },

    { icon:<FaBuilding/>, label:"Company Insights", desc:"Learn about hiring companies" },

    { icon:<FaFileAlt/>, label:"Application Help", desc:"Guidance on applications" },

    { icon:<FaPen/>, label:"Resume Tips", desc:"Improve your resume with AI" },

    { icon:<FaGraduationCap/>, label:"Career Advice", desc:"Get personalized guidance" },

];


const SUGGESTED_QUESTIONS = [

    "What are the upcoming placement drives?",

    "Show me jobs for Computer Science students",

    "How to apply for a placement drive?",

    "What are the eligibility criteria for internships?",

    "Give me tips to crack technical interviews",

];




const PlacementChatbot = ()=>{


const bodyRef = useRef(null);

const fileInputRef = useRef(null);


const [messages,setMessages] = useState([{

sender:"bot",

text:"Hi! I'm Vetri AI 👋\n\nI can help you with job opportunities, placement drives, student information, company details and more. How can I assist you today?"

}]);


const [message,setMessage] = useState("");

const [attachedFile,setAttachedFile] = useState(null);

const [loading,setLoading] = useState(false);

const [history,setHistory] = useState([]);




useEffect(()=>{

getChatHistory()

.then(res=>setHistory(res.data || []))

.catch(()=>{});

},[]);


useEffect(()=>{

if(bodyRef.current){

bodyRef.current.scrollTop = bodyRef.current.scrollHeight;

}

},[messages,loading]);




const handleFileSelected = (e)=>{

const file = e.target.files[0];

if(!file) return;

setAttachedFile(file);

e.target.value = "";

};




const handleSend = async(overrideText)=>{

const textToSend = overrideText ?? message;

if(!textToSend.trim() && !attachedFile) return;

setMessages(prev=>[...prev, { sender:"user", text:textToSend }]);

const pendingFile = attachedFile;

setMessage("");

setAttachedFile(null);

setLoading(true);

try{

const response = await sendChatMessage(textToSend, pendingFile);

setMessages(prev=>[...prev, { sender:"bot", text: response.data.reply || "Sorry, I couldn't understand that." }]);

}
catch(error){

setMessages(prev=>[...prev, { sender:"bot", text:"Unable to connect with assistant." }]);

}
finally{

setLoading(false);

}

};




return(


<div className="placement-chatbot-page">


<div className="pc-banner">

<div className="pc-banner-text">

<div className="pc-banner-title">

<h1>AI Placement Assistant</h1>

<span className="pc-beta-badge">Beta</span>

</div>

<p>Your intelligent assistant for students, companies and placement activities.</p>

<p>Ask anything. Get instant, accurate answers.</p>

</div>

<div className="pc-banner-icon"><FaRobot/></div>

<div className="pc-banner-quote">

"Smarter Questions<br/>Brighter Careers"

</div>

</div>


<div className="pc-layout">


<div className="pc-chat-card">

<div className="pc-chat-header">

<div className="pc-chat-avatar"><FaRobot/></div>

<div>

<h4>Vetri AI</h4>

<span className="pc-online-dot"></span> Online

</div>

<button className="pc-new-chat-btn" onClick={()=>setMessages([messages[0]])}>

<FaPlus/> New Chat

</button>

</div>


<div className="pc-chat-body" ref={bodyRef}>

{
messages.map((item,index)=>(

<div key={index} className={"pc-message " + item.sender}>

{item.text}

</div>

))
}

{
loading &&

<div className="pc-message bot typing">

<span></span><span></span><span></span>

</div>
}

</div>


{
messages.length <= 1 &&

<div className="pc-quick-buttons">

<button onClick={()=>handleSend("Show all upcoming placement drives")}>Show all drives</button>

<button onClick={()=>handleSend("What jobs are available at Google?")}>Jobs at Google</button>

<button onClick={()=>handleSend("How do I apply for a placement drive?")}>How to apply?</button>

<button onClick={()=>handleSend("What are the eligibility criteria?")}>Eligibility criteria?</button>

</div>
}


{
attachedFile &&

<div className="pc-attachment-preview">

<FaPaperclip/> {attachedFile.name}

<button onClick={()=>setAttachedFile(null)}>✕</button>

</div>
}


<div className="pc-input-row">

<input type="file" ref={fileInputRef} style={{display:"none"}} onChange={handleFileSelected}/>

<button className="pc-attach-btn" onClick={()=>fileInputRef.current?.click()}><FaPaperclip/></button>

<input

value={message}

onChange={(e)=>setMessage(e.target.value)}

onKeyDown={(e)=>{ if(e.key==="Enter") handleSend(); }}

placeholder="Type your message here..."

/>

<button className="pc-send-btn" onClick={()=>handleSend()} disabled={loading || (!message.trim() && !attachedFile)}>

<FaPaperPlane/>

</button>

</div>

</div>


<div className="pc-sidebar">


<div className="pc-panel">

<h4>AI Capabilities</h4>

<div className="pc-capabilities-grid">

{
CAPABILITIES.map((cap,index)=>(

<div className="pc-capability-card" key={index}>

<span className="pc-capability-icon">{cap.icon}</span>

<strong>{cap.label}</strong>

<p>{cap.desc}</p>

</div>

))
}

</div>

</div>


<div className="pc-panel">

<h4>Suggested Questions</h4>

<ul className="pc-suggested-list">

{
SUGGESTED_QUESTIONS.map((q,index)=>(

<li key={index} onClick={()=>handleSend(q)}>

<span>›</span> {q}

</li>

))
}

</ul>

</div>


<div className="pc-panel">

<div className="pc-panel-header">

<h4>Recent Conversations</h4>

</div>

<ul className="pc-recent-list">

{
history.slice(0,4).map((h,index)=>(

<li key={index}>

<span>{h.message || h.title || "Conversation"}</span>

<small>{h.created_at ? new Date(h.created_at).toLocaleDateString() : ""}</small>

</li>

))
}

{
history.length===0 &&

<li className="pc-recent-empty">No conversations yet</li>
}

</ul>

</div>


<div className="pc-panel">

<h4>Chat Statistics</h4>

<div className="pc-stat-row">

<span>Total Queries</span>

<b>{history.length}</b>

</div>

</div>


</div>


</div>


</div>


);



};




export default PlacementChatbot;
