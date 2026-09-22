import React, {
    useEffect,
    useState
} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    FaFileAlt,
    FaUserCheck,
    FaUserTie,
    FaClock,
    FaCheckCircle,
    FaTimesCircle,
    FaMapMarkerAlt,
    FaBriefcase,
    FaSearch,
    FaFileUpload,
    FaUserEdit,
    FaRobot

} from "react-icons/fa";


import {

    getStudentDashboard

} from "../../../api/studentApi";


import {

    getSiteBranding

} from "../../../api/brandingApi";


import "./StudentDashboard.css";





const StudentDashboard = ()=>{


const navigate = useNavigate();


const [dashboard,setDashboard] = useState(null);

const [loading,setLoading] = useState(true);

const [error,setError] = useState("");


const [branding,setBranding] = useState({

dashboard_assistant_image_url:null,

});


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);


const studentName = (()=>{

try{

const stored = JSON.parse(localStorage.getItem("user") || "null");

return stored?.full_name || stored?.username || "Student";

}
catch(e){

return "Student";

}

})();


const greeting = (()=>{

const hour = new Date().getHours();

if(hour < 12) return "Good Morning";

if(hour < 17) return "Good Afternoon";

return "Good Evening";

})();






// =================================
// LOAD DASHBOARD DATA
// =================================


useEffect(()=>{


loadDashboard();


},[]);






const loadDashboard = async()=>{


try{


const response = await getStudentDashboard();


setDashboard(
response.data
);


}
catch(err){


console.log(
"Dashboard Error",
err
);


setError(
"Unable to load dashboard"
);


}
finally{


setLoading(false);


}


};







if(loading){


return(

<div className="dashboard-loading">

Loading Dashboard...

</div>


);


}







