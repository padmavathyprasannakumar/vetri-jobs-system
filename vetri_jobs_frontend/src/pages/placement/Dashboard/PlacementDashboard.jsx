import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementDashboard

} from "../../../api/placementApi";


import {

    FaUserGraduate,

    FaBuilding,

    FaBriefcase,

    FaUserCheck,

    FaChartLine,

    FaArrowRight,

    FaCalendarAlt,

    FaCheckCircle

} from "react-icons/fa";


import {

    useNavigate

} from "react-router-dom";


import EmptyState from "../../../components/EmptyState/EmptyState";

import "./PlacementDashboard.css";







const PlacementDashboard = ()=>{



const navigate = useNavigate();


const recruiterName = (()=>{

try{

const stored = JSON.parse(localStorage.getItem("user") || "null");

return stored?.full_name || stored?.username || "there";

}
catch(e){

return "there";

}

})();



const [dashboard,setDashboard]=useState(null);


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");









useEffect(()=>{


loadDashboard();


},[]);









// =====================================
// LOAD DASHBOARD DATA
// =====================================


const loadDashboard=async()=>{


try{


const response =

await getPlacementDashboard();



setDashboard(

response.data

);



}

catch(error){


console.log(error);


setError(

"Unable to load placement dashboard"

);



}

finally{


setLoading(false);


}



};









if(loading){


return(


<div className="placement-loading">


<div className="spinner-border"></div>


<p>

Loading placement dashboard...

</p>


</div>


);


}









if(error){


return(


<div className="placement-error">


{error}


</div>


);


}









return(



<div className="placement-dashboard">







{/* ===========================
        HEADER
=========================== */}



<section className="dashboard-header-banner">


<div>

<h1>Welcome back, {recruiterName}! 👋</h1>

<p>Manage placements smarter with AI-powered insights.</p>

</div>


<div className="placement-header-quote">

"Empowering Careers, Building Futures."

</div>


<div className="placement-header-icon">

<FaChartLine/>

</div>


</section>









{/* ===========================
        STAT CARDS
=========================== */}



<div className="placement-stats">







<div className="placement-card blue">


<div>


<h3>


{

dashboard?.total_students

||

0

}


</h3>


<p>

Total Students

</p>


</div>



<FaUserGraduate/>


</div>









<div className="placement-card green">


<div>


<h3>


{

dashboard?.total_companies

||

0

}


</h3>


<p>

Companies

</p>


</div>



<FaBuilding/>


</div>









<div className="placement-card orange">


<div>


<h3>


{

dashboard?.active_drives

||

0

}


</h3>


<p>

Active Drives

</p>


</div>



<FaBriefcase/>


</div>









<div className="placement-card purple">


<div>


<h3>


{

dashboard?.placed_students

||

0

}


</h3>


<p>

Placed Students

</p>


</div>



<FaUserCheck/>


</div>









</div>









{/* ===========================
        PLACEMENT RATE
=========================== */}



<section className="placement-rate">



<h2>

Placement Success Rate

</h2>





<div className="rate-container">



<div className="rate-progress">


<div


style={{

width:

`${

dashboard?.placement_percentage

||

0

}%`

}}


/>


</div>



<strong>


{

dashboard?.placement_percentage

||

0

}%


</strong>



</div>





</section>









{/* ===========================
        STUDENT PLACEMENT STATUS
=========================== */}


<div className="placement-status-panel">

<h2>Student Placement Status</h2>

<div className="placement-status-body">

<div className="placement-status-donut-wrap">

<svg viewBox="0 0 100 100" className="placement-status-donut-svg">

<circle cx="50" cy="50" r="40" className="placement-status-donut-track"/>

{
(()=>{

const rows = dashboard?.student_placement_status || [];

const total = rows.reduce((sum,r)=>sum + (r.count||0), 0) || 1;

const colorMap = {

"Placed":"#16a34a",

"In Process":"#2563eb",

"Shortlisted":"#f59e0b",

"Not Placed":"#ef4444",

};

let offset = 0;

return rows.map((row,index)=>{

const pct = (row.count / total) * 100;

const dash = `${pct} ${100 - pct}`;

const el = (

<circle

key={index}

cx="50" cy="50" r="40"

fill="none"

stroke={colorMap[row.label] || "#94a3b8"}

strokeWidth="16"

strokeDasharray={dash}

strokeDashoffset={-offset}

/>

);

offset += pct;

return el;

});

})()
}

</svg>

<div className="placement-status-donut-center">

<strong>{dashboard?.total_students || 0}</strong>

<span>Students</span>

</div>

</div>


<ul className="placement-status-legend">

{
(dashboard?.student_placement_status || []).map((row,index)=>{

const total = (dashboard?.total_students || 0) || 1;

const pct = Math.round((row.count / total) * 100);

const colorMap = {

"Placed":"#16a34a",

"In Process":"#2563eb",

"Shortlisted":"#f59e0b",

"Not Placed":"#ef4444",

};

return(

<li key={index}>

<span className="placement-status-dot" style={{background: colorMap[row.label] || "#94a3b8"}}></span>

{row.label}

<b>{row.count} ({pct}%)</b>

</li>

);

})
}

</ul>

</div>

</div>


{/* ===========================
        RECENT ACTIVITIES
=========================== */}



<div className="placement-sections">







<section className="placement-section">



<div className="section-title">


<h2>

Recent Students

</h2>



<button

onClick={()=>navigate("/placement/students")}

>


View All

<FaArrowRight/>


</button>



</div>









{

dashboard?.recent_students?.length >0



?


dashboard.recent_students.map(

(student)=>(



<div

className="activity-item"

key={student.id}

>


<div>


<h4>


{

student.name

}


</h4>



<p>


{

student.course

||

"Student"

}


</p>


</div>




<FaUserGraduate/>





</div>



)


)



:

<EmptyState icon="folder" title="No students found" message="Students you add will appear here."/>



}





</section>









<section className="placement-section">



<div className="section-title">


<h2>

Recent Companies

</h2>



<button

onClick={()=>navigate("/placement/companies")}

>


View All

<FaArrowRight/>


</button>



</div>









{

dashboard?.recent_companies?.length >0



?


dashboard.recent_companies.map(

(company)=>(



<div

className="activity-item"

key={company.id}

>


<div>


<h4>


{

company.name

}


</h4>



<p>


{

company.industry

||

"Company"

}


</p>


</div>




<FaBuilding/>





</div>



)


)



:

<EmptyState icon="folder" title="No companies found" message="Companies you add will appear here."/>



}





</section>









</div>









{/* ===========================
        UPCOMING DRIVES
=========================== */}



<section className="placement-section full">





<div className="section-title">


<h2>

Upcoming Placement Drives

</h2>



<button

onClick={()=>navigate("/placement/drives")}

>


Manage Drives

<FaArrowRight/>


</button>



</div>









{

dashboard?.upcoming_drives?.length >0



?


dashboard.upcoming_drives.map(

(drive)=>(



<div

className="drive-item"

key={drive.id}

>





<div>


<h4>


{

drive.company_name

}


</h4>



<p>


{

drive.job_title

}


</p>



</div>







<div>


<FaCalendarAlt/>


{

drive.date

}


</div>





</div>



)


)



:

<div className="empty-box">


No upcoming drives


</div>



}





</section>









</div>



);



};



export default PlacementDashboard;