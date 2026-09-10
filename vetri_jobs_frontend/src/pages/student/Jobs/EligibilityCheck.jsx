import React,{

useEffect,

useState

} from "react";



import {

useParams,

useNavigate

} from "react-router-dom";



import {

checkEligibility,

applyJob

} from "../../../api/studentApi";



import {

FaArrowLeft,

FaCheckCircle,

FaTimesCircle,

FaInfoCircle,

FaClipboardCheck,

FaPaperPlane

} from "react-icons/fa";



import "./Jobs.css";




const EligibilityCheck=()=>{



const { id } = useParams();


const navigate = useNavigate();


const [result,setResult]=useState(null);


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");


const [applying,setApplying]=useState(false);


const [message,setMessage]=useState("");








useEffect(()=>{

checkJob();

},[id]);




const checkJob=async()=>{

try{

const response = await checkEligibility(id);

setResult(response.data);

}
catch(error){

console.log("ELIGIBILITY ERROR", error);

setError(

error.response?.data?.error ||

"Unable to check eligibility"

);

}
finally{

setLoading(false);

}

};




const handleApply=async()=>{

try{

setApplying(true);

await applyJob(id);

setMessage("Application submitted successfully");

}
catch(error){

console.log(error);

setMessage(

error.response?.data?.message || "Unable to apply"

);

}
finally{

setApplying(false);

}

};




const statusIcon=(status)=>{

if(status==="pass") return <FaCheckCircle/>;

if(status==="fail") return <FaTimesCircle/>;

return <FaInfoCircle/>;

};








if(loading){

return(

<div className="jobs-loading">

<div className="loader"></div>

<p>Checking eligibility...</p>

</div>

);

}




if(error){

return(

<div className="student-jobs">

<button className="back-to-jobs-link" onClick={()=>navigate(-1)}>

<FaArrowLeft/> Back

</button>

<div className="job-message">{error}</div>

</div>

);

}








return(



<div className="student-jobs">




<button

className="back-to-jobs-link"

onClick={()=>navigate(`/student/jobs/${id}`)}

>

<FaArrowLeft/> Back to Job

</button>




<div className="eligibility-header-card">


<div className={"eligibility-badge " + (result?.eligible ? "eligible" : "not-eligible")}>

{
result?.eligible ? <FaCheckCircle/> : <FaTimesCircle/>
}

{result?.eligible ? "Eligible" : "Not Eligible"}

</div>


<h1>{result?.job_title}</h1>

<p>{result?.summary}</p>


</div>




{
message &&

<div className="job-message">{message}</div>

}




<div className="job-detail-card">


<h2><FaClipboardCheck/> Eligibility Conditions</h2>


<div className="eligibility-conditions-list">

{
(result?.conditions || []).map((cond,index)=>(

<div className={"eligibility-condition-row " + cond.status} key={index}>

<div className="eligibility-condition-icon">

{statusIcon(cond.status)}

</div>

<div>

<h4>{cond.label}</h4>

<p>{cond.detail}</p>

</div>

</div>

))
}

</div>



{
result?.eligible &&

<button

className="apply-btn eligibility-apply-btn"

onClick={handleApply}

disabled={applying}

>

<FaPaperPlane/> {applying ? "Submitting..." : "Apply Now"}

</button>

}


</div>




</div>


);



};




export default EligibilityCheck;
