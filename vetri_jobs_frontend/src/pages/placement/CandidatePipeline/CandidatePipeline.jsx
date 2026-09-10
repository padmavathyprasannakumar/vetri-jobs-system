import React, {

    useEffect,

    useState

} from "react";


import {

    getCandidatePipeline

} from "../../../api/placementApi";


import {

    FaUsers,

    FaFileAlt,

    FaUserFriends,

    FaCheckCircle,

    FaGraduationCap

} from "react-icons/fa";


import "./CandidatePipeline.css";




const STAGES = [

    { key:"applied", label:"Applied", color:"blue" },

    { key:"shortlisted", label:"Shortlisted", color:"yellow" },

    { key:"interview", label:"Interviewing", color:"purple" },

    { key:"selected", label:"Offered", color:"green" },

];




const CandidatePipeline = ()=>{


const [data,setData] = useState(null);

const [loading,setLoading] = useState(true);

const [expandedStage,setExpandedStage] = useState(null);




useEffect(()=>{

getCandidatePipeline()

.then(res=>setData(res.data))

.catch(err=>console.log("PIPELINE LOAD ERROR", err))

.finally(()=>setLoading(false));

},[]);


const stats = data?.stats || {};

const candidates = data?.candidates || [];

const pipelineOverview = data?.pipeline_overview || [];


const grouped = STAGES.reduce((acc,stage)=>{

acc[stage.key] = candidates.filter(c=>(c.status||"").toLowerCase()===stage.key);

return acc;

},{});


const topCandidates = [...candidates]

.filter(c=>c.resume_score)

.sort((a,b)=>(b.resume_score||0)-(a.resume_score||0))

.slice(0,5);




if(loading){

return(

<div className="cp-loading">

<div className="loader"></div>

<p>Loading candidate pipeline...</p>

</div>

);

}




return(


<div className="candidate-pipeline-page">


<div className="cp-header">

<div className="cp-header-icon"><FaUsers/></div>

<div>

<h1>Candidate Pipeline</h1>

<p>Track candidates from application to placement</p>

</div>

</div>


<div className="cp-stat-cards">

<div className="cp-stat-card blue">

<div className="cp-stat-icon"><FaUsers/></div>

<div>

<h3>{stats.total_applicants || 0}</h3>

<p>Total Candidates</p>

</div>

</div>

<div className="cp-stat-card pink">

<div className="cp-stat-icon"><FaFileAlt/></div>

<div>

<h3>{stats.shortlisted || 0}</h3>

<p>Shortlisted</p>

</div>

</div>

<div className="cp-stat-card orange">

<div className="cp-stat-icon"><FaUserFriends/></div>

<div>

<h3>{stats.interviews_scheduled || 0}</h3>

<p>Interviewing</p>

</div>

</div>

<div className="cp-stat-card yellow">

<div className="cp-stat-icon"><FaFileAlt/></div>

<div>

<h3>{stats.final_selected || 0}</h3>

<p>Offered</p>

</div>

</div>

<div className="cp-stat-card green">

<div className="cp-stat-icon"><FaGraduationCap/></div>

<div>

<h3>{stats.joined || 0}</h3>

<p>Placed</p>

</div>

</div>

</div>


<div className="cp-columns">

{
STAGES.map(stage=>(

<div className={"cp-column " + stage.color} key={stage.key}>

<div className="cp-column-header">

<h4>{stage.label}</h4>

<span>{grouped[stage.key]?.length || 0}</span>

</div>

<div className="cp-column-body">

{
(grouped[stage.key] || [])

.slice(0, expandedStage===stage.key ? undefined : 3)

.map(c=>(

<div className="cp-candidate-card" key={c.id}>

<div className="cp-candidate-avatar">{(c.student_name||"?").charAt(0).toUpperCase()}</div>

<div>

<strong>{c.student_name}</strong>

<p>{c.department || "—"}</p>

<p className="cp-candidate-company">{c.applied_job} · {c.company}</p>

</div>

</div>

))
}

{
(grouped[stage.key]?.length || 0) === 0 &&

<p className="cp-column-empty">No candidates</p>
}

</div>

{
(grouped[stage.key]?.length || 0) > 3 &&

<button

className="cp-view-all-btn"

onClick={()=>setExpandedStage(

expandedStage===stage.key ? null : stage.key

)}

>

{
expandedStage===stage.key

? "Show less ↑"

: `View all ${grouped[stage.key]?.length || 0} →`
}

</button>
}

</div>

))
}

</div>


<div className="cp-bottom-row">


<div className="cp-panel">

<h2>Pipeline Analytics</h2>

<div className="cp-bar-chart">

{
pipelineOverview.map(row=>{

const maxVal = Math.max(...pipelineOverview.map(r=>r.count||0), 1);

const heightPct = Math.round(((row.count||0)/maxVal)*100);

return(

<div className="cp-bar-col" key={row.stage}>

<span className="cp-bar-value">{row.count}</span>

<div className="cp-bar-track">

<div className="cp-bar-fill" style={{height: heightPct + "%"}}></div>

</div>

<span className="cp-bar-label">{row.stage}</span>

</div>

);

})
}

</div>

</div>


<div className="cp-panel">

<h2>Conversion Funnel</h2>

<div className="cp-funnel">

{
pipelineOverview.map((row,index)=>{

const maxVal = pipelineOverview[0]?.count || 1;

const widthPct = Math.max(20, Math.round(((row.count||0)/maxVal)*100));

const pct = Math.round(((row.count||0)/maxVal)*100);

return(

<div className="cp-funnel-row" key={row.stage}>

<div className="cp-funnel-bar-wrap">

<div className="cp-funnel-bar" style={{width: widthPct + "%"}}>

{row.count}

</div>

</div>

<span className="cp-funnel-label">{row.stage}</span>

<span className="cp-funnel-pct">{pct}%</span>

</div>

);

})
}

</div>

</div>


<div className="cp-panel">

<h2>Top Candidates</h2>

<table className="cp-top-table">

<thead>

<tr><th>#</th><th>Candidate</th><th>Company</th><th>Stage</th><th>Score</th></tr>

</thead>

<tbody>

{
topCandidates.map((c,index)=>(

<tr key={c.id}>

<td>{index+1}</td>

<td>{c.student_name}</td>

<td>{c.company}</td>

<td><span className="cp-stage-pill">{c.status_display}</span></td>

<td><b>{c.resume_score}</b></td>

</tr>

))
}

{
topCandidates.length===0 &&

<tr><td colSpan="5" className="cp-column-empty">No scored candidates yet</td></tr>
}

</tbody>

</table>

</div>


</div>


</div>


);



};




export default CandidatePipeline;
