import React, {

    useState,

    useRef,

    useEffect

} from "react";


import {

    sendChatMessage

} from "../../../api/chatbotApi";


import {

    getSiteBranding

} from "../../../api/brandingApi";


import {

    FaRobot,

    FaPaperclip,

    FaPaperPlane,

    FaPlus,

    FaUsers,

    FaFileAlt,

    FaChartLine,

    FaSearch

} from "react-icons/fa";


import "./CompanyAIAssistant.css";




const QUICK_ACTIONS = [

    { icon:<FaSearch/>, label:"Find candidates for a job", text:"Find candidates for a job" },

    { icon:<FaFileAlt/>, label:"Write a job description", text:"Help me write a job description" },

    { icon:<FaUsers/>, label:"Analyse a resume", text:"Analyse a candidate's resume" },

    { icon:<FaChartLine/>, label:"Show hiring insights", text:"Show me hiring insights" },

];


const CHECKLIST = [

    "Find the best candidates",

    "Analyze resumes",

    "Create job descriptions",

    "Schedule interviews",

    "Send WhatsApp notifications",

    "Get hiring insights",

];




const CompanyAIAssistant = ()=>{


const bodyRef = useRef(null);


const fileInputRef = useRef(null);


const [branding,setBranding] = useState({ chatbot_avatar_image_url:null });


const recruiterName = (()=>{

try{

const stored = JSON.parse(localStorage.getItem("user") || "null");

return stored?.full_name || stored?.username || "there";

}
catch(e){

return "there";

}

})();


const initialGreeting = {

sender:"bot",

text:`Hi ${recruiterName}! 👋 I'm Vetri AI, your recruitment assistant. I can help you with:\n\n${CHECKLIST.map(c=>"✓ "+c).join("\n")}\n\nWhat would you like to do today?`

};


const [messages,setMessages] = useState([initialGreeting]);


const [message,setMessage] = useState("");


const [attachedFile,setAttachedFile] = useState(null);


const [loading,setLoading] = useState(false);




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




const handleFileSelected = (e)=>{

const file = e.target.files[0];

if(!file) return;

setAttachedFile(file);

e.target.value = "";

};




const handleSend = async(overrideText)=>{

const textToSend = overrideText ?? message;

if(!textToSend.trim() && !attachedFile) return;

setMessages(prev=>[

...prev,

{ sender:"user", text:textToSend, attachment: attachedFile?.name || null }

]);

const pendingFile = attachedFile;

setMessage("");

setAttachedFile(null);

setLoading(true);

try{

const response = await sendChatMessage(textToSend, pendingFile);

setMessages(prev=>[

...prev,

{ sender:"bot", text: response.data.reply || "Sorry, I couldn't understand that." }

]);

}
catch(error){

setMessages(prev=>[

...prev,

{ sender:"bot", text:"Unable to connect with assistant." }

]);

}
finally{

setLoading(false);

}

};




return(


<div className="company-ai-page">


<div className="company-ai-page-header">

<div className="company-ai-page-avatar">

{
branding.chatbot_avatar_image_url ?
<img src={branding.chatbot_avatar_image_url} alt="AI"/>
:
<FaRobot/>
}

</div>

<div>

<h1>Vetri AI Assistant</h1>

<p>Your intelligent hiring companion</p>

</div>

<button

className="company-ai-new-chat-btn"

onClick={()=>setMessages([initialGreeting])}

>

<FaPlus/> New Chat

</button>

</div>


<div className="company-ai-chat-card">


<div className="company-ai-body" ref={bodyRef}>

{
messages.map((item,index)=>(

<div key={index} className={"company-ai-message " + item.sender}>

{
item.attachment &&

<div className="company-ai-attachment"><FaPaperclip/> {item.attachment}</div>
}

{item.text}

</div>

))
}


{
loading &&

<div className="company-ai-message bot typing">

<span></span><span></span><span></span>

</div>
}

</div>


{
messages.length <= 1 &&

<div className="company-ai-quick-actions">

{
QUICK_ACTIONS.map((action,index)=>(

<button key={index} onClick={()=>handleSend(action.text)}>

<span>{action.icon}</span> {action.label}

</button>

))
}

</div>
}


{
attachedFile &&

<div className="company-ai-attachment-preview">

<FaPaperclip/> {attachedFile.name}

<button onClick={()=>setAttachedFile(null)}>✕</button>

</div>
}


<div className="company-ai-input">

<input

type="file"

ref={fileInputRef}

style={{display:"none"}}

accept=".pdf,.doc,.docx"

onChange={handleFileSelected}

/>

<button

type="button"

className="company-ai-attach-btn"

onClick={()=>fileInputRef.current?.click()}

title="Attach a file"

>

<FaPaperclip/>

</button>

<input

value={message}

onChange={(e)=>setMessage(e.target.value)}

onKeyDown={(e)=>{ if(e.key==="Enter") handleSend(); }}

placeholder="Type your message..."

/>

<button

className="company-ai-send-btn"

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




export default CompanyAIAssistant;
