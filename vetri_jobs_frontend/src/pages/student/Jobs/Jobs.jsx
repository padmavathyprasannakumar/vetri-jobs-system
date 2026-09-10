import React,{
    useEffect,
    useState
} from "react";


import {

    getJobs,

    applyJob,

    saveJob,

    removeSavedJob,

    checkEligibility

} from "../../../api/studentApi";



import {

    useNavigate

} from "react-router-dom";



import {

FaSearch,
FaMapMarkerAlt,
FaBriefcase,
FaMoneyBillWave,
FaBuilding,
FaStar,
FaArrowRight,
FaLaptop,
FaUsers,
FaClock,
FaBookmark,
FaRegBookmark,
FaTimes,
FaPaperPlane,
FaRedo,
FaCheck,
FaExclamationTriangle

} from "react-icons/fa";



import EmptyState from "../../../components/EmptyState/EmptyState";

import "./Jobs.css";




// Job Type / Work Mode options match the backend's actual
// choices (Job.JOB_TYPE_CHOICES / Job.WORK_MODE_CHOICES) so
// every filter here can actually match a real job.

const JOB_TYPE_OPTIONS = [
    { value:"full_time", label:"Full Time" },
    { value:"part_time", label:"Part Time" },
    { value:"internship", label:"Internship" },
    { value:"contract", label:"Contract" },
];


const WORK_MODE_OPTIONS = [
    { value:"onsite", label:"On-site" },
    { value:"remote", label:"Remote" },
    { value:"hybrid", label:"Hybrid" },
];




