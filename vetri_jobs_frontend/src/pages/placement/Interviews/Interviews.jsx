import React, {

    useEffect,

    useState

} from "react";


import {

    getCandidatePipeline,

    updatePlacementApplicationStatus

} from "../../../api/placementApi";


import {

    FaUsers,

    FaCheckCircle,

    FaCalendarCheck,

    FaTrophy,

    FaHandshake,

    FaSearch

} from "react-icons/fa";


import "./Interview.css";




const STATUS_OPTIONS = [

    { value:"applied", label:"Applied" },

    { value:"reviewing", label:"Under Review" },

    { value:"shortlisted", label:"Shortlisted" },

    { value:"interview", label:"Interview Scheduled" },

    { value:"selected", label:"Selected" },

    { value:"rejected", label:"Rejected" },

];




const PlacementInterviews = ()=>{


const [data,setData]=useState(null);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [message,setMessage]=useState("");




useEffect(()=>{

loadPipeline();

},[]);




const loadPipeline=async()=>{

try{

const response = await getCandidatePipeline();

setData(response.data);

}
catch(error){

console.log(error);

}
finally{

setLoading(false);

}

};




const handleStatusChange=async(applicationId,newStatus)=>{

try{

await updatePlacementApplicationStatus(applicationId,{status:newStatus});

setData(prev=>({

...prev,

candidates: prev.candidates.map(c=>

c.id===applicationId

? {...c, status:newStatus, status_display: STATUS_OPTIONS.find(o=>o.value===newStatus)?.label || newStatus}

: c

)

}));

setMessage("Candidate status updated");

}
catch(error){

console.log(error);

setMessage("Unable to update status");

}

};




const filteredCandidates = (data?.candidates || []).filter(c=>

!search ||

(c.student_name||"").toLowerCase().includes(search.toLowerCase()) ||

(c.applied_job||"").toLowerCase().includes(search.toLowerCase()) ||

(c.company||"").toLowerCase().includes(search.toLowerCase())

);




const statusBadgeClass=(status)=>{

if(status==="shortlisted") return "badge-blue";

if(status==="interview") return "badge-orange";

if(status==="selected") return "badge-green";

if(status==="rejected") return "badge-red";

return "badge-grey";

};




if(loading){

return(

<div className="company-loading">

<div className="spinner-border"></div>

<p>Loading candidate pipeline...</p>

</div>

);

}




const stats = data?.stats || {};

const pipelineOverview = data?.pipeline_overview || [];

const todayInterviews = data?.today_interviews || [];








return(



<div className="interviews-page">




{/* BANNER */}


<div className="interviews-banner">

<div className="interviews-banner-icon"><FaUsers/></div>

<div>

<h1>Candidate Pipeline</h1>

<p>Shortlist candidates, schedule interviews and update selection status</p>

</div>

</div>




{
message &&

<div className="interviews-message">{message}</div>

}




{/* STAT CARDS */}


<div className="interviews-stats">

<div className="interviews-stat-card">

<div className="stat-icon purple"><FaUsers/></div>

<div><p>Total Applicants</p><h3>{stats.total_applicants || 0}</h3></div>

</div>

<div className="interviews-stat-card">

<div className="stat-icon blue"><FaCheckCircle/></div>

<div><p>Shortlisted</p><h3>{stats.shortlisted || 0}</h3></div>

</div>

<div className="interviews-stat-card">

<div className="stat-icon orange"><FaCalendarCheck/></div>

<div><p>Interviews Scheduled</p><h3>{stats.interviews_scheduled || 0}</h3></div>

</div>

<div className="interviews-stat-card">

<div className="stat-icon green"><FaTrophy/></div>

<div><p>Final Selected</p><h3>{stats.final_selected || 0}</h3></div>

</div>

<div className="interviews-stat-card">

<div className="stat-icon teal"><FaHandshake/></div>

<div><p>Joined</p><h3>{stats.joined || 0}</h3></div>

</div>

</div>




{/* PIPELINE OVERVIEW */}


<div className="pipeline-overview-card">

<h2>Candidate Pipeline Overview</h2>

<div className="pipeline-stage-row">

{
pipelineOverview.map((stage,index)=>(

<React.Fragment key={stage.stage}>

<div className="pipeline-stage">

<div className="pipeline-stage-circle">{stage.count}</div>

<span>{stage.stage}</span>

</div>

{
index < pipelineOverview.length-1 &&

<div className="pipeline-stage-arrow">›</div>

}

</React.Fragment>

))
}

</div>

</div>




<div className="pipeline-body-row">




{/* CANDIDATE TABLE */}


<div className="candidates-table-card pipeline-table-card">


<div className="pipeline-table-header">

<h2>Candidate Shortlist</h2>

<div className="pipeline-search">

<FaSearch/>

<input

type="text"

placeholder="Search by name, job or company..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>

</div>


{
filteredCandidates.length > 0 ?

<table className="candidates-table">

<thead>

<tr>

<th>Student</th>

<th>Department</th>

<th>CGPA</th>

<th>Resume Score</th>

<th>Applied Job</th>

<th>Status</th>

<th>Actions</th>

</tr>

</thead>

<tbody>

{
filteredCandidates.map(c=>(

<tr key={c.id}>

<td>

<div className="candidate-cell">

<div className="candidate-avatar">{(c.student_name||"?").charAt(0).toUpperCase()}</div>

<div><h4>{c.student_name}</h4><p>{c.student_code}</p></div>

</div>

</td>

<td>{c.department || "—"}</td>

<td>{c.cgpa || "—"}</td>

<td>{c.resume_score !== null && c.resume_score !== undefined ? `${c.resume_score}%` : "—"}</td>

<td>{c.applied_job}<br/><small>{c.company}</small></td>

<td>

<span className={"status-badge " + statusBadgeClass(c.status)}>{c.status_display}</span>

</td>

<td>

<select value={c.status} onChange={(e)=>handleStatusChange(c.id,e.target.value)}>

{
STATUS_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>

</td>

</tr>

))
}

</tbody>

</table>

:

<div className="empty-candidates">

<h2>No Candidates Found</h2>

<p>Applications will appear here as students apply to jobs.</p>

</div>

}


</div>




{/* TODAY'S INTERVIEWS */}


<div className="today-interviews-card">

<h2>Today's Interviews</h2>

{
todayInterviews.length > 0 ?

<div className="today-interview-list">

{
todayInterviews.map(iv=>(

<div className="today-interview-row" key={iv.id}>

<strong>{iv.time}</strong>

<div>

<h4>{iv.candidate_name}</h4>

<p>{iv.job_title}</p>

</div>

<span className="mode-pill">{iv.mode}</span>

</div>

))
}

</div>

:

<p className="candidate-modal-muted">No interviews scheduled for today</p>

}

</div>




</div>




</div>


);



};




export default PlacementInterviews;
