import React, {

    useState

} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    createCompanyJob

} from "../../../api/companyApi";


import {

    FaBriefcase,

    FaFileAlt,

    FaListUl,

    FaEye,

    FaMapMarkerAlt,

    FaMoneyBillWave,

    FaGraduationCap,

    FaLaptop,

    FaCalendarAlt,

    FaUsers,

    FaArrowLeft,

    FaArrowRight,

    FaCheck

} from "react-icons/fa";


import "./CreateJob.css";




const TABS = [

    { key:"details", label:"Job Details", icon:<FaBriefcase/> },

    { key:"description", label:"Job Description", icon:<FaFileAlt/> },

    { key:"requirements", label:"Requirements", icon:<FaListUl/> },

    { key:"preview", label:"Preview", icon:<FaEye/> },

];




const CreateJob = ()=>{


const navigate = useNavigate();



const [loading,setLoading]=useState(false);


const [message,setMessage]=useState("");


const [activeTab,setActiveTab]=useState("details");



const [formData,setFormData]=useState({

title:"",

department:"",

description:"",

requirements:"",

skills_required:"",

qualification_required:"",

experience_required:"",

location:"",

salary:"",

job_type:"full_time",

work_mode:"onsite",

vacancies:1,

application_deadline:"",

interview_process:"",

eligibility_criteria:"",

min_cgpa:"",

min_percentage:"",

eligible_departments:"",

eligible_graduation_years:"",

max_backlogs:"",

min_age:"",

max_age:"",

is_active:true,

});




const handleChange=(e)=>{

const { name, value, type, checked } = e.target;

setFormData({

...formData,

[name]: type==="checkbox" ? checked : value

});

};




const tabIndex = TABS.findIndex(t=>t.key===activeTab);


const goNext=()=>{

if(tabIndex < TABS.length-1) setActiveTab(TABS[tabIndex+1].key);

};


const goBack=()=>{

if(tabIndex > 0) setActiveTab(TABS[tabIndex-1].key);

};




const handleSubmit=async()=>{


if(!formData.title || !formData.description){

setMessage("Job title and description are required");

setActiveTab("details");

return;

}


setLoading(true);


setMessage("");


try{


const payload = {

...formData,

status: formData.is_active ? "active" : "pending",

min_cgpa: formData.min_cgpa === "" ? null : formData.min_cgpa,

min_percentage: formData.min_percentage === "" ? null : formData.min_percentage,

max_backlogs: formData.max_backlogs === "" ? null : formData.max_backlogs,

min_age: formData.min_age === "" ? null : formData.min_age,

max_age: formData.max_age === "" ? null : formData.max_age,

application_deadline: formData.application_deadline === "" ? null : formData.application_deadline,

};


await createCompanyJob(payload);


setMessage("Job posted successfully");


setTimeout(()=>{

navigate("/company/jobs");

},1200);



}

catch(error){


console.log(error);


const errorData = error.response?.data;

let realMessage = errorData?.message || errorData?.error;

if(!realMessage && errorData && typeof errorData === "object"){

    // DRF validation errors look like {"field_name": ["reason"]} -
    // surface the first one instead of a generic message, so
    // whichever field is actually wrong is visible to the user.
    const firstField = Object.keys(errorData)[0];

    const firstError = errorData[firstField];

    if(firstField && firstError){

        realMessage = `${firstField}: ${Array.isArray(firstError) ? firstError[0] : firstError}`;

    }

}

setMessage(

realMessage ||

"Unable to create job"

);


}

finally{


setLoading(false);


}



};




const jobTypeLabel = {

full_time:"Full Time", part_time:"Part Time",

internship:"Internship", contract:"Contract"

}[formData.job_type] || formData.job_type;


const workModeLabel = {

onsite:"On-site", remote:"Remote", hybrid:"Hybrid"

}[formData.work_mode] || formData.work_mode;








return(



<div className="create-job-page">




{/* BANNER */}


<div className="create-job-banner">


<div className="create-job-banner-icon">

<FaBriefcase/>

</div>


<div>

<h1>Post New Job</h1>

<p>Fill in the details to create a new job post</p>

</div>


</div>




{
message &&

<div className="create-job-message">{message}</div>

}




{/* TABS */}


<div className="create-job-tabs">


{
TABS.map((tab,index)=>(

<button

key={tab.key}

className={

activeTab===tab.key

? "create-job-tab active"

: index < tabIndex

? "create-job-tab done"

: "create-job-tab"

}

onClick={()=>setActiveTab(tab.key)}

>

{tab.icon} {tab.label}

</button>

))
}


</div>




<div className="create-job-form-card">




{/* =============== JOB DETAILS =============== */}

{
activeTab==="details" &&

<div className="create-job-section">


<h2><FaBriefcase/> Job Details</h2>


<div className="form-grid">


<div className="form-field">

<label>Job Title *</label>

<input

name="title"

value={formData.title}

onChange={handleChange}

placeholder="e.g. Senior Frontend Developer"

/>

</div>


<div className="form-field">

<label>Department</label>

<input

name="department"

value={formData.department}

onChange={handleChange}

placeholder="e.g. Engineering"

/>

</div>


<div className="form-field">

<label>Job Type *</label>

<select name="job_type" value={formData.job_type} onChange={handleChange}>

<option value="full_time">Full Time</option>

<option value="part_time">Part Time</option>

<option value="internship">Internship</option>

<option value="contract">Contract</option>

</select>

</div>


<div className="form-field">

<label>Experience Level</label>

<input

name="experience_required"

value={formData.experience_required}

onChange={handleChange}

placeholder="e.g. 0-1 years, Fresher"

/>

</div>


<div className="form-field">

<label><FaLaptop/> Work Mode</label>

<select name="work_mode" value={formData.work_mode} onChange={handleChange}>

<option value="onsite">On-site</option>

<option value="remote">Remote</option>

<option value="hybrid">Hybrid</option>

</select>

</div>


<div className="form-field">

<label><FaUsers/> No. of Openings *</label>

<input

type="number"

min="1"

name="vacancies"

value={formData.vacancies}

onChange={handleChange}

/>

</div>


<div className="form-field">

<label><FaMapMarkerAlt/> Location *</label>

<input

name="location"

value={formData.location}

onChange={handleChange}

placeholder="e.g. Bangalore, India"

/>

</div>


<div className="form-field">

<label><FaMoneyBillWave/> Salary Range</label>

<input

name="salary"

value={formData.salary}

onChange={handleChange}

placeholder="e.g. ₹6,00,000 - ₹9,00,000"

/>

</div>


<div className="form-field">

<label><FaCalendarAlt/> Application Deadline</label>

<input

type="date"

name="application_deadline"

value={formData.application_deadline}

onChange={handleChange}

/>

</div>


</div>



<label className="active-toggle">

<input

type="checkbox"

name="is_active"

checked={formData.is_active}

onChange={handleChange}

/>

Is this job active?

</label>


</div>

}




{/* =============== JOB DESCRIPTION =============== */}

{
activeTab==="description" &&

<div className="create-job-section">


<h2><FaFileAlt/> Job Description</h2>


<div className="form-field full">

<label>Job Description *</label>

<textarea

name="description"

rows={6}

value={formData.description}

onChange={handleChange}

placeholder="Describe the role, team, and what a day in this job looks like..."

/>

</div>


<div className="form-field full">

<label>Interview Process</label>

<textarea

name="interview_process"

rows={3}

value={formData.interview_process}

onChange={handleChange}

placeholder="e.g. Screening call → Technical round → HR round"

/>

</div>


</div>

}




{/* =============== REQUIREMENTS =============== */}

{
activeTab==="requirements" &&

<div className="create-job-section">


<h2><FaListUl/> Requirements</h2>


<div className="form-field full">

<label>Key Responsibilities</label>

<textarea

name="requirements"

rows={4}

value={formData.requirements}

onChange={handleChange}

placeholder="One responsibility per line..."

/>

</div>


<div className="form-field full">

<label>Required Skills (comma separated)</label>

<input

name="skills_required"

value={formData.skills_required}

onChange={handleChange}

placeholder="e.g. React, Node.js, SQL"

/>

</div>


<div className="form-grid">


<div className="form-field">

<label><FaGraduationCap/> Qualification</label>

<input

name="qualification_required"

value={formData.qualification_required}

onChange={handleChange}

placeholder="e.g. B.Tech / B.E."

/>

</div>


<div className="form-field">

<label>Eligibility Criteria (notes)</label>

<input

name="eligibility_criteria"

value={formData.eligibility_criteria}

onChange={handleChange}

placeholder="e.g. No active backlogs"

/>

</div>


</div>



<h3 className="requirements-subheading">Eligibility Engine Conditions (optional)</h3>

<p className="requirements-subnote">

Leave any field blank to skip that condition - students are automatically

marked Eligible / Not Eligible against whatever you set here.

</p>


<div className="form-grid">


<div className="form-field">

<label>Minimum CGPA (out of 10)</label>

<input

type="number"

step="0.01"

min="0"

max="10"

name="min_cgpa"

value={formData.min_cgpa}

onChange={handleChange}

placeholder="e.g. 7.0"

/>

</div>


<div className="form-field">

<label>Minimum Percentage (10th/12th)</label>

<input

type="number"

step="0.1"

min="0"

max="100"

name="min_percentage"

value={formData.min_percentage}

onChange={handleChange}

placeholder="e.g. 60"

/>

</div>


<div className="form-field">

<label>Eligible Departments</label>

<input

name="eligible_departments"

value={formData.eligible_departments}

onChange={handleChange}

placeholder="e.g. CSE, IT, ECE (blank = all)"

/>

</div>


<div className="form-field">

<label>Eligible Graduation Years</label>

<input

name="eligible_graduation_years"

value={formData.eligible_graduation_years}

onChange={handleChange}

placeholder="e.g. 2025, 2026 (blank = any)"

/>

</div>


<div className="form-field">

<label>Maximum Backlogs Allowed</label>

<input

type="number"

min="0"

name="max_backlogs"

value={formData.max_backlogs}

onChange={handleChange}

placeholder="e.g. 0"

/>

</div>


<div className="form-field">

<label>Age Range</label>

<div className="age-range-row">

<input

type="number"

min="0"

name="min_age"

value={formData.min_age}

onChange={handleChange}

placeholder="Min"

/>

<span>to</span>

<input

type="number"

min="0"

name="max_age"

value={formData.max_age}

onChange={handleChange}

placeholder="Max"

/>

</div>

</div>


</div>


</div>

}




{/* =============== PREVIEW =============== */}

{
activeTab==="preview" &&

<div className="create-job-section">


<h2><FaEye/> Preview</h2>


<div className="job-preview-card">


<h3>{formData.title || "Untitled Job"}</h3>

<p className="preview-department">{formData.department || "No department"}</p>


<div className="preview-meta">

<span><FaMapMarkerAlt/> {formData.location || "Not specified"}</span>

<span><FaMoneyBillWave/> {formData.salary || "Not disclosed"}</span>

<span><FaLaptop/> {workModeLabel}</span>

<span><FaUsers/> {formData.vacancies || 0} opening{(formData.vacancies||0)!==1?"s":""}</span>

</div>


<span className="preview-job-type">{jobTypeLabel}</span>


<h4>Description</h4>

<p>{formData.description || "No description provided"}</p>


{
formData.skills_required &&

<>

<h4>Skills</h4>

<div className="preview-skills">

{
formData.skills_required.split(",").map((skill,index)=>(

<span key={index}>{skill.trim()}</span>

))
}

</div>

</>

}


</div>


</div>

}




{/* NAVIGATION */}


<div className="create-job-nav">


<button

className="wizard-back-btn"

onClick={goBack}

disabled={tabIndex===0}

>

<FaArrowLeft/> Back

</button>


{
tabIndex < TABS.length-1 ?

<button className="wizard-next-btn" onClick={goNext}>

Next: {TABS[tabIndex+1].label} <FaArrowRight/>

</button>

:

<button

className="wizard-submit-btn"

onClick={handleSubmit}

disabled={loading}

>

<FaCheck/> {loading ? "Posting..." : "Post Job"}

</button>

}


</div>




</div>




</div>


);



};




export default CreateJob;
