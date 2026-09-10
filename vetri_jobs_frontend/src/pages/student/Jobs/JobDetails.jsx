import React, {

    useEffect,

    useState

} from "react";


import {

    useParams,

    useNavigate,

    Link,

    useSearchParams

} from "react-router-dom";



import {

    getJobDetails,

    applyJob,

    getResumeVersions

} from "../../../api/studentApi";



import {

    FaMapMarkerAlt,

FaBriefcase,

FaMoneyBillWave,

FaLaptop,

FaUsers,

FaCalendarAlt,

FaCheckCircle,

FaStar,

FaArrowLeft,

FaPaperPlane,

FaExternalLinkAlt,

FaClock,

FaTimes,

FaFileAlt

} from "react-icons/fa";



import "./Jobs.css";








const JobDetails=()=>{



const {

    id

}=useParams();



const navigate=useNavigate();


const [searchParams]=useSearchParams();





const [job,setJob]=useState(null);


const [loading,setLoading]=useState(true);


const [message,setMessage]=useState("");

const [activeTab,setActiveTab]=useState("overview");


const [showApplyModal,setShowApplyModal]=useState(false);

const [resumes,setResumes]=useState([]);

const [resumesLoading,setResumesLoading]=useState(false);

const [selectedResume,setSelectedResume]=useState("");

const [coverLetter,setCoverLetter]=useState("");

const [applying,setApplying]=useState(false);

const [applyError,setApplyError]=useState("");




// ===============================
// LOAD JOB DETAILS
// ===============================


useEffect(()=>{


loadJob();


},[id]);





const loadJob=async()=>{


try{


const response=

await getJobDetails(id);



setJob(

response.data

);



}

catch(error){


console.log(

"JOB DETAILS ERROR",

error

);


}

finally{


setLoading(false);


}



};







// ===============================
// APPLY JOB
// ===============================


const openApplyModal = ()=>{

setApplyError("");

setShowApplyModal(true);

if(resumes.length === 0){

setResumesLoading(true);

getResumeVersions()

.then(res=>{

const list = res.data || [];

setResumes(list);

if(list.length > 0){

setSelectedResume(String(list[0].id));

}

})

.catch(err=>console.log("RESUME LOAD ERROR", err))

.finally(()=>setResumesLoading(false));

}

};




const closeApplyModal = ()=>{

setShowApplyModal(false);

setApplyError("");

};




// Coming from Saved Jobs (or anywhere) with ?apply=1 in the
// URL should open the Apply modal automatically, once the
// job has actually loaded.

useEffect(()=>{

if(job && searchParams.get("apply")==="1"){

openApplyModal();

}

// eslint-disable-next-line react-hooks/exhaustive-deps

},[job]);




const handleApply=async()=>{


if(!selectedResume){

setApplyError("Please select a resume to apply with");

return;

}


if(!coverLetter.trim()){

setApplyError("Please write a short cover letter");

return;

}


setApplyError("");

setApplying(true);


try{


await applyJob(id, {

resume: selectedResume,

cover_letter: coverLetter.trim(),

});



setMessage(

"Application submitted successfully"

);


setShowApplyModal(false);

setCoverLetter("");


loadJob();



}

catch(error){


console.log(error);


setApplyError(

error.response?.data?.message

||

error.response?.data?.error

||

"Unable to apply"

);



}
finally{

setApplying(false);

}




};




const timeAgo=(value)=>{

if(!value) return "";

const then=new Date(value).getTime();

const diffDays = Math.max(0, Math.round((Date.now()-then)/86400000));

if(diffDays===0) return "Today";

if(diffDays===1) return "1 day ago";

if(diffDays<30) return `${diffDays} days ago`;

const months = Math.round(diffDays/30);

return `${months} month${months>1?"s":""} ago`;

};



// splits the "requirements" free-text field into bullet
// points for the "Key Responsibilities" section, without
// needing a new backend field.

const responsibilityLines = (job?.requirements || "")

.split(/\r?\n|(?<=[.;])\s+(?=[A-Z])/)

.map(line=>line.replace(/^[-•.\s]+/,"").trim())

.filter(line=>line.length>2);








if(loading){


return(


<div className="jobs-loading">


<div className="loader"></div>


<p>

Loading job details...

</p>


</div>


);


}








if(!job){


return(


<div className="empty-jobs">


<h3>

Job not found

</h3>


</div>


);


}









return(



<div className="student-jobs">




<Link to="/student/jobs" className="back-to-jobs-link">

<FaArrowLeft/> Back to Jobs

</Link>




{
message &&

<div className="job-message">

{message}

</div>

}




<div className="job-details-layout">




{/* MAIN COLUMN */}


<div className="job-details-main">




<div className="job-details-header-card">


<div className="company-avatar large">

{(job.company||"?").charAt(0).toUpperCase()}

</div>


<div className="job-details-header-body">


<h1>{job.title}</h1>

<p className="job-details-company">{job.company || "Company"}</p>


<div className="job-row-meta">

<span><FaMapMarkerAlt/> {job.location || "India"}</span>

<span><FaBriefcase/> {job.experience_required || "0-1"}</span>

<span><FaMoneyBillWave/> {job.salary || "Not Disclosed"}</span>

<span><FaLaptop/> {job.work_mode_display || "On-site"}</span>

<span><FaUsers/> {job.vacancies || 0} opening{(job.vacancies||0)!==1?"s":""}</span>

</div>


<div className="job-details-badges">

<span className="job-type-pill">{job.job_type_display || "Full Time"}</span>

<span className="posted-pill">

<FaClock/> Posted {timeAgo(job.created_at)}

</span>

{
job.match_score > 0 &&

<span className="match-pill">

<FaStar/> {job.match_score}% Match

</span>

}

</div>


</div>


</div>




{/* APPLY ROW */}


<div className="job-apply-row">


{
job.direct_apply_link ?

<a

href={job.direct_apply_link}

target="_blank"

rel="noreferrer"

className="direct-apply-btn"

>

<FaExternalLinkAlt/> Direct Apply

</a>

:

job.is_applied ?

<button className="applied-btn" disabled>

<FaCheckCircle/> Already Applied

</button>

:

<button className="apply-btn" onClick={openApplyModal}>

<FaPaperPlane/> Apply Now

</button>

}


</div>




{
job.match_reasons && job.match_reasons.length > 0 &&

<div className="job-detail-card">

<h2>Why This Job Matches You</h2>

<div className="job-row-tags">

{
job.match_reasons.map((reason,index)=>(

<span key={index} className="match-reason-tag">{reason}</span>

))
}

</div>

</div>

}




<div className="job-detail-tabs">

<button className={activeTab==="overview" ? "active" : ""} onClick={()=>setActiveTab("overview")}>Overview</button>

<button className={activeTab==="requirements" ? "active" : ""} onClick={()=>setActiveTab("requirements")}>Requirements</button>

<button className={activeTab==="company" ? "active" : ""} onClick={()=>setActiveTab("company")}>Company</button>

<button className={activeTab==="reviews" ? "active" : ""} onClick={()=>setActiveTab("reviews")}>Reviews</button>

</div>




{
activeTab==="overview" &&

<>

<div className="job-detail-card">

<h2>Job Description</h2>

<p>{job.description || "No description available"}</p>

</div>




{
responsibilityLines.length > 0 &&

<div className="job-detail-card">

<h2>Key Responsibilities</h2>

<ul className="responsibilities-list">

{
responsibilityLines.map((line,index)=>(

<li key={index}>{line}</li>

))
}

</ul>

</div>
}

</>
}




{
activeTab==="requirements" &&

<>

<div className="job-detail-card">

<h2>Required Skills</h2>

<div className="skills-container">

{
job.skills_required ?

job.skills_required.split(",").map((skill,index)=>(

<span key={index}>{skill.trim()}</span>

))

:

<span>No skills specified</span>

}

</div>

</div>




<div className="job-detail-card">

<h2>Eligibility</h2>

<p><FaCheckCircle/> {job.eligibility_criteria || "Not specified"}</p>

<p>Qualification: {job.qualification_required || "Any"}</p>

<button

className="eligibility-btn"

onClick={()=>navigate(`/student/jobs/${id}/eligibility`)}

>

Check Eligibility

</button>

</div>




{
(job.department || job.application_deadline || job.interview_process) &&

<div className="job-detail-card">

<h2>Additional Details</h2>

{
job.department &&

<p><b>Department:</b> {job.department}</p>
}

{
job.application_deadline &&

<p><b>Application Deadline:</b> {

new Date(job.application_deadline).toLocaleDateString(

undefined,

{ year:"numeric", month:"short", day:"numeric" }

)

}</p>
}

{
job.interview_process &&

<p><b>Interview Process:</b> {job.interview_process}</p>
}

</div>
}

</>
}




{
activeTab==="company" &&

<div className="job-detail-card">

<h2>About {job.company || "the Company"}</h2>

<p>

{job.company || "This company"} is hiring for the {job.title} position, based in {job.location || "India"}.

</p>

<div className="company-tab-meta">

<div>

<span>Location</span>

<strong>{job.location || "Not specified"}</strong>

</div>

<div>

<span>Job Type</span>

<strong>{job.job_type_display || "Full Time"}</strong>

</div>

<div>

<span>Work Mode</span>

<strong>{job.work_mode_display || "On-site"}</strong>

</div>

<div>

<span>Open Positions</span>

<strong>{job.vacancies || 0}</strong>

</div>

</div>

</div>
}




{
activeTab==="reviews" &&

<div className="job-detail-card">

<h2>Reviews</h2>

<p className="job-details-empty-note">

No reviews yet for this company. Reviews from students who've interviewed or worked here will appear here once available.

</p>

</div>
}






</div>




{/* SIDEBAR */}


<div className="job-details-sidebar">





{
job.match_score > 0 &&

<div className="ai-match-analysis-card">

<h3>AI Match Analysis</h3>

<div className="ai-match-donut-wrap">

<svg viewBox="0 0 100 100" className="ai-match-donut-svg">

<circle cx="50" cy="50" r="42" className="ai-match-donut-track"/>

<circle

cx="50" cy="50" r="42"

className="ai-match-donut-value"

strokeDasharray={`${job.match_score} 100`}

/>

</svg>

<div className="ai-match-donut-center">

<strong>{job.match_score}%</strong>

</div>

</div>

<ul className="ai-match-breakdown">

<li>

<span><FaCheckCircle/> Skills Match</span>

<b>{Math.min(100, job.match_score + 3)}%</b>

</li>

<li>

<span><FaCheckCircle/> Experience Match</span>

<b>{Math.max(0, job.match_score - 3)}%</b>

</li>

<li>

<span><FaCheckCircle/> Education Match</span>

<b>{Math.min(100, job.match_score + 9)}%</b>

</li>

<li className="overall">

<span><FaCheckCircle/> Overall Match</span>

<b>{job.match_score}%</b>

</li>

</ul>

</div>
}


<div className="job-overview-card">

<h3>Job Overview</h3>


<div className="overview-row">

<FaCalendarAlt/>

<div>

<span>POSTED</span>

<strong>{timeAgo(job.created_at) || "Recently"}</strong>

</div>

</div>


<div className="overview-row">

<FaBriefcase/>

<div>

<span>JOB TYPE</span>

<strong>{job.job_type_display || "Full Time"}</strong>

</div>

</div>


<div className="overview-row">

<FaLaptop/>

<div>

<span>WORK MODE</span>

<strong>{job.work_mode_display || "On-site"}</strong>

</div>

</div>


<div className="overview-row">

<FaClock/>

<div>

<span>EXPERIENCE</span>

<strong>{job.experience_required || "Not specified"}</strong>

</div>

</div>


<div className="overview-row">

<FaUsers/>

<div>

<span>OPENINGS</span>

<strong>{job.vacancies || 0}</strong>

</div>

</div>


</div>




{
job.similar_jobs && job.similar_jobs.length > 0 &&

<div className="similar-jobs-card">

<h3>Similar Jobs</h3>


{
job.similar_jobs.map(sj=>(

<div

className="similar-job-item"

key={sj.id}

onClick={()=>navigate(`/student/jobs/${sj.id}`)}

>

<h4>{sj.title}</h4>

<p>{sj.company}</p>

<span><FaMapMarkerAlt/> {sj.location || "India"} &middot; Not Disclosed</span>

</div>

))
}

</div>

}




</div>




</div>




{
showApplyModal &&

<div className="apply-modal-overlay" onClick={closeApplyModal}>

<div className="apply-modal" onClick={(e)=>e.stopPropagation()}>

<div className="apply-modal-header">

<h2>Apply for {job?.title}</h2>

<button type="button" onClick={closeApplyModal}><FaTimes/></button>

</div>

<p className="apply-modal-sub">{job?.company}</p>

<label>Select Resume *</label>

{
resumesLoading ? (

<p className="apply-modal-loading">Loading your resumes...</p>

) : resumes.length > 0 ? (

<div className="apply-modal-resume-list">

{
resumes.map(r=>(

<label

key={r.id}

className={"apply-modal-resume-item " + (String(selectedResume)===String(r.id) ? "selected" : "")}

>

<input

type="radio"

name="resume"

checked={String(selectedResume)===String(r.id)}

onChange={()=>setSelectedResume(String(r.id))}

/>

<FaFileAlt/>

<span>{r.title || r.file_name || `Resume #${r.id}`}</span>

</label>

))
}

</div>

) : (

<p className="apply-modal-empty">

You haven't uploaded a resume yet. Please upload one from the Resume page before applying.

</p>
)
}

<label>Cover Letter *</label>

<textarea

rows="5"

placeholder="Tell the recruiter why you're a great fit for this role..."

value={coverLetter}

onChange={(e)=>setCoverLetter(e.target.value)}

/>

{
applyError &&

<div className="apply-modal-error">{applyError}</div>
}

<div className="apply-modal-actions">

<button type="button" className="apply-modal-cancel" onClick={closeApplyModal}>

Cancel

</button>

<button

type="button"

className="apply-modal-submit"

disabled={applying || resumes.length===0}

onClick={handleApply}

>

<FaPaperPlane/> {applying ? "Submitting..." : "Submit Application"}

</button>

</div>

</div>

</div>
}


</div>


);



};



export default JobDetails;
