import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementCompanies,

    verifyCompany

} from "../../../api/placementApi";


import {

    FaSearch,

    FaBuilding,

    FaCheckCircle,

    FaTimesCircle,

    FaGlobe,

    FaUsers,

    FaBriefcase,

    FaHistory,

    FaTimes,

    FaEnvelope,

    FaPhone,

    FaMapMarkerAlt,

    FaUserTie,

    FaIndustry

} from "react-icons/fa";


import "./Companies.css";







const Companies = ()=>{


const [companies,setCompanies]=useState([]);

const [showAddModal,setShowAddModal] = useState(false);

const [newCompany,setNewCompany] = useState({

company_name:"", email:"", password:"", industry:"", website:"",

location:"", description:"", hr_contact_name:"", phone:"", company_type:"",

});

const [creating,setCreating] = useState(false);

const [historyModal,setHistoryModal] = useState(null);

const [loadingHistory,setLoadingHistory] = useState(false);

const [selectedCompany,setSelectedCompany] = useState(null);

const handleViewCompany = (company)=>{

setSelectedCompany(company);

};

const closeCompanyProfile = ()=>{

setSelectedCompany(null);

};


const handleViewHistory = async(companyId)=>{

setLoadingHistory(true);

setHistoryModal({});

try{

const { getCompanyHistory } = await import("../../../api/placementApi");

const response = await getCompanyHistory(companyId);

setHistoryModal(response.data);

}
catch(error){

console.log("HISTORY LOAD ERROR", error);

setHistoryModal(null);

}
finally{

setLoadingHistory(false);

}

};


const [createError,setCreateError] = useState("");


const handleCreateCompany = async(e)=>{

e.preventDefault();

setCreating(true);

setCreateError("");

try{

const { createCompany } = await import("../../../api/placementApi");

await createCompany(newCompany);

setShowAddModal(false);

setNewCompany({ company_name:"", email:"", password:"", industry:"", website:"", location:"", description:"", hr_contact_name:"", phone:"", company_type:"" });

window.location.reload();

}
catch(error){

setCreateError(error.response?.data?.error || "Could not create company. Please check the details and try again.");

}
finally{

setCreating(false);

}

};



const [filteredCompanies,setFilteredCompanies]=useState([]);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [industry,setIndustry]=useState("All");


const [message,setMessage]=useState("");









useEffect(()=>{


loadCompanies();


},[]);









// =================================
// LOAD COMPANIES
// =================================


const loadCompanies=async()=>{


try{


const response =

await getPlacementCompanies();



setCompanies(response.data);


setFilteredCompanies(response.data);



}

catch(error){


console.log(error);


}

finally{


setLoading(false);


}



};











// =================================
// FILTER
// =================================


useEffect(()=>{


let data=[...companies];





if(search){


data=data.filter(company=>


company.company_name

?.toLowerCase()

.includes(

search.toLowerCase()

)



);


}








if(industry !== "All"){


data=data.filter(company=>

company.industry===industry

);


}







setFilteredCompanies(data);



},[search,industry,companies]);











// =================================
// STATUS UPDATE
// =================================


const [verifyingId,setVerifyingId]=useState(null);


const handleVerify=async(id)=>{


try{


setVerifyingId(id);


await verifyCompany(id);



setMessage(

"Company verified"

);


setSelectedCompany(prev=>

prev && prev.id===id

? {...prev, verified:true}

: prev

);



loadCompanies();



}

catch(error){


console.log(error);


}

finally{


setVerifyingId(null);


}



};









if(loading){


return(


<div className="companies-loading">


<div className="spinner-border"></div>


<p>

Loading companies...

</p>


</div>


);


}









return(



<div className="placement-companies">







{/* HEADER */}



<div className="companies-header-banner">

<div>

<h1>Companies</h1>

<p>Manage recruiting companies and industry partners</p>

</div>

<div className="companies-header-quote">

"Great companies create greater opportunities."

</div>

<div className="companies-icon">

<FaBuilding/>

</div>

<button

className="companies-add-btn"

onClick={()=>setShowAddModal(true)}

>

+ Add Company

</button>

</div>


<div className="companies-stat-cards">

<div className="companies-stat-card blue">

<div className="companies-stat-icon"><FaBuilding/></div>

<div>

<p>Total Companies</p>

<h3>{companies.length}</h3>

</div>

</div>

<div className="companies-stat-card green">

<div className="companies-stat-icon"><FaCheckCircle/></div>

<div>

<p>Verified</p>

<h3>{companies.filter(c=>c.verified).length}</h3>

</div>

</div>

<div className="companies-stat-card orange">

<div className="companies-stat-icon"><FaBriefcase/></div>

<div>

<p>Pending Verification</p>

<h3>{companies.filter(c=>!c.verified).length}</h3>

</div>

</div>

<div className="companies-stat-card purple">

<div className="companies-stat-icon"><FaBuilding/></div>

<div>

<p>Industries</p>

<h3>{new Set(companies.map(c=>c.industry).filter(Boolean)).size}</h3>

</div>

</div>

</div>










{

message &&


<div className="companies-message">


{message}


</div>


}









{/* FILTER */}



<div className="company-filter">





<div className="company-search">


<FaSearch/>


<input


placeholder="Search company..."


value={search}


onChange={

e=>setSearch(e.target.value)

}


/>


</div>








<select


value={industry}


onChange={

e=>setIndustry(e.target.value)

}


>


<option>

All

</option>


<option>

IT

</option>


<option>

Finance

</option>


<option>

Healthcare

</option>


<option>

Engineering

</option>



</select>






</div>









{/* COMPANY GRID */}



<div className="companies-table-wrap">

<table className="companies-table">

<thead>

<tr>

<th>#</th>

<th>COMPANY</th>

<th>INDUSTRY</th>

<th>EMPLOYEES</th>

<th>JOBS</th>

<th>STATUS</th>

<th>ACTIONS</th>

</tr>

</thead>

<tbody>

{
filteredCompanies.length > 0 ?

filteredCompanies.map((company,index)=>(

<tr key={company.id}>

<td>{index + 1}</td>

<td>

<div className="companies-table-name-cell">

<div className="companies-table-logo">

{
company.logo ?
<img src={company.logo} alt="logo"/>
:
<FaBuilding/>
}

</div>

<div>

<button
className="companies-table-name-link"
onClick={()=>handleViewCompany(company)}
title="Click to view company details"
>
{company.company_name || "Unnamed Company"}
</button>

{
company.website &&

<p><FaGlobe/> {company.website}</p>
}

</div>

</div>

</td>

<td>{company.industry || "—"}</td>

<td>{company.company_size || "N/A"}</td>

<td>{company.jobs?.length || 0}</td>

<td>

<span className={"companies-table-status-pill " + (company.verified ? "approved" : "pending")}>

{company.verified ? "Verified" : "Pending"}

</span>

</td>

<td>

<div className="companies-table-actions">

<button title="View Details" className="view" onClick={()=>handleViewCompany(company)}>

<FaBuilding/>

</button>

<button title="View History" className="history" onClick={()=>handleViewHistory(company.id)}>

<FaHistory/>

</button>

{
!company.verified &&

<button title="Verify" className="approve" disabled={verifyingId===company.id} onClick={()=>handleVerify(company.id)}>

<FaCheckCircle/>

</button>
}

</div>

</td>

</tr>

))

:

<tr>

<td colSpan="7">

<div className="empty-companies">

<h3>No Companies Found</h3>

<p>Registered companies will appear here.</p>

</div>

</td>

</tr>

}

</tbody>

</table>

</div>

<div className="companies-charts-row">


<div className="companies-chart-panel">

<div className="companies-chart-header">

<h2>Top Hiring Companies</h2>

<span>View All</span>

</div>

<div className="companies-top-list">

{
[...companies]

.sort((a,b)=>(b.jobs?.length||0)-(a.jobs?.length||0))

.slice(0,5)

.map((company,index)=>{

const maxJobs = Math.max(...companies.map(c=>c.jobs?.length||0), 1);

const pct = Math.round(((company.jobs?.length||0)/maxJobs)*100);

return(

<div className="companies-top-row" key={company.id}>

<span className="companies-top-rank">{index+1}</span>

<div className="companies-top-logo">

{
company.logo ?
<img src={company.logo} alt="logo"/>
:
<FaBuilding/>
}

</div>

<div className="companies-top-info">

<strong>{company.company_name}</strong>

<div className="companies-top-bar-track">

<div className="companies-top-bar-fill" style={{width: pct + "%"}}></div>

</div>

</div>

<span className="companies-top-count">{company.jobs?.length||0} jobs</span>

</div>

);

})
}

</div>

</div>


<div className="companies-chart-panel">

<div className="companies-chart-header">

<h2>Companies by Industry</h2>

<span>View All</span>

</div>

<div className="companies-industry-body">

<div className="companies-donut-wrap">

<svg viewBox="0 0 100 100" className="companies-donut-svg">

<circle cx="50" cy="50" r="40" className="companies-donut-track"/>

{
(()=>{

const counts = {};

companies.forEach(c=>{

const key = c.industry || "Other";

counts[key] = (counts[key]||0) + 1;

});

const entries = Object.entries(counts).sort((a,b)=>b[1]-a[1]);

const total = companies.length || 1;

const colors = ["#2563eb","#16a34a","#f59e0b","#7c3aed","#94a3b8"];

let offset = 0;

return entries.map(([label,count],index)=>{

const pct = (count/total)*100;

const dash = pct + " " + (100-pct);

const el = (

<circle

key={label}

cx="50" cy="50" r="40"

fill="none"

stroke={colors[index % colors.length]}

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

<div className="companies-donut-center">

<strong>{companies.length}</strong>

<span>Companies</span>

</div>

</div>

<ul className="companies-industry-legend">

{
(()=>{

const counts = {};

companies.forEach(c=>{

const key = c.industry || "Other";

counts[key] = (counts[key]||0) + 1;

});

const entries = Object.entries(counts).sort((a,b)=>b[1]-a[1]);

const total = companies.length || 1;

const colors = ["#2563eb","#16a34a","#f59e0b","#7c3aed","#94a3b8"];

return entries.map(([label,count],index)=>(

<li key={label}>

<span className="companies-industry-dot" style={{background:colors[index % colors.length]}}></span>

{label}

<b>{Math.round((count/total)*100)}%</b>

</li>

));

})()
}

</ul>

</div>

</div>


</div>














{
showAddModal &&

<div className="company-modal-overlay" onClick={()=>setShowAddModal(false)}>

<div className="company-modal" onClick={(e)=>e.stopPropagation()}>

<h2>Add Company</h2>

<p className="company-modal-sub">Create a company profile and account</p>

{
createError &&

<div className="company-modal-error">{createError}</div>
}

<form onSubmit={handleCreateCompany}>

<label>Company Name *</label>

<input required value={newCompany.company_name} onChange={(e)=>setNewCompany({...newCompany, company_name:e.target.value})} placeholder="Enter company name"/>

<div className="company-modal-row">

<div>

<label>Email *</label>

<input required type="email" value={newCompany.email} onChange={(e)=>setNewCompany({...newCompany, email:e.target.value})} placeholder="company@example.com"/>

</div>

<div>

<label>Password *</label>

<input required type="password" value={newCompany.password} onChange={(e)=>setNewCompany({...newCompany, password:e.target.value})} placeholder="Set a login password"/>

</div>

</div>

<div className="company-modal-row">

<div>

<label>Industry</label>

<input value={newCompany.industry} onChange={(e)=>setNewCompany({...newCompany, industry:e.target.value})} placeholder="e.g. Technology"/>

</div>

<div>

<label>Company Type</label>

<input value={newCompany.company_type} onChange={(e)=>setNewCompany({...newCompany, company_type:e.target.value})} placeholder="e.g. Startup, MNC, SME"/>

</div>

</div>

<div className="company-modal-row">

<div>

<label>Website</label>

<input value={newCompany.website} onChange={(e)=>setNewCompany({...newCompany, website:e.target.value})} placeholder="https://example.com"/>

</div>

<div>

<label>Location</label>

<input value={newCompany.location} onChange={(e)=>setNewCompany({...newCompany, location:e.target.value})} placeholder="City, Country"/>

</div>

</div>

<div className="company-modal-row">

<div>

<label>HR Contact Name</label>

<input value={newCompany.hr_contact_name} onChange={(e)=>setNewCompany({...newCompany, hr_contact_name:e.target.value})} placeholder="Contact person"/>

</div>

<div>

<label>Phone</label>

<input value={newCompany.phone} onChange={(e)=>setNewCompany({...newCompany, phone:e.target.value})} placeholder="Phone number"/>

</div>

</div>

<label>Company Description</label>

<textarea value={newCompany.description} onChange={(e)=>setNewCompany({...newCompany, description:e.target.value})} placeholder="Brief description of the company"/>

<div className="company-modal-actions">

<button type="button" className="company-modal-cancel" onClick={()=>setShowAddModal(false)}>Cancel</button>

<button type="submit" className="company-modal-submit" disabled={creating}>{creating ? "Creating..." : "Create Company"}</button>

</div>

</form>

</div>

</div>
}


{
historyModal &&

<div className="company-modal-overlay" onClick={()=>setHistoryModal(null)}>

<div className="company-modal history-modal" onClick={(e)=>e.stopPropagation()}>

{
loadingHistory ? (

<p>Loading company history...</p>

) : (

<>

<h2>{historyModal.company_name || "Company"} - Hiring History</h2>

<p className="company-modal-sub">{historyModal.industry}</p>

<div className="history-stats-row">

<div className="history-stat">

<strong>{historyModal.total_jobs_posted || 0}</strong>

<span>Jobs Posted</span>

</div>

<div className="history-stat">

<strong>{historyModal.total_applications || 0}</strong>

<span>Applications</span>

</div>

<div className="history-stat">

<strong>{historyModal.students_interviewed || 0}</strong>

<span>Interviewed</span>

</div>

<div className="history-stat">

<strong>{historyModal.students_hired || 0}</strong>

<span>Hired</span>

</div>

</div>

<h4>Previous Placement Drives</h4>

<div className="history-drives-list">

{
(historyModal.previous_drives || []).length > 0 ?

historyModal.previous_drives.map(drive=>(

<div className="history-drive-row" key={drive.id}>

<div>

<strong>{drive.title}</strong>

<p>{drive.drive_date} · {drive.status}</p>

</div>

<div className="history-drive-numbers">

<span>{drive.applied} applied</span>

<span>{drive.selected} selected</span>

</div>

</div>

))

:

<p className="history-empty">No placement drives yet for this company</p>
}

</div>

<h4>Historical Hiring</h4>

<div className="history-hiring-list">

{
(historyModal.historical_hiring || []).length > 0 ?

historyModal.historical_hiring.map((row,index)=>(

<div className="history-hiring-row" key={index}>

<span>{row.month}</span>

<b>{row.hired} hired</b>

</div>

))

:

<p className="history-empty">No hiring history yet</p>
}

</div>

<div className="company-modal-actions">

<button type="button" className="company-modal-cancel" onClick={()=>setHistoryModal(null)}>Close</button>

</div>

</>

)
}

</div>

</div>
}


{
selectedCompany &&

<div
className="company-profile-overlay"
onClick={closeCompanyProfile}
>

<div
className="company-profile-modal"
onClick={(e)=>e.stopPropagation()}
>

<button
className="company-profile-close"
onClick={closeCompanyProfile}
>
<FaTimes/>
</button>

<div className="company-profile-header">

<div className="company-profile-avatar">
{
selectedCompany.logo ?
<img src={selectedCompany.logo} alt="logo"/>
:
<FaBuilding/>
}
</div>

<div>

<h2>{selectedCompany.company_name || "Unnamed Company"}</h2>

{
selectedCompany.tagline &&
<p className="company-profile-tagline">{selectedCompany.tagline}</p>
}

<span className={"companies-table-status-pill " + (selectedCompany.verified ? "approved" : "pending")}>
{selectedCompany.verified ? "Verified" : "Pending Verification"}
</span>

</div>

</div>

{
selectedCompany.description &&

<p className="company-profile-description">{selectedCompany.description}</p>
}

<div className="company-profile-grid">

<div className="company-profile-item">
<FaEnvelope/>
<div>
<span className="company-profile-label">Email</span>
<span>{selectedCompany.contact_email || selectedCompany.user?.email || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaPhone/>
<div>
<span className="company-profile-label">Phone</span>
<span>{selectedCompany.phone || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaIndustry/>
<div>
<span className="company-profile-label">Industry</span>
<span>{selectedCompany.industry || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaBuilding/>
<div>
<span className="company-profile-label">Company Type</span>
<span>{selectedCompany.company_type || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaGlobe/>
<div>
<span className="company-profile-label">Website</span>
<span>{selectedCompany.website || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaUsers/>
<div>
<span className="company-profile-label">Company Size</span>
<span>{selectedCompany.company_size || "N/A"}</span>
</div>
</div>

<div className="company-profile-item">
<FaMapMarkerAlt/>
<div>
<span className="company-profile-label">Address</span>
<span>{selectedCompany.address || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaUserTie/>
<div>
<span className="company-profile-label">HR Contact</span>
<span>{selectedCompany.hr_contact_name || "Not specified"}</span>
</div>
</div>

<div className="company-profile-item">
<FaBriefcase/>
<div>
<span className="company-profile-label">Jobs Posted</span>
<span>{selectedCompany.jobs?.length || 0}</span>
</div>
</div>

</div>

<div className="company-profile-actions">

{
!selectedCompany.verified &&

<button
className="company-profile-verify-btn"
disabled={verifyingId===selectedCompany.id}
onClick={()=>handleVerify(selectedCompany.id)}
>
<FaCheckCircle/>
{verifyingId===selectedCompany.id ? "Verifying..." : "Verify Company"}
</button>
}

<button
className="company-profile-history-btn"
onClick={()=>{ closeCompanyProfile(); handleViewHistory(selectedCompany.id); }}
>
<FaHistory/>
View History
</button>

<button
className="company-profile-close-btn"
onClick={closeCompanyProfile}
>
Close
</button>

</div>

</div>

</div>
}


</div>



);



};



export default Companies;