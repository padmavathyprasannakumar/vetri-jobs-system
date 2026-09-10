import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementReports,

    scheduleAutomatedReport

} from "../../../api/placementApi";


import {

    FaChartLine,

    FaUserGraduate,

    FaBuilding,

    FaBriefcase,

    FaFileAlt,

    FaBullseye,

    FaDownload

} from "react-icons/fa";


import "./Reports.css";




const INDUSTRY_COLORS = ["#2563eb","#16a34a","#f59e0b","#7c3aed","#dc2626","#0891b2","#94a3b8"];

const STATUS_COLORS = ["#2563eb","#16a34a","#f59e0b","#dc2626","#94a3b8"];




const Reports = ()=>{


const [reports,setReports] = useState(null);

const [loading,setLoading] = useState(true);

const [showScheduleModal,setShowScheduleModal] = useState(false);

const [scheduleEmail,setScheduleEmail] = useState("");

const [scheduleFrequency,setScheduleFrequency] = useState("weekly");

const [scheduling,setScheduling] = useState(false);

const [scheduleMessage,setScheduleMessage] = useState("");




useEffect(()=>{

getPlacementReports()

.then(res=>setReports(res.data))

.catch(err=>console.log("REPORTS LOAD ERROR", err))

.finally(()=>setLoading(false));

},[]);


if(loading){

return(

<div className="reports-loading">

<div className="loader"></div>

<p>Loading reports...</p>

</div>

);

}


const statusBreakdown = reports?.status_breakdown || [];

const industryBreakdown = reports?.placement_by_industry || [];

const trend = reports?.placement_trend || [];

const companyReports = reports?.company_reports || [];

const recentActivity = reports?.recent_activity || [];


const statusTotal = statusBreakdown.reduce((sum,r)=>sum+(r.count||0),0) || 1;

const industryTotal = industryBreakdown.reduce((sum,r)=>sum+(r.count||0),0) || 1;

const trendMax = Math.max(...trend.map(t=>Math.max(t.applications||0,t.placed||0)), 1);


const escapeCsv = (val)=>{

const str = String(val ?? "");

if(str.includes(",") || str.includes("\"") || str.includes("\n")){

return `"${str.replace(/"/g,'""')}"`;

}

return str;

};


const handleExportReport = ()=>{

const lines = [];

lines.push("Vetri Jobs - Placement Report");

lines.push(`Generated on,${new Date().toLocaleString()}`);

lines.push("");

lines.push("SUMMARY");

lines.push("Metric,Value");

lines.push(`Total Students,${reports?.total_students || 0}`);

lines.push(`Companies,${companyReports.length}`);

lines.push(`Total Jobs,${reports?.total_jobs || 0}`);

lines.push(`Total Applications,${reports?.total_applications || 0}`);

lines.push(`Placement Rate,${reports?.placement_rate || 0}%`);

lines.push("");

lines.push("COMPANY REPORTS");

lines.push("Company,Industry,Hires,Applications");

companyReports.forEach(c=>{

lines.push([

escapeCsv(c.company_name || c.name || ""),

escapeCsv(c.industry || ""),

escapeCsv(c.hires || 0),

escapeCsv(c.applications || 0),

].join(","));

});

lines.push("");

lines.push("RECENT ACTIVITY");

lines.push("Date,Student,Company,Status");

recentActivity.forEach(a=>{

lines.push([

escapeCsv(a.date || ""),

escapeCsv(a.student_name || a.student || ""),

escapeCsv(a.company_name || a.company || ""),

escapeCsv(a.status || ""),

].join(","));

});

const csvContent = lines.join("\n");

const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

const url = URL.createObjectURL(blob);

const link = document.createElement("a");

link.href = url;

link.download = `vetri-jobs-placement-report-${new Date().toISOString().split("T")[0]}.csv`;

document.body.appendChild(link);

link.click();

document.body.removeChild(link);

URL.revokeObjectURL(url);

};


const handleScheduleReport = async(e)=>{

e.preventDefault();

if(!scheduleEmail.trim()){

setScheduleMessage("Please enter an email address");

return;

}

setScheduling(true);

setScheduleMessage("");

try{

await scheduleAutomatedReport({

email: scheduleEmail,

frequency: scheduleFrequency,

});

setScheduleMessage("Automated report scheduled successfully");

setTimeout(()=>{

setShowScheduleModal(false);

setScheduleMessage("");

},1500);

}

catch(error){

console.log("SCHEDULE REPORT ERROR", error);

setScheduleMessage(

error.response?.data?.error ||

"Could not schedule report. Please try again."

);

}

finally{

setScheduling(false);

}

};




return(


<div className="reports-page">


<div className="reports-header">

<div className="reports-header-icon"><FaChartLine/></div>

<div>

<h1>Reports &amp; Analytics</h1>


</div>

<button className="reports-export-btn" onClick={handleExportReport}>

<FaDownload/> Export Report

</button>

</div>


<div className="reports-stat-cards">

<div className="reports-stat-card blue">

<div className="reports-stat-icon"><FaUserGraduate/></div>

<div>

<p>Total Students</p>

<h3>{reports?.total_students || 0}</h3>

</div>

</div>

<div className="reports-stat-card green">

<div className="reports-stat-icon"><FaBuilding/></div>

<div>

<p>Companies</p>

<h3>{companyReports.length}</h3>

</div>

</div>

<div className="reports-stat-card orange">

<div className="reports-stat-icon"><FaBriefcase/></div>

<div>

<p>Total Jobs</p>

<h3>{reports?.total_jobs || 0}</h3>

</div>

</div>

<div className="reports-stat-card purple">

<div className="reports-stat-icon"><FaFileAlt/></div>

<div>

<p>Total Applications</p>

<h3>{reports?.total_applications || 0}</h3>

</div>

</div>

<div className="reports-stat-card pink">

<div className="reports-stat-icon"><FaBullseye/></div>

<div>

<p>Placement Rate</p>

<h3>{reports?.placement_percentage || 0}%</h3>

</div>

</div>

</div>


<div className="reports-charts-row">


<div className="reports-panel">

<h2>Placement Trend</h2>

<div className="reports-trend-chart">

<svg viewBox="0 0 300 140" preserveAspectRatio="none" className="reports-trend-svg">

<polyline

fill="none"

stroke="#2563eb"

strokeWidth="2"

points={trend.map((t,i)=>(i/(Math.max(trend.length-1,1)))*300 + "," + (140-((t.applications||0)/trendMax)*130)).join(" ")}

/>

<polyline

fill="none"

stroke="#7c3aed"

strokeWidth="2"

points={trend.map((t,i)=>(i/(Math.max(trend.length-1,1)))*300 + "," + (140-((t.placed||0)/trendMax)*130)).join(" ")}

/>

</svg>

<div className="reports-trend-labels">

{
trend.map((t,i)=>(

<span key={i}>{t.month}</span>

))
}

</div>

<div className="reports-trend-legend">

<span><i style={{background:"#2563eb"}}></i> Applications</span>

<span><i style={{background:"#7c3aed"}}></i> Placed Students</span>

</div>

</div>

</div>


<div className="reports-panel">

<h2>Placement by Industry</h2>

<div className="reports-industry-body">

<div className="reports-donut-wrap">

<svg viewBox="0 0 100 100" className="reports-donut-svg">

<circle cx="50" cy="50" r="40" className="reports-donut-track"/>

{
(()=>{

let offset = 0;

return industryBreakdown.map((row,index)=>{

const pct = (row.count/industryTotal)*100;

const dash = pct + " " + (100-pct);

const el = (

<circle

key={row.industry}

cx="50" cy="50" r="40"

fill="none"

stroke={INDUSTRY_COLORS[index % INDUSTRY_COLORS.length]}

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

<div className="reports-donut-center">

<strong>{companyReports.length}</strong>

<span>Companies</span>

</div>

</div>

<ul className="reports-legend-list">

{
industryBreakdown.map((row,index)=>(

<li key={row.industry}>

<span className="reports-legend-dot" style={{background:INDUSTRY_COLORS[index % INDUSTRY_COLORS.length]}}></span>

{row.industry}

<b>{row.count} ({Math.round((row.count/industryTotal)*100)}%)</b>

</li>

))
}

</ul>

</div>

</div>


<div className="reports-panel">

<h2>Application Status</h2>

<div className="reports-industry-body">

<div className="reports-donut-wrap">

<svg viewBox="0 0 100 100" className="reports-donut-svg">

<circle cx="50" cy="50" r="40" className="reports-donut-track"/>

{
(()=>{

let offset = 0;

return statusBreakdown.map((row,index)=>{

const pct = (row.count/statusTotal)*100;

const dash = pct + " " + (100-pct);

const el = (

<circle

key={row.status}

cx="50" cy="50" r="40"

fill="none"

stroke={STATUS_COLORS[index % STATUS_COLORS.length]}

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

<div className="reports-donut-center">

<strong>{reports?.total_applications || 0}</strong>

<span>Applications</span>

</div>

</div>

<ul className="reports-legend-list">

{
statusBreakdown.map((row,index)=>(

<li key={row.status}>

<span className="reports-legend-dot" style={{background:STATUS_COLORS[index % STATUS_COLORS.length]}}></span>

{row.status}

<b>{row.count} ({Math.round((row.count/statusTotal)*100)}%)</b>

</li>

))
}

</ul>

</div>

</div>


</div>


<div className="reports-tables-row">


<div className="reports-panel">

<div className="reports-panel-header">

<h2>Top Recruiting Companies</h2>

<span>View All</span>

</div>

<table className="reports-table">

<thead>

<tr><th>#</th><th>Company</th><th>Industry</th><th>Hires</th><th>Applications</th></tr>

</thead>

<tbody>

{
companyReports.slice(0,5).map((c,index)=>(

<tr key={c.id}>

<td>{index+1}</td>

<td>{c.name}</td>

<td>{c.industry || "—"}</td>

<td>{c.hired}</td>

<td>{c.applications || 0}</td>

</tr>

))
}

</tbody>

</table>

</div>


<div className="reports-panel">

<div className="reports-panel-header">

<h2>Recent Placement Activity</h2>

<span>View All</span>

</div>

<table className="reports-table">

<thead>

<tr><th>Date</th><th>Student</th><th>Company</th><th>Status</th></tr>

</thead>

<tbody>

{
recentActivity.map(item=>(

<tr key={item.id}>

<td>{item.date ? new Date(item.date).toLocaleDateString(undefined,{day:"2-digit",month:"short",year:"numeric"}) : "—"}</td>

<td>{item.student_name}</td>

<td>{item.company_name}</td>

<td><span className={"reports-status-pill " + (item.status||"").toLowerCase()}>{item.status}</span></td>

</tr>

))
}

</tbody>

</table>

</div>


</div>


<div className="reports-footer-banner">

<div>

<FaChartLine/>

<div>

<h3>Data-Driven Placements, Brighter Futures</h3>

<p>Use insights to improve engagement, track progress, and achieve higher placement success.</p>

</div>

</div>

<button onClick={()=>setShowScheduleModal(true)}>Schedule Automated Reports</button>

</div>


{
showScheduleModal &&

<div className="schedule-report-overlay" onClick={()=>setShowScheduleModal(false)}>

<div className="schedule-report-modal" onClick={(e)=>e.stopPropagation()}>

<h2>Schedule Automated Reports</h2>

<p>Get a placement report summary emailed to you automatically.</p>

<form onSubmit={handleScheduleReport}>

<label>Email Address</label>

<input

type="email"

placeholder="you@example.com"

value={scheduleEmail}

onChange={(e)=>setScheduleEmail(e.target.value)}

required

/>

<label>Frequency</label>

<select

value={scheduleFrequency}

onChange={(e)=>setScheduleFrequency(e.target.value)}

>

<option value="weekly">Weekly</option>

<option value="monthly">Monthly</option>

</select>

{
scheduleMessage &&

<div className="schedule-report-message">{scheduleMessage}</div>
}

<div className="schedule-report-actions">

<button type="button" onClick={()=>setShowScheduleModal(false)}>Cancel</button>

<button type="submit" className="schedule-report-submit" disabled={scheduling}>

{scheduling ? "Scheduling..." : "Schedule"}

</button>

</div>

</form>

</div>

</div>
}


</div>


);



};




export default Reports;
