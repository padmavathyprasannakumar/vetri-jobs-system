import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementStudents,

    sendPlacementNotification

} from "../../../api/placementApi";


import {

    FaBell,

    FaEnvelope,

    FaWhatsapp,

    FaMobileAlt,

    FaPaperPlane,

    FaSearch

} from "react-icons/fa";


import "./SendNotifications.css";




const SendNotifications = ()=>{


const [students,setStudents] = useState([]);

const [loadingStudents,setLoadingStudents] = useState(true);

const [search,setSearch] = useState("");


const [audience,setAudience] = useState("all_students");

const [selectedIds,setSelectedIds] = useState([]);


const [channels,setChannels] = useState({

app: true,

email: false,

whatsapp: false,

});


const [title,setTitle] = useState("");

const [message,setMessage] = useState("");


const [sending,setSending] = useState(false);

const [result,setResult] = useState(null);

const [error,setError] = useState("");




useEffect(()=>{

getPlacementStudents()

.then(res=>{

const list = res.data?.results || res.data || [];

setStudents(list);

})

.catch(err=>console.log("STUDENTS LOAD ERROR", err))

.finally(()=>setLoadingStudents(false));

},[]);




const toggleChannel = (key)=>{

setChannels(prev=>({ ...prev, [key]: !prev[key] }));

};




const toggleStudent = (id)=>{

setSelectedIds(prev=>

prev.includes(id)

? prev.filter(x=>x!==id)

: [...prev, id]

);

};




const filteredStudents = students.filter(s=>

(s.full_name||"").toLowerCase().includes(search.toLowerCase())

);




const handleSend = async(e)=>{

e.preventDefault();

setError("");

setResult(null);


if(!title.trim() || !message.trim()){

setError("Please enter both a title and a message.");

return;

}


const selectedChannels = Object.keys(channels).filter(key=>channels[key]);


if(selectedChannels.length === 0){

setError("Please select at least one delivery channel.");

return;

}


if(audience==="specific" && selectedIds.length===0){

setError("Please select at least one student.");

return;

}


setSending(true);


try{


const res = await sendPlacementNotification({

title,

message,

channels: selectedChannels,

audience,

student_ids: audience==="specific" ? selectedIds : [],

});


setResult(res.data);

setTitle("");

setMessage("");

setSelectedIds([]);


}

catch(err){

console.log("SEND NOTIFICATION ERROR", err);

setError(

err.response?.data?.error ||

"Could not send notification. Please try again."

);

}

finally{

setSending(false);

}


};




return(


<div className="send-notifications-page">


<div className="sn-header">

<div className="sn-header-icon"><FaBell/></div>

<div>

<h1>Send Notifications</h1>

<p>Reach students through app, email, and WhatsApp</p>

</div>

</div>


<div className="sn-layout">


<form className="sn-form" onSubmit={handleSend}>


<label>Audience</label>

<div className="sn-audience-toggle">

<button

type="button"

className={audience==="all_students" ? "active" : ""}

onClick={()=>setAudience("all_students")}

>

All Students

</button>

<button

type="button"

className={audience==="specific" ? "active" : ""}

onClick={()=>setAudience("specific")}

>

Select Students

</button>

</div>


{
audience==="specific" &&

<div className="sn-student-picker">

<div className="sn-picker-search">

<FaSearch/>

<input

placeholder="Search students..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>

<div className="sn-picker-list">

{
loadingStudents ? (

<p className="sn-picker-empty">Loading students...</p>

) : filteredStudents.length > 0 ? (

filteredStudents.map(student=>(

<label key={student.id} className="sn-picker-item">

<input

type="checkbox"

checked={selectedIds.includes(student.id)}

onChange={()=>toggleStudent(student.id)}

/>

<span>{student.full_name}</span>

<span className="sn-picker-email">{student.email}</span>

</label>

))

) : (

<p className="sn-picker-empty">No students found</p>

)
}

</div>

<p className="sn-picker-count">{selectedIds.length} student(s) selected</p>

</div>
}


<label>Delivery Channels</label>

<div className="sn-channels">

<label className={"sn-channel-card " + (channels.app ? "active" : "")}>

<input type="checkbox" checked={channels.app} onChange={()=>toggleChannel("app")}/>

<FaMobileAlt/>

<span>App Notification</span>

</label>

<label className={"sn-channel-card " + (channels.email ? "active" : "")}>

<input type="checkbox" checked={channels.email} onChange={()=>toggleChannel("email")}/>

<FaEnvelope/>

<span>Email</span>

</label>

<label className={"sn-channel-card " + (channels.whatsapp ? "active" : "")}>

<input type="checkbox" checked={channels.whatsapp} onChange={()=>toggleChannel("whatsapp")}/>

<FaWhatsapp/>

<span>WhatsApp</span>

</label>

</div>


<label>Title</label>

<input

value={title}

onChange={(e)=>setTitle(e.target.value)}

placeholder="e.g. New Placement Drive Announced"

/>


<label>Message</label>

<textarea

rows="5"

value={message}

onChange={(e)=>setMessage(e.target.value)}

placeholder="Write your notification message..."

/>


{
error &&

<div className="sn-error">{error}</div>
}


{
result &&

<div className="sn-result">

Sent to {result.total_students} student(s) —{" "}

{result.app_notified} app, {result.email_sent} email,{" "}

{result.whatsapp_sent} WhatsApp.

</div>
}


<button type="submit" className="sn-send-btn" disabled={sending}>

<FaPaperPlane/>

{sending ? "Sending..." : "Send Notification"}

</button>


</form>


<div className="sn-tips">

<h3>Tips</h3>

<ul>

<li>App notifications appear instantly in the student's notification bell.</li>

<li>Email requires the student to have a valid email on file.</li>

<li>WhatsApp requires the student's WhatsApp number and an active WhatsApp Business configuration.</li>

<li>You can combine multiple channels for important announcements like placement drives.</li>

</ul>

</div>


</div>


</div>


);


};




export default SendNotifications;
