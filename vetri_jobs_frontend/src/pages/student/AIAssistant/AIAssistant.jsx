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




const AIAssistant = ()=>{


const bodyRef = useRef(null);


const fileInputRef = useRef(null);


const [branding,setBranding] = useState({ chatbot_avatar_image_url:null });


const [messages,setMessages] = useState([

    {

        sender:"bot",

        text:"Hi! 👋 I can help you with:\n\n• Find suitable jobs\n• Improve your resume\n• Prepare for interviews\n• Suggest skills to learn\n• Career guidance\n\nWhat would you like to do today?"

    }

]);


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

onClick={()=>setMessages([{

sender:"bot",

text:"Hi! 👋 I can help you with:\n\n• Find suitable jobs\n• Improve your resume\n• Prepare for interviews\n• Suggest skills to learn\n• Career guidance\n\nWhat would you like to do today?"

}])}

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
messages.length <= 1 &&

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
