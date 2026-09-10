import React, {

    useEffect,

    useState

} from "react";


import {

    getCompanyAnalytics

} from "../../../api/companyApi";


import {

    FaChartBar,

    FaUsers,

    FaFileAlt,

    FaCalendarCheck,

    FaCheckCircle,

    FaListUl,

    FaClock

} from "react-icons/fa";


import {

    ResponsiveContainer,

    LineChart,

    Line,

    XAxis,

    YAxis,

    CartesianGrid,

    Tooltip,

    Legend,

    PieChart,

    Pie,

    Cell

} from "recharts";


import "./Analytics.css";




const TYPE_COLORS = ["#2563eb", "#16a34a", "#7c3aed", "#f59e0b", "#ef4444"];

const DEPT_COLORS = ["#0f766e", "#2563eb", "#7c3aed", "#f59e0b", "#ef4444"];




const CompanyAnalytics = ()=>{


const [analytics,setAnalytics]=useState(null);


const [loading,setLoading]=useState(true);


const [error,setError]=useState("");



useEffect(()=>{


loadAnalytics();


},[]);



const loadAnalytics=async()=>{

try{

const response = await getCompanyAnalytics();

setAnalytics(response.data);

}
catch(err){

console.log(err);

setError("Unable to load analytics");

}
finally{

setLoading(false);

}

};




const timeAgo=(value)=>{

if(!value) return "";

const then = new Date(value).getTime();

const diffMinutes = Math.max(1, Math.round((Date.now()-then)/60000));

if(diffMinutes<60) return `${diffMinutes} min ago`;

const diffHours = Math.round(diffMinutes/60);

if(diffHours<24) return `${diffHours} hour${diffHours>1?"s":""} ago`;

const diffDays = Math.round(diffHours/24);

return `${diffDays} day${diffDays>1?"s":""} ago`;

};




const activityIcon=(type)=>{

if(type==="application") return <FaFileAlt/>;

if(type==="interview") return <FaCalendarCheck/>;

if(type==="job") return <FaListUl/>;

if(type==="shortlist") return <FaCheckCircle/>;

return <FaClock/>;

};




if(loading){

return(

<div className="company-loading">

<div className="spinner-border"></div>

<p>Loading analytics...</p>

</div>

);

}


if(error){

return(

<div className="company-error">{error}</div>

);

}




const stats = analytics?.stats || {};

const trend = analytics?.trend || [];

const byJobType = analytics?.applications_by_job_type || [];

const totalTypeCount = byJobType.reduce((sum,row)=>sum+(row.count||0),0);

const topDepartments = analytics?.top_departments || [];

const maxDeptCount = Math.max(1, ...topDepartments.map(d=>d.count));

const recentActivity = analytics?.recent_activity || [];




return(



<div className="analytics-page">




{/* BANNER */}


<div className="analytics-banner">


<div className="analytics-banner-icon">

<FaChartBar/>

</div>


<div>

<h1>Company Analytics</h1>

<p>Track your recruitment performance and key metrics.</p>

</div>


</div>




{/* STAT CARDS */}


<div className="analytics-stats">


<div className="analytics-stat-card">

<div className="stat-icon green"><FaUsers/></div>

<div>

<p>Total Jobs Posted</p>

<h3>{stats.total_jobs_posted || 0}</h3>

</div>

</div>


<div className="analytics-stat-card">

<div className="stat-icon blue"><FaFileAlt/></div>

<div>

<p>Total Applications</p>

<h3>{stats.total_applications || 0}</h3>

</div>

</div>


<div className="analytics-stat-card">

<div className="stat-icon purple"><FaCalendarCheck/></div>

<div>

<p>Interviews Scheduled</p>

<h3>{stats.interviews_scheduled || 0}</h3>

</div>

</div>


<div className="analytics-stat-card">

<div className="stat-icon orange"><FaCheckCircle/></div>

<div>

<p>Hired Candidates</p>

<h3>{stats.hired_candidates || 0}</h3>

</div>

</div>


</div>




{/* CHARTS ROW */}


<div className="analytics-charts-row">



<div className="analytics-panel analytics-trend-panel">


<div className="analytics-panel-header">

<h2>Job Posting &amp; Applications Trend</h2>

<span>Last 7 Days</span>

</div>


{
trend.length > 0 ?

<ResponsiveContainer width="100%" height={260}>

<LineChart data={trend}>

<CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7"/>

<XAxis dataKey="date" tick={{fontSize:12,fill:"#94a3b8"}} axisLine={false} tickLine={false}/>

<YAxis allowDecimals={false} tick={{fontSize:12,fill:"#94a3b8"}} axisLine={false} tickLine={false}/>

<Tooltip/>

<Legend/>

<Line type="monotone" dataKey="applications" stroke="#0d9488" strokeWidth={3} dot={false} name="Applications"/>

<Line type="monotone" dataKey="job_postings" stroke="#2563eb" strokeWidth={3} dot={false} name="Job Postings"/>

</LineChart>

</ResponsiveContainer>

:

<div className="analytics-empty">No activity in the last 7 days</div>

}


</div>




<div className="analytics-panel analytics-donut-panel">


<div className="analytics-panel-header">

<h2>Applications by Job Type</h2>

</div>


{
totalTypeCount > 0 ?

<div className="analytics-donut-body">


<ResponsiveContainer width="100%" height={180}>

<PieChart>

<Pie

data={byJobType}

dataKey="count"

nameKey="label"

innerRadius={50}

outerRadius={78}

paddingAngle={2}

>

{
byJobType.map((entry,index)=>(

<Cell key={entry.label} fill={TYPE_COLORS[index % TYPE_COLORS.length]}/>

))
}

</Pie>

<Tooltip/>

</PieChart>

</ResponsiveContainer>


<div className="analytics-donut-center">

<strong>{totalTypeCount}</strong>

<span>Total</span>

</div>


<div className="analytics-legend">

{
byJobType.map((row,index)=>(

<div className="analytics-legend-row" key={row.label}>

<span className="legend-dot" style={{background:TYPE_COLORS[index % TYPE_COLORS.length]}}/>

<span className="legend-label">{row.label}</span>

<span className="legend-value">{row.count}</span>

<span className="legend-percent">{row.percent}%</span>

</div>

))
}

</div>


</div>

:

<div className="analytics-empty">No applications yet</div>

}


</div>


</div>




{/* TOP DEPARTMENTS + RECENT ACTIVITY */}


<div className="analytics-charts-row">



<div className="analytics-panel">


<div className="analytics-panel-header">

<h2>Top Departments</h2>

</div>


{
topDepartments.length > 0 ?

<div className="departments-list">

{
topDepartments.map((dept,index)=>(

<div className="department-row" key={dept.department}>

<span className="department-name">{dept.department}</span>

<div className="department-bar-track">

<div

className="department-bar-fill"

style={{

width: `${(dept.count/maxDeptCount)*100}%`,

background: DEPT_COLORS[index % DEPT_COLORS.length],

}}

/>

</div>

<span className="department-count">{dept.count}</span>

</div>

))
}

</div>

:

<div className="analytics-empty">No department data yet. Set a department when posting a job.</div>

}


</div>




<div className="analytics-panel">


<div className="analytics-panel-header">

<h2>Recent Activity</h2>

</div>


{
recentActivity.length > 0 ?

<div className="activity-list">

{
recentActivity.map((item,index)=>(

<div className="activity-row" key={index}>

<div className={"activity-icon " + item.type}>

{activityIcon(item.type)}

</div>

<p>{item.message}</p>

<small>{timeAgo(item.timestamp)}</small>

</div>

))
}

</div>

:

<div className="analytics-empty">No recent activity</div>

}


</div>


</div>




</div>





);



};




export default CompanyAnalytics;