return(


<div className="student-dashboard">




{
error &&

<div className="dashboard-error">

{error}

</div>

}




{/* ======================================
GREETING HEADER
====================================== */}


<div className="dashboard-greeting">

<h1>{greeting}, {studentName}! 👋</h1>

<p>Let's continue your career journey</p>

</div>




{/* ======================================
APPLICATION SUMMARY + AI ASSISTANT
====================================== */}



<div className="dashboard-top-row">


<div className="dashboard-stat-grid">



<StatCard

icon={<FaFileAlt/>}

title="Total Applied"

value={
dashboard?.stats?.total_applied || 0
}

/>



<StatCard

icon={<FaUserCheck/>}

title="Shortlisted"

value={
dashboard?.stats?.shortlisted || 0
}

/>




<StatCard

icon={<FaUserTie/>}

title="Interview"

value={
dashboard?.stats?.interview || 0
}

/>





<StatCard

icon={<FaClock/>}

title="Pending"

value={
dashboard?.stats?.pending || 0
}

/>





<StatCard

icon={<FaCheckCircle/>}

title="Offered"

value={
dashboard?.stats?.offered || 0
}

/>




<StatCard

icon={<FaTimesCircle/>}

title="Rejected"

value={
dashboard?.stats?.rejected || 0
}

/>



</div>


<div className="ai-assistant-card">

<h3>AI Career Assistant</h3>

<p>Get personalized job recommendations, improve your resume and prepare for interviews.</p>

<div className="ai-assistant-illustration">

{
branding.dashboard_assistant_image_url ?

<img src={branding.dashboard_assistant_image_url} alt="AI Assistant"/>

:

<div className="ai-assistant-fallback">

<FaRobot/>

</div>
}

</div>

<button

className="ai-assistant-btn"

onClick={()=>{

const chatBtn = document.querySelector(".chatbot-button");

if(chatBtn) chatBtn.click();

}}

>

💬 Chat with AI

</button>

</div>


</div>










<div className="dashboard-charts-row">


<div className="chart-card">

<h4>Application Progress</h4>

<div className="donut-wrap">

<svg viewBox="0 0 100 100" className="donut-svg">

<circle cx="50" cy="50" r="42" className="donut-track"/>

<circle

cx="50" cy="50" r="42"

className="donut-value blue"

strokeDasharray={`${((dashboard?.stats?.total_applied ? (((dashboard.stats.offered||0)+(dashboard.stats.interview||0)+(dashboard.stats.shortlisted||0))/ (dashboard.stats.total_applied||1) *100) : 0)).toFixed(0)} 100`}

/>

</svg>

<div className="donut-center">

<strong>{

dashboard?.stats?.total_applied

? Math.round((((dashboard.stats.offered||0)+(dashboard.stats.interview||0)+(dashboard.stats.shortlisted||0))/(dashboard.stats.total_applied||1))*100)

: 0

}%</strong>

</div>

</div>

<ul className="chart-legend">

<li><span className="dot blue"></span>Applied <b>{dashboard?.stats?.total_applied||0}</b></li>

<li><span className="dot purple"></span>Shortlisted <b>{dashboard?.stats?.shortlisted||0}</b></li>

<li><span className="dot indigo"></span>Interview <b>{dashboard?.stats?.interview||0}</b></li>

<li><span className="dot green"></span>Offered <b>{dashboard?.stats?.offered||0}</b></li>

<li><span className="dot red"></span>Rejected <b>{dashboard?.stats?.rejected||0}</b></li>

</ul>

</div>


<div className="chart-card">

<h4>Skills Match</h4>

<div className="donut-wrap">

<svg viewBox="0 0 100 100" className="donut-svg">

<circle cx="50" cy="50" r="42" className="donut-track"/>

<circle

cx="50" cy="50" r="42"

className="donut-value green"

strokeDasharray={`${dashboard?.skills_match_score || (dashboard?.resume?.resume_score || 0)} 100`}

/>

</svg>

<div className="donut-center">

<strong>{dashboard?.skills_match_score || dashboard?.resume?.resume_score || 0}%</strong>

</div>

</div>

<p className="chart-caption">

{
(dashboard?.skills_match_score || dashboard?.resume?.resume_score || 0) >= 70
? "Good Match! Based on your resume and skills"
: "Improve your resume and skills to boost this score"
}

</p>

<button className="chart-cta" onClick={()=>navigate("/student/resume")}>Improve My Skills</button>

</div>


<div className="chart-card">

<h4>Upcoming Interview</h4>

{
/*
    Reads dashboard.next_interview - real data computed
    from the actual Interview model by StudentDashboardView,
    rather than the old (broken) lookup that checked a
    "recent_applications" field this endpoint never actually
    returns, against a "status==='Interview'" string that
    never matched the real status label either.
*/
}

{
dashboard?.next_interview ?

<div className="upcoming-interview-info">

<div className="upcoming-interview-icon">📅</div>

<div>

<strong>{dashboard.next_interview.job_title}</strong>

<p>{dashboard.next_interview.company}</p>

<p className="chart-caption">

{dashboard.next_interview.date} • {dashboard.next_interview.time} • {dashboard.next_interview.mode}

</p>

</div>

</div>

:

<p className="chart-caption">No upcoming interviews scheduled</p>
}

<button className="chart-cta" onClick={()=>navigate("/student/interviews")}>View Details</button>

</div>


</div>


<div className="dashboard-main-grid">







{/* ======================================
RECOMMENDED JOBS
====================================== */}



<div className="recommended-section">



<div className="section-title">


<h2>

✨ Recommended For You

</h2>


<p>

Based on your skills, resume and activity

</p>


</div>








{

dashboard?.recommended_jobs?.length > 0 ?



dashboard.recommended_jobs.map(

(job)=>(


<div

className="job-recommend-card"

key={job.id}

>




<div className="job-header">


<div className="job-icon">

{
job.title?.charAt(0)
}

</div>



<div>


<h3>

{job.title}

</h3>


<p>

{job.company}

</p>


</div>


</div>






<div className="job-info">


<span>

<FaMapMarkerAlt/>

{job.location || "Remote"}

</span>



<span>

<FaBriefcase/>

{job.job_type || "Full Time"}

</span>


</div>







<div className="skills">


{

job.skills?.map(

(skill,index)=>(


<span key={index}>

+ {skill}

</span>


)

)

}


</div>









{
job.match_reasons && job.match_reasons.length > 0 &&

<div className="match-reasons">

{
job.match_reasons.slice(0,4).map((reason,index)=>(

<span key={index}>{reason}</span>

))
}

</div>

}


<div className="job-footer">


<div className="match-score">


<FaRobot/>

{job.match_score || 0}% Match


</div>




<button onClick={()=>navigate(`/student/jobs/${job.id}`)}>

Apply Now

</button>



</div>





</div>


)


)

:


<div className="empty-box">

No recommended jobs available

</div>



}



</div>












{/* ======================================
RIGHT SIDEBAR
====================================== */}



<div className="dashboard-right">





{/* Recent Applications */}



<div className="dashboard-card">


<div className="card-title">


<h3>

Recent Applications

</h3>


</div>





{

dashboard?.applications?.length > 0 ?



dashboard.applications.map(

(app,index)=>(


<div

className="application-item"

key={index}

>


<h4>

{app.job}

</h4>


<p>

{app.company}

</p>


<span>

{app.status}

</span>


</div>


)


)



:


<div className="empty-box">

No applications yet

<br/>

Browse Jobs

</div>



}



</div>









{/* Skills */}



<div className="dashboard-card">


<div className="card-title">


<h3>

Your Skills

</h3>


</div>





<div className="skill-list">


{

dashboard?.skills?.map(

(skill,index)=>(


<span key={index}>

{skill}

</span>


)


)

}



</div>



<button className="link-btn" onClick={()=>navigate("/student/profile")}>

+ Add Skills

</button>



</div>









{/* Resume AI */}



<div className="dashboard-card resume-ai">


<div className="card-title">


<h3>

AI Resume Score

</h3>


</div>




<div className="resume-score">


<FaRobot/>


<h2>

{

dashboard?.resume?.score || 0

}

/100

</h2>


</div>




{

dashboard?.resume?.missing?.map(

(item,index)=>(


<p key={index}>

⚠ {item}

</p>


)


)

}



</div>










{/* Quick Actions */}



<div className="dashboard-card">


<h3>

Quick Actions

</h3>



<Action

icon={<FaUserEdit/>}

text="Update Profile"

onClick={()=>navigate("/student/profile")}

/>



<Action

icon={<FaSearch/>}

text="Search Jobs"

onClick={()=>navigate("/student/jobs")}

/>



<Action

icon={<FaFileAlt/>}

text="My Applications"

onClick={()=>navigate("/student/applications")}

/>



<Action

icon={<FaFileUpload/>}

text="Upload Resume"

onClick={()=>navigate("/student/resume")}

/>



</div>








</div>






</div>


{/* ======================================
AI RESUME INTELLIGENCE
====================================== */}


<div className="resume-dashboard-card">


<div className="resume-dashboard-header">

<h2>
🤖 Resume Intelligence
</h2>

<p>
AI powered resume analysis and career insights
</p>

</div>




<div className="resume-summary-grid">



<div className="resume-status-box">

<h3>
Resume Status
</h3>


<div className="resume-file">
📄 {dashboard?.resume?.file_name || "No resume uploaded yet"}
</div>


<p>
Last Updated:{" "}
{
dashboard?.resume?.updated_at
?
new Date(dashboard.resume.updated_at).toLocaleDateString(
    undefined,
    { year:"numeric", month:"short", day:"numeric" }
)
:
"—"
}
</p>



<div className="resume-actions">

<button onClick={()=>navigate("/student/resume")}>
View
</button>


</div>


</div>




<div className="resume-score-box">

<h3>
AI Resume Score
</h3>

<div className="score-circle">
{dashboard?.resume?.score || 0}
</div>

<span>
Out of 100
</span>


</div>


</div>






<div className="resume-analysis-grid">



<div>
<h3>
Detected Skills
</h3>


<ul>
{
dashboard?.resume?.skills?.length > 0
?
dashboard.resume.skills.slice(0,6).map(
(skill,index)=>(
<li key={index}>{skill}</li>
)
)
:
<li>No skills detected yet</li>
}
</ul>


</div>





<div>
<h3>
Missing Information
</h3>


<ul className="warning">
{
dashboard?.resume?.missing?.length > 0
?
dashboard.resume.missing.map(
(item,index)=>(
<li key={index}>{item}</li>
)
)
:
<li>Nothing missing — looks complete</li>
}
</ul>


</div>




<div>
<h3>
Recommended Job Categories
</h3>


<ul>
{
dashboard?.resume?.job_categories?.length > 0
?
dashboard.resume.job_categories.map(
(category,index)=>(
<li key={index}>{category}</li>
)
)
:
<li>Upload a resume to get suggestions</li>
}
</ul>


</div>


</div>


</div>




</div>


);



};











// ===============================
// SMALL COMPONENTS
// ===============================


const StatCard =({

icon,

title,

value

})=>(


<div className="stat-card">


<div className="stat-icon">

{icon}

</div>


<div>


<h2>

{value}

</h2>


<p>

{title}

</p>


</div>


</div>


);







const Action=({

icon,

text,

onClick

})=>(


<div className="quick-action" onClick={onClick} style={{cursor:"pointer"}}>


{icon}

<span>

{text}

</span>


</div>


);

export default StudentDashboard;
