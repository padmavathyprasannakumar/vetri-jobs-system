import React,{

useEffect,

useState

} from "react";



import {

getSavedJobs,

removeSavedJob

} from "../../../api/studentApi";



import {

FaBuilding,

FaMapMarkerAlt,

FaBriefcase,

FaMoneyBillWave,

FaTrash,

FaPaperPlane,

FaBookmark,

FaClock

} from "react-icons/fa";



import {

useNavigate

} from "react-router-dom";



import "./SavedJobs.css";







const SavedJobs=()=>{



const navigate=useNavigate();




const [jobs,setJobs]=useState([]);


const [loading,setLoading]=useState(true);


const [message,setMessage]=useState("");









// =====================================
// LOAD SAVED JOBS
// =====================================


useEffect(()=>{


loadSavedJobs();


},[]);









const loadSavedJobs=async()=>{


try{


const response=

await getSavedJobs();



setJobs(

response.data

);



}

catch(error){


console.log(

"SAVED JOB ERROR",

error

);



}

finally{


setLoading(false);


}



};











// =====================================
// REMOVE SAVED JOB
// =====================================


const handleRemove=async(id)=>{


try{


await removeSavedJob(id);



setMessage(

"Job removed from saved list"

);



loadSavedJobs();



}

catch(error){


console.log(error);



}



};












// =====================================
// APPLY JOB
// =====================================
// (Applying now happens on the Job Details page, via the
// Apply Now popup - this page just navigates there with
// ?apply=1 so it opens automatically.)












if(loading){


return(


<div className="saved-loading">


<div className="loader"></div>


<p>

Loading saved jobs...

</p>


</div>


);


}









return(



<div className="saved-jobs-page">







{/* HEADER */}



<div className="saved-banner">



<div>


<h1>

Saved Jobs

</h1>



<p>

Jobs you saved for future applications

</p>


</div>





<div className="saved-icon">


<FaBookmark/>


</div>



</div>









{

message &&


<div className="saved-message">


{message}


</div>


}









<div className="saved-job-container">







{

jobs.length>0

?



jobs.map(job=>(





<div

className="saved-job-card"

key={job.id}

>









<div className="saved-job-header">





<div className="company-logo">


<FaBuilding/>


</div>







<div>


<h2>

{

job.title

||

job.job_title

}


</h2>



<p>


{

job.company

||

job.company_name

||

"Company"


}


</p>


</div>







</div>












<div className="saved-job-details">





<div>


<FaMapMarkerAlt/>


<span>


{

job.location

||

"India"


}


</span>


</div>








<div>


<FaBriefcase/>


<span>


{

job.job_type

||

"Full Time"


}


</span>


</div>








<div>


<FaMoneyBillWave/>


<span>


{

job.salary

||

"Negotiable"


}


</span>


</div>








<div>


<FaClock/>


<span>


Saved Job


</span>


</div>







</div>













<div className="saved-actions">





<button


className="view-job-btn"


onClick={()=>navigate(

`/student/jobs/${job.id}`

)}


>


View Details


</button>








<button


className="apply-saved-btn"


onClick={()=>navigate(

`/student/jobs/${job.id}?apply=1`

)}


>


<FaPaperPlane/>

Apply


</button>









<button


className="remove-btn"


onClick={()=>handleRemove(job.id)}


>


<FaTrash/>

Remove


</button>







</div>









</div>





))




:





<div className="empty-saved">


<FaBookmark/>


<h2>

No Saved Jobs

</h2>



<p>

Save interesting jobs and apply later.

</p>



<button


onClick={()=>navigate("/student/jobs")}


>


Browse Jobs


</button>



</div>




}





</div>









</div>



);


};





export default SavedJobs;