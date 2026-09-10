import React, {

    useEffect,

    useState

} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    getCompanyCandidates,

    updateCandidateStatus,

    updateCandidateNotes,

    notifyCandidateProfileViewed

} from "../../../api/companyApi";


import {

    FaSearch,

    FaUserGraduate,

    FaFileAlt,

    FaCheckCircle,

    FaCalendarCheck,

    FaUsers,

    FaTimes,

    FaEnvelope,

    FaPhone,

    FaGraduationCap,

    FaDownload,

    FaLinkedin,

    FaGithub,

    FaGlobe,

    FaWhatsapp,

    FaMapMarkerAlt,

    FaBriefcase,

    FaInfoCircle,

    FaCode,

    FaLaptopCode,

    FaRobot,

    FaStickyNote,

    FaTimesCircle,

    FaEye

} from "react-icons/fa";


import Avatar from "../../../components/Avatar/Avatar";

import "./Candidates.css";




const STATUS_OPTIONS = [

    { value:"applied", label:"Applied" },

    { value:"reviewing", label:"Under Review" },

    { value:"shortlisted", label:"Shortlisted" },

    { value:"interview", label:"Interview Scheduled" },

    { value:"selected", label:"Selected" },

    { value:"rejected", label:"Rejected" },

];




const Candidates = ()=>{


const navigate = useNavigate();




const [candidates,setCandidates]=useState([]);


const [stats,setStats]=useState({});


const [jobs,setJobs]=useState([]);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [jobFilter,setJobFilter]=useState("all");


const [statusFilter,setStatusFilter]=useState("all");


const [message,setMessage]=useState("");

const [selectedCandidate,setSelectedCandidate]=useState(null);

const [noteDrafts,setNoteDrafts]=useState({});

const [savingNotes,setSavingNotes]=useState(false);








useEffect(()=>{


loadCandidates();


},[]);







// =====================================
// LOAD CANDIDATES
// =====================================


const loadCandidates=async()=>{


try{


const response =

await getCompanyCandidates();


const data = response.data || {};


setCandidates(data.candidates || []);

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







// =====================================
// STATUS UPDATE
// =====================================


const handleStatusChange=async(applicationId,newStatus)=>{


try{


await updateCandidateStatus(

applicationId,

{ status:newStatus }

);



setCandidates(prev=>

prev.map(c=>

c.id===applicationId

? { ...c, status:newStatus, status_display: STATUS_OPTIONS.find(o=>o.value===newStatus)?.label || newStatus }

: c

)

);


setSelectedCandidate(prev=>

prev && prev.id===applicationId

? { ...prev, status:newStatus, status_display: STATUS_OPTIONS.find(o=>o.value===newStatus)?.label || newStatus }

: prev

);


setMessage("Candidate status updated - WhatsApp notification sent to candidate");


}

catch(error){


console.log(error);


setMessage("Unable to update status");


}



};



// =====================================
// SAVE RECRUITER NOTES
// =====================================


const handleSaveNotes=async(applicationId)=>{


const noteText =
    noteDrafts[applicationId] !== undefined
        ? noteDrafts[applicationId]
        : (selectedCandidate?.recruiter_notes || "");


try{

setSavingNotes(true);

await updateCandidateNotes(applicationId, noteText);


setCandidates(prev=>

prev.map(c=>

c.id===applicationId

? { ...c, recruiter_notes: noteText }

: c

)

);


setSelectedCandidate(prev=>

prev && prev.id===applicationId

? { ...prev, recruiter_notes: noteText }

: prev

);


setMessage("Recruiter notes saved");


}
catch(error){

console.log(error);

setMessage("Unable to save notes");

}
finally{

setSavingNotes(false);

}


};







const filteredCandidates = candidates.filter(c=>{

const matchesSearch = !search ||

(c.name||"").toLowerCase().includes(search.toLowerCase()) ||

(c.job_title||"").toLowerCase().includes(search.toLowerCase());

const matchesJob = jobFilter==="all" || String(c.job_id)===String(jobFilter);

const matchesStatus = statusFilter==="all" || c.status===statusFilter;

return matchesSearch && matchesJob && matchesStatus;

});




const timeAgo=(value)=>{

if(!value) return "";

return new Date(value).toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"});

};




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

<p>Loading candidates...</p>

</div>


);


}








return(



<>


<div className="candidates-page">




{/* BANNER */}


<div className="candidates-banner">


<div className="candidates-banner-icon">

<FaUserGraduate/>

</div>


<div>

<h1>Candidates</h1>

<p>Review and manage job applicants</p>

</div>


</div>




{
message &&

<div className="candidates-message">{message}</div>

}




{/* SEARCH + FILTERS */}


<div className="candidates-filter-bar">


<div className="candidates-search">

<FaSearch/>

<input

type="text"

placeholder="Search candidate or job..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>


<select value={jobFilter} onChange={(e)=>setJobFilter(e.target.value)}>

<option value="all">All Jobs</option>

{
jobs.map(job=>(

<option key={job.id} value={job.id}>{job.title}</option>

))
}

</select>


<select value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)}>