const Jobs=()=>{



const navigate=useNavigate();




const [jobs,setJobs]=useState([]);


const [filteredJobs,setFilteredJobs]=useState([]);


const [search,setSearch]=useState("");


const [experienceFilter,setExperienceFilter]=useState("");


const [jobTypeFilter,setJobTypeFilter]=useState("");


const [workModeFilter,setWorkModeFilter]=useState("");


const [sortBy,setSortBy]=useState("best_match");


const [loading,setLoading]=useState(true);


const [message,setMessage]=useState("");

const [loadError,setLoadError]=useState("");



// =================================
// APPLY NOW MODAL
// =================================

const [applyModalJob,setApplyModalJob]=useState(null);

const [coverLetter,setCoverLetter]=useState("");

const [submittingApplication,setSubmittingApplication]=useState(false);

const [eligibility,setEligibility]=useState(null);

const [eligibilityLoading,setEligibilityLoading]=useState(false);






// ===============================
// LOAD JOBS
// ===============================


useEffect(()=>{


loadJobs();


},[]);






const loadJobs=async()=>{


try{


setLoadError("");


const response=

await getJobs();



const data=response.data;



setJobs(data);

setFilteredJobs(data);



}

catch(error){


console.log(

"JOB LOAD ERROR",

error

);


setLoadError(

error.response?.data?.error ||

error.response?.data?.detail ||

"Unable to load jobs. Please try again."

);


}


finally{


setLoading(false);


}



};










// ===============================
// FILTER + SORT
// ===============================


const applyFilters=()=>{


let result=[...jobs];



if(search){

const q = search.toLowerCase();

result=result.filter(job=>

job.title?.toLowerCase().includes(q)

||

(job.company||"").toLowerCase().includes(q)

||

(job.skills_required||"").toLowerCase().includes(q)

||

(job.location||"").toLowerCase().includes(q)

);

}



if(jobTypeFilter){

result=result.filter(job=> job.job_type===jobTypeFilter);

}



if(workModeFilter){

result=result.filter(job=> job.work_mode===workModeFilter);

}



if(experienceFilter.trim()){

const exp = experienceFilter.trim().toLowerCase();

result=result.filter(job=>

(job.experience_required||"").toLowerCase().includes(exp)

);

}



if(sortBy==="best_match"){

result.sort((a,b)=> (b.match_score||0)-(a.match_score||0));

}

else if(sortBy==="newest"){

result.sort((a,b)=> new Date(b.created_at)-new Date(a.created_at));

}



setFilteredJobs(result);


};




useEffect(()=>{

applyFilters();

// eslint-disable-next-line react-hooks/exhaustive-deps

},[search,jobTypeFilter,workModeFilter,sortBy,jobs]);




const clearFilters=()=>{

setSearch("");

setExperienceFilter("");

setJobTypeFilter("");

setWorkModeFilter("");

setSortBy("best_match");

setFilteredJobs(jobs);

};








// ===============================
// APPLY NOW MODAL
// ===============================


const openApplyModal=(job)=>{

setApplyModalJob(job);

setCoverLetter("");

setEligibility(null);

loadEligibility(job.id);

};




const loadEligibility=async(jobId)=>{

try{

setEligibilityLoading(true);

const response = await checkEligibility(jobId);

setEligibility(response.data);

}
catch(error){

console.log("ELIGIBILITY CHECK ERROR", error);

setEligibility(null);

}
finally{

setEligibilityLoading(false);

}

};



const closeApplyModal=()=>{

if(submittingApplication) return;

setApplyModalJob(null);

setCoverLetter("");

};



const confirmApply=async()=>{


if(!applyModalJob) return;


try{


setSubmittingApplication(true);


await applyJob(

applyModalJob.id,

{
cover_letter: coverLetter
}

);



setMessage(

"Application submitted successfully"

);



const markApplied = (list)=> list.map(j=>

j.id===applyModalJob.id
? {...j, is_applied:true}
: j

);


setJobs(markApplied);

setFilteredJobs(markApplied);


setApplyModalJob(null);

setCoverLetter("");


}


catch(error){


console.log(error);


setMessage(

error.response?.data?.message

||

"Unable to apply"

);


}


finally{


setSubmittingApplication(false);


}



};




// ===============================
// SAVE / UNSAVE JOB
// ===============================


const handleSaveToggle=async(job)=>{


const updateLocal = (isSaved)=>{

const apply = (list)=> list.map(j=>

j.id===job.id
? {...j, is_saved:isSaved}
: j

);

setJobs(apply);

setFilteredJobs(apply);

};



try{


if(job.is_saved){


await removeSavedJob(job.id);


updateLocal(false);


setMessage("Job removed from saved list");


}

else{


await saveJob(job.id);


updateLocal(true);


setMessage("Job saved");


}


}


catch(error){


console.log(error);


setMessage(

error.response?.data?.error ||

"Unable to update saved job"

);


}



};




const timeAgo=(value)=>{

if(!value) return "";

const then=new Date(value).getTime();

const diffDays = Math.max(0, Math.round((Date.now()-then)/86400000));

if(diffDays===0) return "Today";

if(diffDays===1) return "1 day ago";

return `${diffDays} days ago`;

};








if(loading){


return(


<div className="jobs-loading">


<div className="loader"></div>


<p>

Loading jobs...

</p>


</div>


);


}








return(


<>


<div className="student-jobs">




{/* TOP SEARCH BAR */}


<div className="jobs-search-bar">


<div className="jobs-search-input">

<FaSearch/>

<input

type="text"

placeholder="Job title, skills, company, or location..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>


<button className="jobs-search-btn" onClick={applyFilters}>

<FaSearch/> Search

</button>


<button className="jobs-clear-btn" onClick={clearFilters}>

<FaRedo/> Clear

</button>


</div>




{
message &&

<div className="job-message">

{message}

</div>

}


{
loadError &&

<div className="job-message error">

{loadError}

</div>

}




<div className="jobs-layout">




{/* SIDEBAR FILTERS */}


<div className="jobs-filter-bar">


<div className="filter-chip">

<label>Job Type</label>

<select

value={jobTypeFilter}

onChange={(e)=>setJobTypeFilter(e.target.value)}

>

<option value="">All Types</option>

{
JOB_TYPE_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>

</div>


<div className="filter-chip">

<label>Work Mode</label>

<select

value={workModeFilter}

onChange={(e)=>setWorkModeFilter(e.target.value)}

>

<option value="">All Modes</option>

{
WORK_MODE_OPTIONS.map(opt=>(

<option key={opt.value} value={opt.value}>{opt.label}</option>

))
}

</select>

</div>


<div className="filter-chip">

<label>Experience</label>

<input

type="text"

placeholder="e.g. 2 years, Fresher"

value={experienceFilter}

onChange={(e)=>setExperienceFilter(e.target.value)}

onBlur={applyFilters}

/>

</div>


{
(jobTypeFilter || workModeFilter || experienceFilter) &&

<button

className="filter-clear-chip"

onClick={()=>{

setJobTypeFilter("");

setWorkModeFilter("");

setExperienceFilter("");

}}

>

<FaRedo/> Clear Filters

</button>
}


</div>





{/* JOB LIST */}


<div className="jobs-main">



<div className="jobs-main-header">

<p>{filteredJobs.length} jobs found</p>

<select

value={sortBy}

onChange={(e)=>setSortBy(e.target.value)}

>

<option value="best_match">Best Match</option>

<option value="newest">Newest</option>

</select>

</div>




<div className="jobs-list">


{

filteredJobs.length>0

?

filteredJobs.map(job=>(


<div className="job-row-card" key={job.id}>


<div

className="company-avatar"

>

{(job.company||"?").charAt(0).toUpperCase()}

</div>



<div className="job-row-body">


<div className="job-row-top">

<div>

<h3

className="job-row-title"

onClick={()=>navigate(`/student/jobs/${job.id}`)}

>

{job.title}

</h3>

<p className="job-row-company">

{job.company || "Company"}

</p>

</div>


<div className="job-row-actions-top">

<div className="match-score small">

<FaStar/>

{job.match_score || 0}% Match

</div>

<button

className={"job-save-btn " + (job.is_saved ? "saved" : "")}

onClick={()=>handleSaveToggle(job)}

title={job.is_saved ? "Remove from saved" : "Save job"}

>

{job.is_saved ? <FaBookmark/> : <FaRegBookmark/>}

</button>

</div>

</div>



<div className="job-row-meta">

<span><FaMapMarkerAlt/> {job.location || "India"}</span>

<span><FaBriefcase/> {job.experience_required || "0-1"}</span>

<span><FaMoneyBillWave/> {job.salary || "Not Disclosed"}</span>

<span><FaLaptop/> {job.work_mode_display || "On-site"}</span>

</div>



{
job.skills_required &&

<div className="job-row-tags">

{

job.skills_required.split(",").slice(0,5).map((skill,index)=>(

<span key={index}>{skill.trim()}</span>

))

}

</div>

}



<div className="job-row-footer">

<div className="job-row-footer-left">

<span className="job-type-pill">

{job.job_type_display || "Full Time"}

</span>

<span className="job-row-time">

<FaClock/> {timeAgo(job.created_at)}

</span>

<span className="job-row-openings">

<FaUsers/> {job.vacancies || 0} opening{(job.vacancies||0)!==1?"s":""}

</span>

</div>


<div className="job-row-footer-right">

<button

className="details-link-btn"

onClick={()=>navigate(`/student/jobs/${job.id}`)}

>

View Details <FaArrowRight/>

</button>


<button

className={job.is_applied ? "applied-btn" : "apply-btn"}

disabled={job.is_applied}

onClick={()=>openApplyModal(job)}

>

{job.is_applied ? "Applied" : "Apply Now"}

</button>

</div>


</div>



</div>


</div>


))

:

<EmptyState

icon="search"

title={loadError ? "Couldn't load jobs" : "No jobs found"}

message={loadError ? loadError : "Try different search keywords"}

/>

}


</div>


</div>



</div>



</div>




{/* =================================
APPLY NOW MODAL
================================= */}

{
applyModalJob &&

<div className="apply-modal-overlay" onClick={closeApplyModal}>

<div className="apply-modal" onClick={(e)=>e.stopPropagation()}>

<button className="apply-modal-close" onClick={closeApplyModal}>
<FaTimes/>
</button>

<h2>Apply for {applyModalJob.title}</h2>

<p className="apply-modal-sub">
{applyModalJob.company || "Company"}
{" "}&middot;{" "}
{applyModalJob.location || "India"}
</p>


{/* ELIGIBILITY STATUS */}

{
eligibilityLoading ?

<div className="modal-eligibility-box checking">

Checking your eligibility...

</div>

:

eligibility &&

<div className={

"modal-eligibility-box " +

(eligibility.eligible ? "eligible" : "not-eligible")

}>

<div className="modal-eligibility-title">

{eligibility.eligible ? <FaCheck/> : <FaExclamationTriangle/>}

{eligibility.eligible ? "You're eligible for this job" : "You may not meet all requirements"}

</div>

{
!eligibility.eligible &&

<ul>

{
eligibility.conditions
    .filter(c=>c.status==="fail")
    .map((c,index)=>(

<li key={index}>{c.detail}</li>

))
}

</ul>

}

<button

type="button"

className="modal-eligibility-link"

onClick={()=>navigate(`/student/jobs/${applyModalJob.id}/eligibility`)}

>

View full eligibility breakdown

</button>

</div>

}


<label className="apply-modal-label">
Cover Letter (optional)
</label>

<textarea
className="apply-modal-textarea"
rows={5}
placeholder="Tell the recruiter why you're a great fit for this role..."
value={coverLetter}
onChange={(e)=>setCoverLetter(e.target.value)}
/>

<p className="apply-modal-note">
Your profile and latest resume will be shared with the recruiter.
</p>

<div className="apply-modal-actions">

<button
className="apply-modal-cancel"
onClick={closeApplyModal}
disabled={submittingApplication}
>
Cancel
</button>

<button
className="apply-modal-submit"
onClick={confirmApply}
disabled={submittingApplication}
>
<FaPaperPlane/>
{submittingApplication ? "Submitting..." : "Submit Application"}
</button>

</div>

</div>

</div>

}


</>


);



};




export default Jobs;
