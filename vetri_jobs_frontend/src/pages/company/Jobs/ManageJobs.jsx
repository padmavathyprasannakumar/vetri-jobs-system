import React,{
useEffect,
useState
} from "react";


import {

    useNavigate

} from "react-router-dom";



import {

getCompanyJobs,

createCompanyJob,

updateCompanyJob,

deleteCompanyJob

} from "../../../api/companyApi";


import {

FaPlus,

FaEdit,

FaTrash,

FaSearch,

FaBriefcase,

FaMapMarkerAlt,

FaMoneyBill,

FaUsers,

FaTimes,

FaCalendarAlt,

FaGraduationCap,

FaTasks,

FaClipboardList

} from "react-icons/fa";


import "./ManageJobs.css";





const ManageJobs=()=>{


const navigate = useNavigate();


const [jobs,setJobs]=useState([]);


const [filteredJobs,setFilteredJobs]=useState([]);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [showForm,setShowForm]=useState(false);


const [editId,setEditId]=useState(null);


const [message,setMessage]=useState("");


const [selectedJob,setSelectedJob]=useState(null);





const initialForm={


title:"",

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

eligibility_criteria:""


};



const [form,setForm]=useState(initialForm);






useEffect(()=>{

loadJobs();

},[]);







const loadJobs=async()=>{


try{


const response=await getCompanyJobs();


setJobs(response.data);


setFilteredJobs(response.data);


}

catch(error){

console.log(
"UPDATE ERROR",
error.response?.data
);


setMessage(

JSON.stringify(
error.response?.data
)

||
"Unable to save job"

);

}

finally{

setLoading(false);

}


};










useEffect(()=>{


const result=jobs.filter(job=>

job.title

?.toLowerCase()

.includes(

search.toLowerCase()

)

);


setFilteredJobs(result);


},[search,jobs]);











const handleChange=(e)=>{


setForm({

...form,

[e.target.name]:

e.target.value

});


};









const handleSubmit=async(e)=>{


e.preventDefault();


try{


if(editId){


await updateCompanyJob(

editId,

form

);


setMessage(
"Job updated successfully"
);


}

else{


await createCompanyJob(

form

);


setMessage(
"Job created successfully"
);


}



setForm(initialForm);


setEditId(null);


setShowForm(false);


loadJobs();



}

catch(error){

console.log(error);


setMessage(
"Unable to save job"
);


}



};











const handleViewJob=(job)=>{

setSelectedJob(job);

};




const closeJobDetails=()=>{

setSelectedJob(null);

};




const handleEdit=(job)=>{


setForm({


title:job.title || "",


description:job.description || "",


requirements:job.requirements || "",


skills_required:job.skills_required || "",


qualification_required:
job.qualification_required || "",


experience_required:
job.experience_required || "",


location:job.location || "",


salary:job.salary || "",


job_type:
job.job_type || "full_time",


work_mode:
job.work_mode || "onsite",


vacancies:
job.vacancies || 1,


application_deadline:
job.application_deadline || "",


interview_process:
job.interview_process || "",


eligibility_criteria:
job.eligibility_criteria || ""

});


setEditId(job.id);


setShowForm(true);


};









const handleDelete=async(id)=>{


if(!window.confirm(
"Delete this job?"
))

return;



try{


await deleteCompanyJob(id);


setMessage(
"Job deleted successfully"
);


loadJobs();


}

catch(error){

console.log(error);

}


};







if(loading){


return(

<div className="jobs-loading">

Loading jobs...

</div>

);

}









return(


<div className="manage-jobs">





<div className="manage-header">


<div>

<h1>

Manage Jobs

</h1>


<p>

Create and manage your recruitment posts

</p>


</div>



<button

onClick={()=>navigate("/company/jobs/create")}

>

<FaPlus/>

Post New Job

</button>


</div>









{
message &&

<div className="job-message">

{message}

</div>

}









<div className="job-search">


<FaSearch/>


<input

placeholder="Search jobs..."

value={search}

onChange={
e=>setSearch(e.target.value)
}

/>


</div>









{
showForm &&


<div className="job-form-card">


<h2>

{
editId
?
"Edit Job"
:
"Create Job"

}

</h2>




<form onSubmit={handleSubmit}>


<label className="edit-job-label">Job Title</label>
<input


name="title"

placeholder="Job Title"

value={form.title}

onChange={handleChange}

/>





<label className="edit-job-label">Job Description</label>
<textarea


name="description"

placeholder="Job Description"

value={form.description}

onChange={handleChange}

/>






<label className="edit-job-label">Requirements</label>
<textarea


name="requirements"

placeholder="Requirements"

value={form.requirements}

onChange={handleChange}

/>






<label className="edit-job-label">Required Skills</label>
<textarea


name="skills_required"

placeholder="Required Skills"

value={form.skills_required}

onChange={handleChange}

/>








<label className="edit-job-label">Qualification</label>
<input


name="qualification_required"

placeholder="Qualification"

value={form.qualification_required}

onChange={handleChange}

/>







<label className="edit-job-label">Experience</label>
<input


name="experience_required"

placeholder="Experience"

value={form.experience_required}

onChange={handleChange}

/>








<label className="edit-job-label">Location</label>
<input


name="location"

placeholder="Location"

value={form.location}

onChange={handleChange}

/>







<label className="edit-job-label">Salary</label>
<input


name="salary"

placeholder="Salary"

value={form.salary}

onChange={handleChange}

/>








<label className="edit-job-label">Job Type</label>
<select


name="job_type"

value={form.job_type}

onChange={handleChange}

>


<option value="full_time">

Full Time

</option>


<option value="part_time">

Part Time

</option>


<option value="internship">

Internship

</option>


<option value="contract">

Contract

</option>


</select>








<label className="edit-job-label">Work Mode</label>
<select


name="work_mode"

value={form.work_mode}

onChange={handleChange}

>


<option value="onsite">

On Site

</option>


<option value="remote">

Remote

</option>


<option value="hybrid">

Hybrid

</option>


</select>








<label className="edit-job-label">Number of Openings</label>
<input

type="number"


name="vacancies"

placeholder="Number of openings"

value={form.vacancies}

onChange={handleChange}

/>







<label className="edit-job-label">Application Deadline</label>
<input

type="date"


name="application_deadline"

value={form.application_deadline}

onChange={handleChange}

/>








<label className="edit-job-label">Interview Process</label>
<textarea


name="interview_process"

placeholder="Interview Process"

value={form.interview_process}

onChange={handleChange}

/>







<label className="edit-job-label">Eligibility Criteria</label>
<textarea


name="eligibility_criteria"

placeholder="Eligibility Criteria"

value={form.eligibility_criteria}

onChange={handleChange}

/>







<div className="form-actions">


<button type="submit">

Save Job

</button>


<button

type="button"

onClick={()=>setShowForm(false)}

>

Cancel

</button>


</div>





</form>


</div>

}












<div className="job-grid">



{

filteredJobs.length>0


?


filteredJobs.map(job=>(


<div

className="company-job-card"

key={job.id}

>


<div
className="job-title job-title-link"
onClick={()=>handleViewJob(job)}
title="Click to view full job details"
>


<FaBriefcase/>

<h3>

{job.title}

</h3>


</div>






<p>

<FaMapMarkerAlt/>

{job.location}

</p>





<p>

<FaMoneyBill/>

{job.salary || "Negotiable"}

</p>







<p>

<FaUsers/>

{job.vacancies}

Openings

</p>







<p>

{job.description}

</p>






<div className="job-actions">


<button

onClick={()=>handleEdit(job)}

>

<FaEdit/>

Edit

</button>



<button

onClick={()=>handleDelete(job.id)}

>

<FaTrash/>

Delete

</button>



</div>





</div>


))


:


<div className="empty-jobs">

No jobs posted yet

</div>


}


</div>



{
selectedJob &&

<div
className="job-details-overlay"
onClick={closeJobDetails}
>

<div
className="job-details-modal"
onClick={(e)=>e.stopPropagation()}
>

<button
className="job-details-close"
onClick={closeJobDetails}
>
<FaTimes/>
</button>

<div className="job-details-header">
<FaBriefcase/>
<h2>{selectedJob.title}</h2>
</div>

<div className="job-details-grid">

<div className="job-details-item">
<FaMapMarkerAlt/>
<div>
<span className="job-details-label">Location</span>
<span>{selectedJob.location || "Not specified"}</span>
</div>
</div>

<div className="job-details-item">
<FaMoneyBill/>
<div>
<span className="job-details-label">Salary</span>
<span>{selectedJob.salary || "Negotiable"}</span>
</div>
</div>

<div className="job-details-item">
<FaUsers/>
<div>
<span className="job-details-label">Openings</span>
<span>{selectedJob.vacancies} Openings</span>
</div>
</div>

<div className="job-details-item">
<FaTasks/>
<div>
<span className="job-details-label">Job Type</span>
<span>{selectedJob.job_type_display || selectedJob.job_type}</span>
</div>
</div>

<div className="job-details-item">
<FaBriefcase/>
<div>
<span className="job-details-label">Work Mode</span>
<span>{selectedJob.work_mode_display || selectedJob.work_mode}</span>
</div>
</div>

<div className="job-details-item">
<FaCalendarAlt/>
<div>
<span className="job-details-label">Application Deadline</span>
<span>{selectedJob.application_deadline || "Not specified"}</span>
</div>
</div>

</div>

<div className="job-details-section">
<h4><FaClipboardList/> Description</h4>
<p>{selectedJob.description || "No description provided"}</p>
</div>

<div className="job-details-section">
<h4><FaClipboardList/> Requirements</h4>
<p>{selectedJob.requirements || "Not specified"}</p>
</div>

<div className="job-details-section">
<h4><FaClipboardList/> Required Skills</h4>
<p>{selectedJob.skills_required || "Not specified"}</p>
</div>

<div className="job-details-section">
<h4><FaGraduationCap/> Qualification</h4>
<p>{selectedJob.qualification_required || "Not specified"}</p>
</div>

<div className="job-details-section">
<h4><FaGraduationCap/> Experience Required</h4>
<p>{selectedJob.experience_required || "Not specified"}</p>
</div>

<div className="job-details-section">
<h4><FaClipboardList/> Eligibility Criteria</h4>
<p>{selectedJob.eligibility_criteria || "Not specified"}</p>
</div>

<div className="job-details-section">
<h4><FaClipboardList/> Interview Process</h4>
<p>{selectedJob.interview_process || "Not specified"}</p>
</div>

<div className="job-details-actions">
<button
onClick={()=>{
closeJobDetails();
handleEdit(selectedJob);
}}
>
<FaEdit/>
Edit Job
</button>

<button
className="job-details-close-btn"
onClick={closeJobDetails}
>
Close
</button>
</div>

</div>

</div>

}




</div>


);


};


export default ManageJobs;