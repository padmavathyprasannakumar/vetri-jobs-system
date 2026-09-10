import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementJobs,

    createPlacementJob,

    getPlacementCompanies,

    updatePlacementJobStatus

} from "../../../api/placementApi";


import {

    FaBriefcase,

    FaPlus,

    FaCheck,

    FaTimes

} from "react-icons/fa";


import "./JobListings.css";




const EMPTY_JOB = {

company_id:"", title:"", department:"", description:"", requirements:"", skills_required:"",

qualification_required:"", experience_required:"", salary:"",

location:"", job_type:"full_time", work_mode:"onsite",

vacancies:"1", application_deadline:"", interview_process:"",

eligibility_criteria:"", min_cgpa:"", min_percentage:"",

eligible_departments:"", eligible_graduation_years:"",

max_backlogs:"", min_age:"", max_age:"",

};




const JobListings = ()=>{


const [jobs,setJobs] = useState([]);

const [companies,setCompanies] = useState([]);

const [loading,setLoading] = useState(true);

const [showModal,setShowModal] = useState(false);

const [form,setForm] = useState(EMPTY_JOB);

const [creating,setCreating] = useState(false);

const [createError,setCreateError] = useState("");

const [statusUpdatingId,setStatusUpdatingId] = useState(null);




const loadJobs = ()=>{

getPlacementJobs()

.then(res=>setJobs(res.data || []))

.catch(err=>console.log("JOBS LOAD ERROR", err))

.finally(()=>setLoading(false));

};


useEffect(()=>{

loadJobs();

getPlacementCompanies()

.then(res=>setCompanies(res.data || []))

.catch(()=>{});

},[]);




const handleChange = (e)=>{

setForm({ ...form, [e.target.name]: e.target.value });

};




const handleCreate = async(e)=>{

e.preventDefault();

setCreating(true);

setCreateError("");

try{

const optionalNumericFields = [

"min_cgpa", "min_percentage", "max_backlogs", "min_age", "max_age"

];

const payload = { ...form };

optionalNumericFields.forEach(field=>{

if(payload[field] === "" || payload[field] === null || payload[field] === undefined){

delete payload[field];

}

});

await createPlacementJob(payload);

setShowModal(false);

setForm(EMPTY_JOB);

loadJobs();

}
catch(error){

setCreateError(error.response?.data?.error || "Could not create job. Please check the details.");

}
finally{

setCreating(false);

}

};




const handleStatusChange = async(jobId, newStatus)=>{

setStatusUpdatingId(jobId);

try{

await updatePlacementJobStatus(jobId, newStatus);

loadJobs();

}

catch(error){

console.log("STATUS UPDATE ERROR", error);

}

finally{

setStatusUpdatingId(null);

}

};




return(


<div className="job-listings-page">


<div className="jl-header">

<div className="jl-header-icon"><FaBriefcase/></div>

<div>

<h1>Job Listings</h1>

<p>Create and manage job opportunities across all companies</p>

</div>

<button className="jl-create-btn" onClick={()=>setShowModal(true)}>

<FaPlus/> Create Job

</button>

</div>


<div className="jl-table-wrap">

<table className="jl-table">

<thead>

<tr><th>#</th><th>Job Title</th><th>Company</th><th>Location</th><th>Type</th><th>Applications</th><th>Status</th><th>Actions</th></tr>

</thead>

<tbody>

{
loading ? (

<tr><td colSpan="8" className="jl-empty">Loading jobs...</td></tr>

) : jobs.length > 0 ? (

jobs.map((job,index)=>(

<tr key={job.id}>

<td>{index+1}</td>

<td><strong>{job.title}</strong></td>

<td>{job.company_name || "—"}</td>

<td>{job.location || "—"}</td>

<td>{job.job_type}</td>

<td>{job.applications_count}</td>

<td><span className={"jl-status-pill " + (job.status||"").toLowerCase()}>{job.status}</span></td>

<td>

<div className="jl-row-actions">

{
job.status !== "active" &&

<button

title="Approve"

className="jl-approve-btn"

disabled={statusUpdatingId===job.id}

onClick={()=>handleStatusChange(job.id, "active")}

>

<FaCheck/>

</button>
}

{
job.status !== "rejected" &&

<button

title="Reject"

className="jl-reject-btn"

disabled={statusUpdatingId===job.id}

onClick={()=>handleStatusChange(job.id, "rejected")}

>

<FaTimes/>

</button>
}

</div>

</td>

</tr>

))

) : (

<tr><td colSpan="8" className="jl-empty">No jobs posted yet</td></tr>

)
}

</tbody>

</table>

</div>


{
showModal &&

<div className="jl-modal-overlay" onClick={()=>setShowModal(false)}>

<div className="jl-modal" onClick={(e)=>e.stopPropagation()}>

<h2>Create Job</h2>

{
createError &&

<div className="jl-modal-error">{createError}</div>
}

<form onSubmit={handleCreate}>

<label>Company *</label>

<select required name="company_id" value={form.company_id} onChange={handleChange}>

<option value="">Select company</option>

{
companies.map(c=>(

<option key={c.id} value={c.id}>{c.company_name}</option>

))
}

</select>

<label>Job Title *</label>

<input required name="title" value={form.title} onChange={handleChange} placeholder="e.g. Software Engineer"/>

<label>Department</label>

<input name="department" value={form.department} onChange={handleChange} placeholder="e.g. Engineering"/>

<label>Job Description *</label>

<textarea required name="description" value={form.description} onChange={handleChange} placeholder="Describe the role"/>

<label>Requirements</label>

<textarea name="requirements" value={form.requirements} onChange={handleChange} placeholder="Key requirements for this role"/>

<label>Required Skills</label>

<input name="skills_required" value={form.skills_required} onChange={handleChange} placeholder="e.g. Python, React"/>

<div className="jl-modal-row">

<div>

<label>Qualification</label>

<input name="qualification_required" value={form.qualification_required} onChange={handleChange}/>

</div>

<div>

<label>Experience</label>

<input name="experience_required" value={form.experience_required} onChange={handleChange} placeholder="e.g. 0-2 years"/>

</div>

</div>

<div className="jl-modal-row">

<div>

<label>Salary</label>

<input name="salary" value={form.salary} onChange={handleChange}/>

</div>

<div>

<label>Location</label>

<input name="location" value={form.location} onChange={handleChange}/>

</div>

</div>

<div className="jl-modal-row">

<div>

<label>Employment Type</label>

<select name="job_type" value={form.job_type} onChange={handleChange}>

<option value="full_time">Full Time</option>

<option value="part_time">Part Time</option>

<option value="internship">Internship</option>

<option value="contract">Contract</option>

</select>

</div>

<div>

<label>Work Mode</label>

<select name="work_mode" value={form.work_mode} onChange={handleChange}>

<option value="onsite">On-site</option>

<option value="remote">Remote</option>

<option value="hybrid">Hybrid</option>

</select>

</div>

</div>

<div className="jl-modal-row">

<div>

<label>Number of Openings</label>

<input type="number" name="vacancies" value={form.vacancies} onChange={handleChange}/>

</div>

<div>

<label>Application Deadline</label>

<input type="date" name="application_deadline" value={form.application_deadline} onChange={handleChange}/>

</div>

</div>

<label>Interview Process</label>

<input name="interview_process" value={form.interview_process} onChange={handleChange} placeholder="e.g. Aptitude, Technical, HR"/>

<label>Eligibility Filters</label>

<div className="jl-modal-row">

<div>

<label>Min CGPA</label>

<input type="number" step="0.1" name="min_cgpa" value={form.min_cgpa} onChange={handleChange} placeholder="e.g. 7.0"/>

</div>

<div>

<label>Min Percentage</label>

<input type="number" step="0.1" name="min_percentage" value={form.min_percentage} onChange={handleChange} placeholder="e.g. 60"/>

</div>

</div>

<div className="jl-modal-row">

<div>

<label>Eligible Departments</label>

<input name="eligible_departments" value={form.eligible_departments} onChange={handleChange} placeholder="e.g. CSE, IT, ECE"/>

</div>

<div>

<label>Eligible Graduation Years</label>

<input name="eligible_graduation_years" value={form.eligible_graduation_years} onChange={handleChange} placeholder="e.g. 2025, 2026"/>

</div>

</div>

<div className="jl-modal-row">

<div>

<label>Max Backlogs Allowed</label>

<input type="number" name="max_backlogs" value={form.max_backlogs} onChange={handleChange} placeholder="e.g. 0"/>

</div>

<div>

<label>Age Range</label>

<div className="jl-modal-row">

<input type="number" name="min_age" value={form.min_age} onChange={handleChange} placeholder="Min age"/>

<input type="number" name="max_age" value={form.max_age} onChange={handleChange} placeholder="Max age"/>

</div>

</div>

</div>

<label>Eligibility Criteria (Notes)</label>

<input name="eligibility_criteria" value={form.eligibility_criteria} onChange={handleChange} placeholder="e.g. Min 60%, no active backlogs"/>

<div className="jl-modal-actions">

<button type="button" className="jl-modal-cancel" onClick={()=>setShowModal(false)}>Cancel</button>

<button type="submit" className="jl-modal-submit" disabled={creating}>{creating ? "Creating..." : "Create Job"}</button>

</div>

</form>

</div>

</div>
}


</div>


);



};




export default JobListings;
