import React, {

    useEffect,

    useState

} from "react";


import {

    getCompanyDashboard

} from "../../../api/companyApi";


import {

    useAuth

} from "../../../context/AuthContext";


import {

    FaBriefcase,

    FaUsers,

    FaUserFriends,

    FaCalendarCheck,

    FaArrowRight,

    FaPlus,

    FaSearch,

    FaChartBar,

    FaClipboardList

} from "react-icons/fa";


import {

    useNavigate

} from "react-router-dom";


import {

    ResponsiveContainer,

    LineChart,

    Line,

    XAxis,

    YAxis,

    CartesianGrid,

    Tooltip,

    PieChart,

    Pie,

    Cell

} from "recharts";


import "./CompanyDashboard.css";




// Donut chart colours, in the same order the backend sends
// applications_by_status: Applied / Shortlisted / Interview /
// Hired / Rejected.

const STATUS_COLORS = [

    "#2563eb",

    "#8b5cf6",

    "#f59e0b",

    "#16a34a",

    "#ef4444"

];




const CompanyDashboard = ()=>{


const navigate = useNavigate();


const {

    user

}=useAuth();




const [dashboard,setDashboard]=useState(null);


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");




useEffect(()=>{


loadDashboard();


},[]);




// =====================================
// LOAD COMPANY DASHBOARD
// =====================================


const loadDashboard=async()=>{


try{


const response =

await getCompanyDashboard();



setDashboard(

response.data

);



}

catch(err){


console.log(err);


setError(

err.response?.data?.error

||

"Unable to load company dashboard"

);


}

finally{


setLoading(false);


}



};




const formatTimeAgo = (value)=>{

if(!value) return "";

const then = new Date(value).getTime();

const now = Date.now();

const diffMinutes = Math.max(

1,

Math.round((now - then) / 60000)

);

if(diffMinutes < 60) return `${diffMinutes} min ago`;

const diffHours = Math.round(diffMinutes / 60);

if(diffHours < 24) return `${diffHours} hour${diffHours>1?"s":""} ago`;

const diffDays = Math.round(diffHours / 24);

return `${diffDays} day${diffDays>1?"s":""} ago`;

};




const statusBadgeClass = (status)=>{

const key = (status || "").toLowerCase();

if(key.includes("short")) return "badge-blue";

if(key.includes("interview")) return "badge-orange";

if(key.includes("select") || key.includes("hire")) return "badge-green";

if(key.includes("reject")) return "badge-red";

return "badge-grey";

};




if(loading){


return (


<div className="company-loading">


<div className="spinner-border"></div>


<p>

Loading dashboard...

</p>


</div>


);


}




if(error){


return (


<div className="company-error">

{error}

</div>


);


}




const stats = dashboard?.stats || {};

const overview = dashboard?.applications_overview || [];

const byStatus = (dashboard?.applications_by_status || [])

    .filter(row => row.count > 0);

const totalStatusCount = (dashboard?.applications_by_status || [])

    .reduce((sum, row)=> sum + (row.count || 0), 0);

const recentJobs = dashboard?.recent_jobs || [];

const recentApplicants = dashboard?.recent_applicants || [];

const topCandidates = dashboard?.top_candidates || [];




return (



<div className="company-dashboard">




{/* ==========================
        HEADER
========================== */}


<section className="cd-header">


<div>

<h1>

Company Dashboard <span className="wave">👋</span>

</h1>


<p>

Welcome back, {user?.company_name || user?.username || "there"}!

Here's what's happening with your company.

</p>

</div>


</section>




{/* ==========================
        STAT CARDS
========================== */}


<div className="cd-stats">


<div className="cd-stat-card">

<div className="cd-stat-icon green">

<FaBriefcase/>

</div>

<div>

<p>Active Jobs</p>

<h3>{stats.active_jobs || 0}</h3>

</div>

</div>



<div className="cd-stat-card">

<div className="cd-stat-icon blue">

<FaUsers/>

</div>

<div>

<p>Total Applications</p>

<h3>{stats.total_applications || 0}</h3>

</div>

</div>



<div className="cd-stat-card">

<div className="cd-stat-icon purple">

<FaUserFriends/>

</div>

<div>

<p>Total Candidates</p>

<h3>{stats.total_candidates || 0}</h3>

</div>

</div>



<div className="cd-stat-card">

<div className="cd-stat-icon orange">

<FaCalendarCheck/>

</div>

<div>

<p>Interviews Scheduled</p>

<h3>{stats.interviews_scheduled || 0}</h3>

</div>

</div>


</div>




{/* ==========================
   CHARTS ROW
========================== */}


<div className="cd-charts-row">



<div className="cd-panel cd-chart-panel">

<div className="cd-panel-header">

<h2>Applications Overview</h2>

<span className="cd-panel-sub">Last 30 days</span>

</div>


<div className="cd-line-chart">

{
overview.length > 0 ? (

<ResponsiveContainer width="100%" height={260}>

<LineChart data={overview}>

<CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7"/>

<XAxis

dataKey="date"

interval={Math.ceil(overview.length / 6)}

tick={{fontSize:12, fill:"#94a3b8"}}

axisLine={false}

tickLine={false}

/>

<YAxis

allowDecimals={false}

tick={{fontSize:12, fill:"#94a3b8"}}

axisLine={false}

tickLine={false}

/>

<Tooltip/>

<Line

type="monotone"

dataKey="count"

stroke="#2dd4bf"

strokeWidth={3}

dot={false}

activeDot={{r:5}}

/>

</LineChart>

</ResponsiveContainer>

) : (

<div className="cd-empty">No application activity yet</div>

)
}

</div>

</div>




<div className="cd-panel cd-donut-panel">

<div className="cd-panel-header">

<h2>Applications by Status</h2>

</div>


{
totalStatusCount > 0 ? (

<div className="cd-donut-body">

<ResponsiveContainer width="100%" height={200}>

<PieChart>

<Pie

data={byStatus}

dataKey="count"

nameKey="status"

innerRadius={55}

outerRadius={85}

paddingAngle={2}

>

{
byStatus.map((entry, index)=>(

<Cell

key={entry.status}

fill={STATUS_COLORS[

(dashboard?.applications_by_status || [])

    .findIndex(s=>s.status===entry.status)

]}

/>

))
}

</Pie>

<Tooltip/>

</PieChart>

</ResponsiveContainer>


<div className="cd-donut-legend">

{
(dashboard?.applications_by_status || []).map((row,index)=>(

<div className="cd-legend-row" key={row.status}>

<span

className="cd-legend-dot"

style={{background: STATUS_COLORS[index]}}

/>

<span className="cd-legend-label">{row.status}</span>

<span className="cd-legend-value">

{row.count} (
{
totalStatusCount > 0
? Math.round((row.count/totalStatusCount)*1000)/10
: 0
}
%)

</span>

</div>

))
}


<div className="cd-legend-total">

<span>Total</span>

<strong>{totalStatusCount}</strong>

</div>


</div>

</div>

) : (

<div className="cd-empty">No applications yet</div>

)
}

</div>


</div>




{/* ==========================
   RECENT JOBS + RECENT APPLICANTS
========================== */}


<div className="cd-tables-row">



<div className="cd-panel">

<div className="cd-panel-header">

<h2>Recent Job Postings</h2>

<button onClick={()=>navigate("/company/jobs")}>

View All Jobs <FaArrowRight/>

</button>

</div>


{
recentJobs.length > 0 ? (

<table className="cd-jobs-table">

<thead>

<tr>

<th>Job Title</th>

<th>Applications</th>

<th>Status</th>

<th>Posted On</th>

</tr>

</thead>

<tbody>

{
recentJobs.map(job=>(

<tr key={job.id}>

<td>{job.title}</td>

<td>{job.applications}</td>

<td>

<span className={

"cd-status-pill " +

(job.status === "Active" ? "pill-green" : "pill-grey")

}>

{job.status}

</span>

</td>

<td>

{

job.posted_on

?

new Date(job.posted_on).toLocaleDateString(

undefined,

{year:"numeric", month:"short", day:"numeric"}

)

:

"—"

}

</td>

</tr>

))
}

</tbody>

</table>

) : (

<div className="cd-empty">No jobs posted yet</div>

)
}

</div>




<div className="cd-panel">

<div className="cd-panel-header">

<h2>AI Recommended Candidates</h2>

<button onClick={()=>navigate("/company/candidates")}>

View All <FaArrowRight/>

</button>

</div>


{
topCandidates.length > 0 ? (

<div className="cd-recommended-list">

{
topCandidates.map(cand=>(

<div className="cd-recommended-card" key={cand.application_id}>

<div className="cd-recommended-avatar">

{(cand.name || "?").charAt(0).toUpperCase()}

</div>


<div className="cd-recommended-info">

<h4>{cand.name}</h4>

<p>{cand.job_title}</p>

<div className="cd-recommended-skills">

{
cand.skills.map((skill,index)=>(

<span key={index}>{skill.trim()}</span>

))
}

</div>

</div>


<div className="cd-recommended-side">

<span className="cd-match-badge">{cand.match_score}% Match</span>

<div className="cd-recommended-actions">

<button

className="cd-recommended-view-btn"

onClick={()=>navigate(`/company/candidates?student=${cand.student_id}`)}

>

View Profile

</button>

<button

className="cd-recommended-schedule-btn"

onClick={()=>navigate(`/company/interviews?application=${cand.application_id}`)}

>

Schedule Interview

</button>

</div>

</div>


</div>

))
}

</div>

) : (

<div className="cd-empty">No candidates to recommend yet</div>

)
}

</div>


</div>





{/* ==========================
   QUICK ACTIONS
========================== */}


<div className="cd-panel cd-quick-actions">


<div className="cd-panel-header">

<h2>Quick Actions</h2>

</div>


<div className="cd-actions-grid">


<button onClick={()=>navigate("/company/jobs")}>

<div className="cd-action-icon green"><FaPlus/></div>

<div>

<h4>Post a New Job</h4>

<p>Create a new job posting</p>

</div>

</button>



<button onClick={()=>navigate("/company/candidates")}>

<div className="cd-action-icon blue"><FaSearch/></div>

<div>

<h4>Search Candidates</h4>

<p>Find the right candidates</p>

</div>

</button>



<button onClick={()=>navigate("/company/interviews")}>

<div className="cd-action-icon purple"><FaCalendarCheck/></div>

<div>

<h4>Schedule Interview</h4>

<p>Book interviews with candidates</p>

</div>

</button>



<button onClick={()=>navigate("/company/analytics")}>

<div className="cd-action-icon orange"><FaChartBar/></div>

<div>

<h4>View Analytics</h4>

<p>Check detailed analytics</p>

</div>

</button>



<button onClick={()=>navigate("/company/jobs")}>

<div className="cd-action-icon teal"><FaClipboardList/></div>

<div>

<h4>Manage Jobs</h4>

<p>Edit or pause job postings</p>

</div>

</button>


</div>


</div>




</div>


);


};



export default CompanyDashboard;
