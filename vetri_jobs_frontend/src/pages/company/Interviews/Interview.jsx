import React,{

    useEffect,

    useState

} from "react";


import {

    getCompanyInterviews,

    createCompanyInterview,

    updateInterviewStatus,

    getCompanyCandidates

} from "../../../api/companyApi";


import {

    FaCalendarCheck,

    FaClock,

    FaCheckCircle,

    FaTimesCircle,

    FaSearch,

    FaPlus,

    FaTimes,

    FaVideo,

    FaMapMarkerAlt

} from "react-icons/fa";


import "./Interview.css";




const MODE_OPTIONS = [

    { value:"online", label:"Video Call" },

    { value:"physical", label:"In Person" },

    { value:"phone", label:"Phone" },

];


const STATUS_OPTIONS = [

    { value:"scheduled", label:"Scheduled" },

    { value:"completed", label:"Completed" },

    { value:"cancelled", label:"Cancelled" },

    { value:"rescheduled", label:"Rescheduled" },

];




const Interview=()=>{



const [interviews,setInterviews]=useState([]);


const [stats,setStats]=useState({});


const [jobs,setJobs]=useState([]);


const [candidates,setCandidates]=useState([]);


const [loading,setLoading]=useState(true);


const [showForm,setShowForm]=useState(false);


const [message,setMessage]=useState("");


const [search,setSearch]=useState("");


const [jobFilter,setJobFilter]=useState("all");


const [statusFilter,setStatusFilter]=useState("all");



const initialForm={

    application:"",

    date:"",

    time:"",

    interview_mode:"online",

    location:"",

    meeting_link:""

};


const [form,setForm]=useState(initialForm);







useEffect(()=>{


loadInterviews();

loadCandidates();


},[]);







// =====================================
// LOAD INTERVIEWS
// =====================================


const loadInterviews=async()=>{


try{


const response=

await getCompanyInterviews();


const data = response.data || {};


setInterviews(data.interviews || []);

setStats(data.stats || {});

setJobs(data.jobs || []);



}

catch(error){


console.log(error);


}

finally{


setLoading(false);


}



};




const loadCandidates=async()=>{

try{

const response = await getCompanyCandidates();

setCandidates(response.data?.candidates || []);

}
catch(error){

console.log(error);

}

};







// =====================================
// FORM INPUT
// =====================================


const handleChange=(e)=>{


setForm({

...form,

[e.target.name]: e.target.value

});


};







// =====================================
// CREATE INTERVIEW
// =====================================


const handleSubmit=async(e)=>{


e.preventDefault();


if(!form.application || !form.date || !form.time){

setMessage("Please select a candidate, date and time");

return;

}


try{


const interview_date = `${form.date}T${form.time}:00`;


await createCompanyInterview({

application: form.application,

interview_date,

interview_mode: form.interview_mode,

location: form.location,

meeting_link: form.meeting_link,

});



setMessage("Interview scheduled successfully");


setForm(initialForm);


setShowForm(false);


loadInterviews();



}

catch(error){


console.log(error);


const data = error.response?.data;

let friendlyMessage = "Unable to schedule interview";

if(data){

if(typeof data === "string"){

friendlyMessage = data;

}
else if(data.error){

friendlyMessage = data.error;

}
else if(typeof data === "object"){

const fieldErrors = Object.entries(data)

.map(([field,messages])=>

Array.isArray(messages) ? messages.join(", ") : messages

);

if(fieldErrors.length > 0){

friendlyMessage = fieldErrors.join(" | ");

}

}

}

setMessage(friendlyMessage);


}



};







// =====================================
// STATUS UPDATE
// =====================================


const handleStatusChange=async(interviewId,newStatus)=>{

try{

await updateInterviewStatus(interviewId,{status:newStatus});

setInterviews(prev=>

prev.map(iv=>

iv.id===interviewId
? {...iv, status:newStatus, status_display: STATUS_OPTIONS.find(o=>o.value===newStatus)?.label || newStatus}
: iv

)

);

setMessage("Interview status updated");

}
catch(error){

console.log(error);

setMessage("Unable to update interview status");

}

};







const filteredInterviews = interviews.filter(iv=>{

const matchesSearch = !search ||

(iv.candidate_name||"").toLowerCase().includes(search.toLowerCase()) ||

(iv.job_title||"").toLowerCase().includes(search.toLowerCase());

const matchesStatus = statusFilter==="all" || iv.status===statusFilter;

return matchesSearch && matchesStatus;

});




const formatDateTime=(value)=>{

if(!value) return { date:"—", time:"" };

const d = new Date(value);

return {

date: d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"}),

time: d.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"}),

};

};




const statusBadgeClass=(status)=>{

if(status==="scheduled") return "badge-green";

if(status==="completed") return "badge-blue";

if(status==="cancelled") return "badge-red";

if(status==="rescheduled") return "badge-orange";

return "badge-grey";

};








if(loading){


return(


<div className="company-loading">

<div className="spinner-border"></div>

<p>Loading interviews...</p>

</div>


);


}








return(



<div className="interviews-page">




{/* BANNER */}


<div className="interviews-banner">


<div className="interviews-banner-icon">

<FaCalendarCheck/>

</div>


<div>

<h1>Interviews</h1>

<p>Schedule and manage candidate interviews</p>

</div>


<button className="schedule-btn" onClick={()=>setShowForm(true)}>

<FaPlus/> Schedule Interview

</button>


</div>




{
message &&

<div className="interviews-message">{message}</div>

}




{/* STAT CARDS */}


<div className="interviews-stats">


<div className="interviews-stat-card">

<div className="stat-icon green"><FaCalendarCheck/></div>

<div>

<p>Total Interviews</p>

<h3>{stats.total || 0}</h3>

</div>

</div>


<div className="interviews-stat-card">

<div className="stat-icon blue"><FaClock/></div>

<div>

<p>Upcoming Interviews</p>

<h3>{stats.upcoming || 0}</h3>

</div>

</div>


<div className="interviews-stat-card">

<div className="stat-icon purple"><FaCheckCircle/></div>

<div>

<p>Completed Interviews</p>

<h3>{stats.completed || 0}</h3>

</div>

</div>


<div className="interviews-stat-card">

<div className="stat-icon orange"><FaTimesCircle/></div>

<div>

<p>Cancelled Interviews</p>

<h3>{stats.cancelled || 0}</h3>

</div>

</div>


</div>




{/* FILTER BAR */}


<div className="interviews-filter-bar">


<div className="interviews-search">

<FaSearch/>

<input

type="text"

placeholder="Search by candidate name or job title..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>


<select value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)}>

