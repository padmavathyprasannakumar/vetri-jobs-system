import React,{
    useEffect,
    useState
} from "react";


import {

    getStudentApplications

} from "../../../api/studentApi";



import {

    useNavigate

} from "react-router-dom";



import {

FaBuilding,
FaCalendarAlt,
FaBriefcase,
FaCheckCircle,
FaClock,
FaTimesCircle,
FaEye,
FaArrowRight,
FaHourglassHalf

} from "react-icons/fa";



import "./Applications.css";







const Applications=()=>{



const navigate=useNavigate();




const [applications,setApplications]=useState([]);

const [statusTab,setStatusTab]=useState("all");


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");









// ===============================
// LOAD APPLICATIONS
// ===============================


useEffect(()=>{


loadApplications();


},[]);









const loadApplications=async()=>{


try{


const response=

await getStudentApplications();



setApplications(

response.data

);



}

catch(error){


console.log(

"APPLICATION ERROR",

error

);



setError(

"Unable to load applications"

);



}


finally{


setLoading(false);


}



};











// ===============================
// STATUS ICON
// ===============================


const statusIcon=(status)=>{


switch(

status?.toLowerCase()

){


case "selected":

return <FaCheckCircle/>;



case "rejected":

return <FaTimesCircle/>;



case "interview":

return <FaCalendarAlt/>;



case "shortlisted":

return <FaCheckCircle/>;



default:

return <FaClock/>;


}



};











// ===============================
// STATUS CLASS
// ===============================


const statusClass=(status)=>{


return status

?

status

.toLowerCase()

.replace(

" ",

"-"

)

:

"pending";


};














if(loading){


return(


<div className="applications-loading">


<div className="loader"></div>


<p>

Loading applications...

</p>


</div>


);


}









return(



<div className="student-applications">









{/* HEADER */}



<div className="applications-banner">


<div>


<h1>

My Applications

</h1>



<p>

Track your job application journey

</p>


</div>



<div className="application-icon">


<FaBriefcase/>


</div>


</div>









{

error &&


<div className="application-error">


{error}


</div>


}













<div className="application-status-tabs">

{
[
{ key:"all", label:"All" },
{ key:"applied", label:"Applied" },
{ key:"shortlisted", label:"Shortlisted" },
{ key:"interview", label:"Interview" },
{ key:"pending", label:"Pending" },
{ key:"selected", label:"Offered" },
{ key:"rejected", label:"Rejected" },
].map(tab=>{

const count = tab.key==="all"

? applications.length

: applications.filter(a=>(a.status||"").toLowerCase()===tab.key).length;

return(

<button

key={tab.key}

className={statusTab===tab.key ? "active" : ""}

onClick={()=>setStatusTab(tab.key)}

>

{tab.label} ({count})

</button>

);

})
}

</div>


<div className="applications-list">






{

(()=>{

const filteredApplications = statusTab==="all"

? applications

: applications.filter(a=>(a.status||"").toLowerCase()===statusTab);

return filteredApplications.length > 0

?

filteredApplications.map(

(application)=>(





<div

className="application-card"

key={application.id}

>







<div className="application-header">





<div className="company-logo">


<FaBuilding/>


</div>







<div>


<h2>


{

application.job_title

||

application.job?.title

||

"Job Position"


}


</h2>




<p>


{

application.company_name

||

application.company?.name

||

"Company"


}


</p>


</div>







<div

className={

`application-status ${

statusClass(

application.status

)

}`

}


>


{

statusIcon(

application.status

)

}


<span>


{

application.status

||

"Pending"

}


</span>



</div>







</div>













{/* DETAILS */}



<div className="application-details">





<div>


<FaBriefcase/>


<p>

{

application.job_type

||

application.job?.job_type_display

||

"Full Time"

}

</p>


</div>







<div>


<FaCalendarAlt/>


<p>


Applied:

{" "}

{

application.applied_date

?

new Date(application.applied_date).toLocaleDateString(

undefined,

{ year:"numeric", month:"short", day:"numeric" }

)

:

"Recently"

}



</p>


</div>





</div>













{/* TRACKING */}



<div className="application-tracking">



<div className="track-item active">


<FaCheckCircle/>


<span>

Applied

</span>


</div>





<div className={

application.status

?

"track-item active"

:

"track-item"

}>


<FaHourglassHalf/>


<span>

Review

</span>


</div>






<div className={

application.status === "interview"

||

application.status === "selected"

?

"track-item active"

:

"track-item"

}>


<FaCalendarAlt/>


<span>

Interview

</span>


</div>








<div className={

application.status === "selected"

?

"track-item active"

:

"track-item"

}>


<FaCheckCircle/>


<span>

Selected

</span>


</div>






</div>













<div className="application-footer">





<button


onClick={()=>navigate(

`/student/jobs/${application.job?.id}`

)}


>


<FaEye/>


View Job


</button>







{

application.status==="interview"

&&


<button


className="interview-btn"


onClick={()=>navigate(

"/student/interviews"

)}


>


View Interview


<FaArrowRight/>


</button>


}




</div>









</div>





)


)

:




<div className="empty-applications">


<h2>

No Applications Yet

</h2>



<p>

Apply for jobs and track your progress here.

</p>



<button


onClick={()=>navigate("/student/jobs")}


>

Browse Jobs


</button>



</div>




;

})()

}





</div>








</div>



);


};



export default Applications;