import React,{

useEffect,

useState

} from "react";



import {

getStudentInterviews

} from "../../../api/studentApi";



import {

useNavigate

} from "react-router-dom";



import {

FaBuilding,

FaCalendarAlt,

FaClock,

FaVideo,

FaCheckCircle,

FaTimesCircle,

FaMapMarkerAlt,

FaCalendarCheck,

FaQuestionCircle,

FaRobot,

FaFileAlt

} from "react-icons/fa";



import EmptyState from "../../../components/EmptyState/EmptyState";

import "./Interviews.css";




const TABS = [

    { key:"scheduled", label:"Upcoming" },

    { key:"completed", label:"Completed" },

    { key:"cancelled", label:"Cancelled" },

];




const Interviews=()=>{



const navigate = useNavigate();


const [interviews,setInterviews]=useState([]);


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");


const [activeTab,setActiveTab]=useState("scheduled");








// ===============================
// LOAD INTERVIEWS
// ===============================


useEffect(()=>{


loadInterviews();


},[]);




const loadInterviews=async()=>{


try{


const response=

await getStudentInterviews();


setInterviews(

response.data || []

);



}

catch(error){


console.log(

"INTERVIEW ERROR",

error

);


setError("Unable to load interviews");


}

finally{


setLoading(false);


}



};




const countFor=(status)=>{

if(status==="scheduled"){

return interviews.filter(iv=>

iv.status==="scheduled" || iv.status==="rescheduled"

).length;

}

return interviews.filter(iv=>iv.status===status).length;

};



const filteredInterviews = interviews.filter(iv=>{

if(activeTab==="scheduled"){

return iv.status==="scheduled" || iv.status==="rescheduled";

}

return iv.status===activeTab;

});




const formatDateTime=(value)=>{

if(!value) return { date:"—", time:"" };

const d = new Date(value);

return {

date: d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"}),

time: d.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"}),

};

};




const statusIcon=(status)=>{

if(status==="completed") return <FaCheckCircle/>;

if(status==="cancelled") return <FaTimesCircle/>;

return <FaClock/>;

};




const modeIcon=(mode)=>{

if((mode||"").toLowerCase().includes("online")) return <FaVideo/>;

return <FaMapMarkerAlt/>;

};








if(loading){


return(


<div className="jobs-loading">

<div className="loader"></div>

<p>Loading interviews...</p>

</div>


);


}








return(



<div className="student-interviews-page">




{/* HEADER */}


<div className="interviews-header">


<div>

<h1>My Interviews</h1>

<p>View and manage your interview schedules</p>

</div>


</div>




{/* TABS */}


<div className="interview-tabs">


{
TABS.map(tab=>(

<button

key={tab.key}

className={activeTab===tab.key ? "interview-tab active" : "interview-tab"}

onClick={()=>setActiveTab(tab.key)}

>

{tab.label} ({countFor(tab.key)})

</button>

))
}


</div>




{
error &&

<div className="interviews-error">{error}</div>

}




{/* TIP BANNER */}


<div className="interview-tip-banner">


<div className="interview-tip-icon">

<FaCalendarAlt/>

</div>


<div>

<h3>Stay prepared for your interviews</h3>

<p>Check your upcoming interviews, prepare well and ace your dream job!</p>

</div>


</div>




{/* LIST / EMPTY STATE */}


{
filteredInterviews.length > 0 ?

<div className="interview-list">


{
filteredInterviews.map(iv=>{

const dt = formatDateTime(iv.interview_date);

const job = iv.application?.job;

const company = job?.company;


return(

<div className="interview-card" key={iv.id}>


<div className="interview-card-icon">

<FaBuilding/>

</div>


<div className="interview-card-body">


<h3>{job?.title || "Interview"}</h3>

<p>{company || "Company"}</p>


<div className="interview-card-meta">

<span><FaCalendarAlt/> {dt.date}</span>

<span><FaClock/> {dt.time}</span>

<span>{modeIcon(iv.interview_mode)} {iv.interview_mode || "Online"}</span>

</div>


</div>


<div className="interview-card-side">


<div className={"interview-status-pill " + iv.status}>

{statusIcon(iv.status)} {iv.status}

</div>


<div className="interview-card-actions">

{
iv.meeting_link ?

<a

href={iv.meeting_link}

target="_blank"

rel="noreferrer"

className="interview-join-btn"

>

Join Meeting

</a>

:

<button className="interview-join-btn" disabled>

Join Meeting

</button>
}


<button

className="interview-view-btn"

onClick={()=>job?.id && navigate(`/student/jobs/${job.id}`)}

>

View Details

</button>


</div>


</div>


</div>

);

})
}


</div>

:

<EmptyState

icon="calendar"

title={
activeTab==="scheduled"
? "No Upcoming Interviews"
: activeTab==="completed"
? "No Completed Interviews"
: "No Cancelled Interviews"
}

message={
activeTab==="scheduled"
? "You don't have any upcoming interviews scheduled."
: activeTab==="completed"
? "Completed interviews will show up here."
: "Cancelled interviews will show up here."
}

action={
activeTab==="scheduled"
? { label:"Browse Jobs", onClick:()=>navigate("/student/jobs") }
: null
}

/>

}






{/* =================================
INTERVIEW PREPARATION
================================= */}


<div className="interview-prep-card">

<h2>Interview Preparation</h2>

<div className="interview-prep-row">

<div className="interview-prep-icon"><FaQuestionCircle/></div>

<div className="interview-prep-text">

<h4>Practice common technical questions</h4>

<p>Get AI-generated questions based on the job role</p>

</div>

<button

className="interview-prep-btn"

onClick={()=>navigate("/student/ai-assistant")}

>

Start Practice

</button>

</div>


<div className="interview-prep-row">

<div className="interview-prep-icon"><FaRobot/></div>

<div className="interview-prep-text">

<h4>Mock Interview with AI</h4>

<p>Simulate a real interview experience</p>

</div>

<button

className="interview-prep-btn"

onClick={()=>navigate("/student/ai-assistant")}

>

Start Mock

</button>

</div>


<div className="interview-prep-row">

<div className="interview-prep-icon"><FaFileAlt/></div>

<div className="interview-prep-text">

<h4>Review Your Resume</h4>

<p>Get AI feedback to improve your answers</p>

</div>

<button

className="interview-prep-btn"

onClick={()=>navigate("/student/resume")}

>

Review Now

</button>

</div>


</div>



</div>


);



};




export default Interviews;