<option value="all">All Status</option>

{
STATUS_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>


</div>




{/* TABLE */}


<div className="interviews-table-card">


{
filteredInterviews.length > 0 ?

<table className="interviews-table">


<thead>

<tr>

<th>Candidate</th>

<th>Job Title</th>

<th>Interview Date &amp; Time</th>

<th>Status</th>

<th>Mode</th>

<th>Actions</th>

</tr>

</thead>


<tbody>

{
filteredInterviews.map(iv=>{

const dt = formatDateTime(iv.interview_date);

return(

<tr key={iv.id}>


<td>

<div className="candidate-cell">

<div className="candidate-avatar">

{(iv.candidate_name||"?").charAt(0).toUpperCase()}

</div>

<div>

<h4>{iv.candidate_name}</h4>

<p>{iv.candidate_email}</p>

</div>

</div>

</td>


<td>{iv.job_title}</td>


<td>

<div className="interview-datetime">

<span>{dt.date}</span>

<small>{dt.time}</small>

</div>

</td>


<td>

<span className={"status-badge " + statusBadgeClass(iv.status)}>

{iv.status_display}

</span>

</td>


<td>

{iv.interview_mode==="Online" ? <FaVideo/> : <FaMapMarkerAlt/>} {iv.interview_mode}

</td>


<td>

<select

value={iv.status}

onChange={(e)=>handleStatusChange(iv.id,e.target.value)}

>

{
STATUS_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>

</td>


</tr>

);

})
}

</tbody>


</table>

:

<div className="empty-interviews">

<div className="empty-icon"><FaCalendarCheck/></div>

<h2>No Interviews Found</h2>

<p>Scheduled interviews will appear here.</p>

</div>

}


</div>




{/* SCHEDULE INTERVIEW MODAL */}


{
showForm &&

<div className="interview-modal-overlay" onClick={()=>setShowForm(false)}>


<div className="interview-modal" onClick={(e)=>e.stopPropagation()}>


<button className="interview-modal-close" onClick={()=>setShowForm(false)}>

<FaTimes/>

</button>


<h2>Schedule Interview</h2>


<form onSubmit={handleSubmit}>


<label>Candidate</label>

<select name="application" value={form.application} onChange={handleChange} required>

<option value="">Select candidate</option>

{
candidates.map(c=>(

<option key={c.id} value={c.id}>{c.name} — {c.job_title}</option>

))
}

</select>


<div className="interview-form-row">

<div>

<label>Date</label>

<input type="date" name="date" value={form.date} onChange={handleChange} required/>

</div>

<div>

<label>Time</label>

<input type="time" name="time" value={form.time} onChange={handleChange} required/>

</div>

</div>


<label>Mode</label>

<select name="interview_mode" value={form.interview_mode} onChange={handleChange}>

{
MODE_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>


{
form.interview_mode==="online" ?

<>

<label>Meeting Link</label>

<input

type="text"

name="meeting_link"

value={form.meeting_link}

onChange={handleChange}

placeholder="https://meet.google.com/..."

/>

</>

:

<>

<label>Location</label>

<input

type="text"

name="location"

value={form.location}

onChange={handleChange}

placeholder="Office address"

/>

</>

}


<button type="submit" className="interview-submit-btn">

Schedule Interview

</button>


</form>


</div>


</div>

}




</div>


);



};




export default Interview;
