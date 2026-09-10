import React,{
useState
} from "react";


import {

useParams,

useNavigate

} from "react-router-dom";



import {

applyJob

} from "../../../api/studentApi";



import {

FaPaperPlane,

FaCheckCircle,

FaArrowLeft,

FaFileAlt,

FaExclamationTriangle,

FaUserCheck

} from "react-icons/fa";



import "./Jobs.css";







const ApplyJob=()=>{


const {

id

}=useParams();



const navigate=useNavigate();





const [loading,setLoading]=useState(false);


const [message,setMessage]=useState("");


const [success,setSuccess]=useState(false);









// =================================
// SUBMIT APPLICATION
// =================================


const submitApplication=async()=>{


if(success)

return;



try{


setLoading(true);


setMessage("");





await applyJob(id);





setSuccess(true);



setMessage(

"Application submitted successfully"

);






setTimeout(()=>{


navigate(

"/student/applications"

);



},2000);





}



catch(error){



console.log(

"APPLICATION ERROR",

error

);




setMessage(


error.response?.data?.message

||

"Application failed. Please try again."


);



}



finally{


setLoading(false);


}



};









return(



<div className="student-jobs">







<button


className="back-btn"


onClick={()=>navigate(-1)}


>


<FaArrowLeft/>

Back


</button>









<div className="apply-page">







<div className="apply-header">


<FaPaperPlane/>




<h1>

Apply For Job

</h1>




<p>

Submit your application to the company.

</p>




</div>









<div className="apply-card">







<div className="application-info">



<FaFileAlt/>




<div>


<h3>

Job Application

</h3>



<p>

Your profile, resume and details will be shared with the recruiter.

</p>


</div>



</div>









<div className="warning-box">


<FaExclamationTriangle/>




<p>


Make sure your profile is completed and your latest resume is uploaded before applying.


</p>



</div>









<div className="application-check">



<div>


<FaUserCheck/>


<p>

Profile Verification

</p>


</div>



<div>


<FaFileAlt/>


<p>

Resume Attached

</p>


</div>



</div>









{

message &&



<div


className={

success

?

"success-message"

:

"error-message"

}


>


{


success &&

<FaCheckCircle/>

}



{message}



</div>



}









<button


className="apply-confirm-btn"


onClick={submitApplication}


disabled={loading || success}


>




<FaPaperPlane/>




{


loading

?

"Submitting..."

:

success

?

"Applied Successfully"

:

"Confirm Apply"


}




</button>









</div>









</div>







</div>



);



};



export default ApplyJob;