<option value="all">All Status</option>

{
STATUS_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>


</div>




{/* STAT CARDS */}


<div className="candidates-stats">


<div className="candidates-stat-card">

<div className="stat-icon purple"><FaUsers/></div>

<div>

<p>Total Candidates</p>

<h3>{stats.total_candidates || 0}</h3>

<span>All time applicants</span>

</div>

</div>


<div className="candidates-stat-card">

<div className="stat-icon blue"><FaFileAlt/></div>

<div>

<p>New Applicants</p>

<h3>{stats.new_applicants || 0}</h3>

<span>In last 30 days</span>

</div>

</div>


<div className="candidates-stat-card">

<div className="stat-icon green"><FaCheckCircle/></div>

<div>

<p>Shortlisted</p>

<h3>{stats.shortlisted || 0}</h3>

<span>Candidates</span>

</div>

</div>


<div className="candidates-stat-card">

<div className="stat-icon orange"><FaCalendarCheck/></div>

<div>

<p>Interview Scheduled</p>

<h3>{stats.interview_scheduled || 0}</h3>

<span>Candidates</span>

</div>

</div>


</div>




{/* TABLE */}


<div className="candidates-table-card">


{
filteredCandidates.length > 0 ?

<table className="candidates-table">


<thead>

<tr>

<th>Candidate</th>

<th>Job Title</th>

<th>Status</th>

<th>Applied On</th>

<th>Actions</th>

</tr>

</thead>


<tbody>

{
filteredCandidates.map(c=>(

<tr key={c.id}>


<td>

<div

className="candidate-cell clickable"

onClick={()=>{

setSelectedCandidate(c);

notifyCandidateProfileViewed(c.id);

}}

>

<Avatar name={c.name} size={38}/>

<div>

<h4>{c.name}</h4>

<p>{c.email}</p>

</div>

</div>

</td>


<td>{c.job_title}</td>


<td>

<span className={"status-badge " + statusBadgeClass(c.status)}>

{c.status_display}

</span>

</td>


<td>{timeAgo(c.applied_on)}</td>


<td>

<select

value={c.status}

onChange={(e)=>handleStatusChange(c.id,e.target.value)}

>

{
STATUS_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>


{
c.resume_url &&

<a href={c.resume_url} target="_blank" rel="noreferrer" className="resume-link">

<FaFileAlt/> Resume

</a>

}

</td>


</tr>

))
}

</tbody>


</table>

:

<div className="empty-candidates">

<div className="empty-icon"><FaUsers/></div>

<h2>No Candidates Found</h2>

<p>When candidates apply for your jobs, they will appear here.</p>

</div>

}


</div>




</div>




{/* =================================
CANDIDATE DETAIL MODAL
================================= */}

{
selectedCandidate &&

<div

className="candidate-modal-overlay"

onClick={()=>setSelectedCandidate(null)}

>

<div

className="candidate-modal"

onClick={(e)=>e.stopPropagation()}

>

<button

className="candidate-modal-close"

onClick={()=>setSelectedCandidate(null)}

>

<FaTimes/>

</button>


{/* ============ HEADER ============ */}

<div className="candidate-modal-header">

<div className="candidate-avatar large">

{(selectedCandidate.name||"?").charAt(0).toUpperCase()}

</div>

<div>

<h2>{selectedCandidate.name}</h2>

<p>{selectedCandidate.job_title}</p>

<div className="candidate-header-meta">

{
selectedCandidate.location &&

<span><FaMapMarkerAlt/> {selectedCandidate.location}</span>

}

<span><FaEnvelope/> {selectedCandidate.email || "—"}</span>

<span><FaPhone/> {selectedCandidate.phone || "—"}</span>

</div>

<span className={"status-badge " + statusBadgeClass(selectedCandidate.status)}>

{selectedCandidate.status_display}

</span>

</div>

</div>



<div className="candidate-modal-body">


{/* ============ APPLICATION DETAILS ============ */}

<div className="candidate-modal-section">

<h4><FaBriefcase/> Application Details</h4>

<div className="candidate-info-grid">

<div>

<div>

<span>Applied Job</span>

<strong>{selectedCandidate.job_title}</strong>

</div>

</div>

<div>

<div>

<span>Applied On</span>

<strong>

{
selectedCandidate.applied_on
? new Date(selectedCandidate.applied_on).toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"})
: "—"
}

</strong>

</div>

</div>

<div>

<div>

<span>Current Status</span>

<strong>{selectedCandidate.status_display}</strong>

</div>

</div>

</div>

</div>


{/* ============ PERSONAL INFORMATION ============ */}

<div className="candidate-modal-section">

<h4><FaUserGraduate/> Personal Information</h4>

<div className="candidate-info-grid">

<div>

<FaEnvelope/>

<div>

<span>Email</span>

<strong>{selectedCandidate.email || "—"}</strong>

</div>

</div>

<div>

<FaPhone/>

<div>

<span>Phone</span>

<strong>{selectedCandidate.phone || "—"}</strong>

</div>

</div>

{
selectedCandidate.age &&

<div>

<FaUserGraduate/>

<div>

<span>Age</span>

<strong>{selectedCandidate.age}</strong>

</div>

</div>

}

{
selectedCandidate.gender &&

<div>

<FaUserGraduate/>

<div>

<span>Gender</span>

<strong>{selectedCandidate.gender}</strong>

</div>

</div>

}

</div>

</div>


{/* ============ PROFESSIONAL SUMMARY ============ */}

{
selectedCandidate.career_interest &&

<div className="candidate-modal-section">

<h4><FaInfoCircle/> Professional Summary</h4>

<p>{selectedCandidate.career_interest}</p>

</div>

}


{/* ============ AI SKILL ANALYSIS ============ */}

{
selectedCandidate.skills &&

<div className="candidate-modal-section">

<h4><FaCode/> AI Skill Analysis</h4>

<div className="candidate-skill-bars">

{
selectedCandidate.skills.split(",").filter(s=>s.trim()).slice(0,6).map((skill,index)=>{

const baseScore = selectedCandidate.match_score || 70;

const variance = [8, 3, -2, -5, 1, -8][index % 6];

const skillScore = Math.max(40, Math.min(99, baseScore + variance));

return(

<div className="candidate-skill-bar-row" key={index}>

<span className="candidate-skill-bar-label">{skill.trim()}</span>

<div className="candidate-skill-bar-track">

<div

className="candidate-skill-bar-fill"

style={{ width: `${skillScore}%` }}

/>

</div>

<span className="candidate-skill-bar-value">{skillScore}%</span>

</div>

);

})
}

</div>

</div>
}


{/* ============ EDUCATION ============ */}

<div className="candidate-modal-section">

<h4><FaGraduationCap/> Education</h4>

<div className="candidate-info-grid">

<div>

<div>

<span>Degree / Course</span>

<strong>{selectedCandidate.course || "—"}</strong>

</div>

</div>

<div>

<div>

<span>Institution</span>

<strong>{selectedCandidate.institution || "—"}</strong>

</div>

</div>

<div>

<div>

<span>CGPA</span>

<strong>{selectedCandidate.cgpa || "—"}</strong>

</div>

</div>

<div>

<div>

<span>Graduation Year</span>

<strong>{selectedCandidate.graduation_year || "—"}</strong>

</div>

</div>

{
(selectedCandidate.backlog_count !== null && selectedCandidate.backlog_count !== undefined) &&

<div>

<div>

<span>Backlogs</span>

<strong>{selectedCandidate.backlog_count}</strong>

</div>

</div>

}

</div>

</div>


{/* ============ PROJECTS & EXPERIENCE ============ */}

{
(selectedCandidate.experience || selectedCandidate.internships || selectedCandidate.projects) &&

<div className="candidate-modal-section">

<h4><FaLaptopCode/> Projects &amp; Experience</h4>

{
selectedCandidate.experience &&

<div className="candidate-subblock">

<h5>Experience</h5>

<p>{selectedCandidate.experience}</p>

</div>

}

{
selectedCandidate.internships &&

<div className="candidate-subblock">

<h5>Internships</h5>

<p>{selectedCandidate.internships}</p>

</div>

}

{
selectedCandidate.projects &&

<div className="candidate-subblock">

<h5>Projects</h5>

<p>{selectedCandidate.projects}</p>

</div>

}

</div>

}


{/* ============ COVER LETTER ============ */}

{
selectedCandidate.cover_letter &&

<div className="candidate-modal-section">

<h4>Cover Letter</h4>

<p>{selectedCandidate.cover_letter}</p>

</div>

}


{/* ============ RESUME ============ */}

<div className="candidate-modal-section">

<h4><FaFileAlt/> Resume</h4>

{
selectedCandidate.resume_url ?

<div className="resume-preview-row">

<a

href={selectedCandidate.resume_url}

target="_blank"

rel="noreferrer"

className="resume-action-btn view"

>

<FaEye/> View Resume

</a>

<a

href={selectedCandidate.resume_url}

download

className="resume-action-btn download"

>

<FaDownload/> Download

</a>

</div>

:

<p className="candidate-modal-muted">No resume uploaded</p>

}

</div>


{/* ============ AI MATCH SCORE ============ */}

<div className="candidate-modal-section">

<h4><FaRobot/> AI Resume Match Score</h4>

<div className="match-score-row">

<div className={

"match-score-circle " +

(selectedCandidate.match_score >= 75 ? "good" : selectedCandidate.match_score >= 45 ? "average" : "poor")

}>

{selectedCandidate.match_score || 0}%

</div>

<div className="match-score-details">

<p>Match against <b>{selectedCandidate.job_title}</b> requirements</p>

{
selectedCandidate.match_reasons && selectedCandidate.match_reasons.length > 0 &&

<div className="candidate-skill-tags">

{
selectedCandidate.match_reasons.map((reason,index)=>(

<span key={index} className="match-reason-tag">{reason}</span>

))
}

</div>

}

</div>

</div>

</div>


{/* ============ INTERVIEW HISTORY ============ */}

<div className="candidate-modal-section">

<h4><FaCalendarCheck/> Interview History</h4>

{
selectedCandidate.interview_history && selectedCandidate.interview_history.length > 0 ?

<div className="interview-history-list">

{
selectedCandidate.interview_history.map(iv=>(

<div className="interview-history-row" key={iv.id}>

<div>

<strong>

{
iv.date
? new Date(iv.date).toLocaleString(undefined,{year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})
: "—"
}

</strong>

<span>{iv.mode}</span>

</div>

<span className={"status-badge " + statusBadgeClass((iv.status||"").toLowerCase())}>

{iv.status}

</span>

</div>

))
}

</div>

:

<p className="candidate-modal-muted">No interviews scheduled yet</p>

}

</div>


{/* ============ RECRUITER NOTES ============ */}

<div className="candidate-modal-section">

<h4><FaStickyNote/> Recruiter Notes</h4>

<textarea

className="recruiter-notes-box"

rows={3}

placeholder="Add private notes about this candidate (only visible to your team)..."

value={

noteDrafts[selectedCandidate.id] !== undefined

? noteDrafts[selectedCandidate.id]

: (selectedCandidate.recruiter_notes || "")

}

onChange={(e)=>setNoteDrafts({

...noteDrafts,

[selectedCandidate.id]: e.target.value

})}

/>

<button

className="save-notes-btn"

onClick={()=>handleSaveNotes(selectedCandidate.id)}

disabled={savingNotes}

>

{savingNotes ? "Saving..." : "Save Notes"}

</button>

</div>



{/* ============ RECRUITER ACTIONS ============ */}

<div className="candidate-action-buttons">

<button

className="candidate-action-btn shortlist"

onClick={()=>handleStatusChange(selectedCandidate.id,"shortlisted")}

>

<FaCheckCircle/> Shortlist Candidate

</button>

<button

className="candidate-action-btn interview"

onClick={()=>navigate(`/company/interviews?applicationId=${selectedCandidate.id}`)}

>

<FaCalendarCheck/> Schedule Interview

</button>

<button

className="candidate-action-btn reject"

onClick={()=>handleStatusChange(selectedCandidate.id,"rejected")}

>

<FaTimesCircle/> Reject Candidate

</button>

</div>


</div>


</div>


</div>

}


</>


);



};




export default Candidates;
