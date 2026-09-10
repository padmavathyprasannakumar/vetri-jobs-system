import React, {

    useEffect,

    useState

} from "react";


import {


    getPlacementDrives,

    createPlacementDrive,

    updatePlacementDrive,

    deletePlacementDrive,

    updateDriveStatus


} from "../../../api/placementApi";


import {


    FaPlus,

    FaSearch,

    FaBriefcase,

    FaBuilding,

    FaCalendarAlt,

    FaClock,

    FaUsers,

    FaEdit,

    FaTrash,

    FaCheckCircle,

    FaTimesCircle


} from "react-icons/fa";


import "./Drives.css";





const Drives = ()=>{



const initialForm={


company_name:"",

job_title:"",

drive_date:"",

eligibility:"",

description:""


};





const [drives,setDrives]=useState([]);


const [filteredDrives,setFilteredDrives]=useState([]);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [showForm,setShowForm]=useState(false);


const [editId,setEditId]=useState(null);


const [message,setMessage]=useState("");



const [form,setForm]=useState(initialForm);









useEffect(()=>{


loadDrives();


},[]);









// =================================
// LOAD DRIVES
// =================================


const loadDrives=async()=>{


try{


const response=

await getPlacementDrives();



setDrives(response.data);


setFilteredDrives(response.data);



}

catch(error){


console.log(error);


}

finally{


setLoading(false);


}



};









// =================================
// SEARCH
// =================================


useEffect(()=>{


let data=[...drives];



if(search){


data=data.filter(drive=>



drive.company_name

?.toLowerCase()

.includes(

search.toLowerCase()

)


||


drive.job_title

?.toLowerCase()

.includes(

search.toLowerCase()

)



);


}



setFilteredDrives(data);



},[search,drives]);









// =================================
// INPUT
// =================================


const handleChange=(e)=>{


setForm({


...form,


[e.target.name]:

e.target.value



});


};









// =================================
// CREATE / UPDATE
// =================================


const handleSubmit=async(e)=>{


e.preventDefault();


if(!editId && form.drive_date){

const todayStr = new Date().toISOString().split("T")[0];

if(form.drive_date < todayStr){

setMessage("Drive date cannot be in the past");

return;

}

}


try{



if(editId){



await updatePlacementDrive(

editId,

form

);



setMessage(

"Drive updated successfully"

);



}

else{



await createPlacementDrive(

form

);



setMessage(

"Drive created successfully"

);



}




setForm(initialForm);


setEditId(null);


setShowForm(false);



loadDrives();



}

catch(error){


console.log(error);


}



};









// =================================
// EDIT
// =================================


const handleEdit=(drive)=>{


setForm({


company_name:

drive.company_name || "",


job_title:

drive.job_title || "",


drive_date:

drive.drive_date || "",


eligibility:

drive.eligibility || "",


description:

drive.description || ""


});



setEditId(drive.id);


setShowForm(true);



};









// =================================
// DELETE
// =================================


const handleDelete=async(id)=>{


if(!window.confirm(

"Delete this placement drive?"

))

return;



try{


await deletePlacementDrive(id);



setMessage(

"Drive deleted successfully"

);



loadDrives();



}

catch(error){


console.log(error);


}



};









// =================================
// STATUS
// =================================


const changeStatus=async(id,status)=>{


try{


await updateDriveStatus(

id,

{

status

}

);



loadDrives();



}

catch(error){


console.log(error);


}



};









if(loading){


return(


<div className="drives-loading">


<div className="spinner-border"></div>


<p>

Loading drives...

</p>


</div>


);


}









return(



<div className="placement-drives">







{/* HEADER */}



<div className="drives-header-banner">

<div>

<h1>Placement Drives</h1>

<p>Manage and track campus recruitment drives</p>

</div>

<div className="drives-header-quote">

"Connecting Talent with Opportunities."

</div>

<button

className="drives-create-btn"

onClick={()=>setShowForm(true)}

>

<FaPlus/> Create Drive

</button>

</div>


<div className="drives-stat-cards">

<div className="drives-stat-card blue">

<div className="drives-stat-icon"><FaCalendarAlt/></div>

<div>

<p>Total Drives</p>

<h3>{drives.length}</h3>

</div>

</div>

<div className="drives-stat-card green">

<div className="drives-stat-icon"><FaClock/></div>

<div>

<p>Upcoming</p>

<h3>{drives.filter(d=>(d.status||"").toLowerCase()==="upcoming").length}</h3>

</div>

</div>

<div className="drives-stat-card orange">

<div className="drives-stat-icon"><FaUsers/></div>

<div>

<p>Ongoing</p>

<h3>{drives.filter(d=>(d.status||"").toLowerCase()==="ongoing").length}</h3>

</div>

</div>

<div className="drives-stat-card purple">

<div className="drives-stat-icon"><FaCheckCircle/></div>

<div>

<p>Completed</p>

<h3>{drives.filter(d=>(d.status||"").toLowerCase()==="completed").length}</h3>

</div>

</div>

</div>










{

message &&


<div className="drive-message">


{message}


</div>


}









{/* SEARCH */}



<div className="drive-search">


<FaSearch/>


<input


placeholder="Search company or job..."


value={search}


onChange={

e=>setSearch(e.target.value)

}


/>


</div>









{/* FORM */}



{

showForm &&



<div className="drive-form-card">


<h2>


{

editId

?

"Edit Drive"

:

"Create Drive"

}


</h2>




<form onSubmit={handleSubmit}>


<input


name="company_name"


placeholder="Company Name"


value={form.company_name}


onChange={handleChange}


/>





<input


name="job_title"


placeholder="Job Position"


value={form.job_title}


onChange={handleChange}


/>





<input


type="date"


name="drive_date"


value={form.drive_date}


min={!editId ? new Date().toISOString().split("T")[0] : undefined}


onChange={handleChange}


/>





<input


name="eligibility"


placeholder="Eligibility (CGPA, Course)"


value={form.eligibility}


onChange={handleChange}


/>





<textarea


name="description"


placeholder="Drive Description"


value={form.description}


onChange={handleChange}


/>






<div className="drive-form-buttons">


<button type="submit">


Save Drive


</button>




<button


type="button"


onClick={()=>setShowForm(false)}


>


Cancel


</button>



</div>



</form>



</div>



}









{/* DRIVE CARDS */}



<div className="drives-table-wrap">

<table className="drives-table">

<thead>

<tr>

<th>#</th>

<th>DRIVE NAME</th>

<th>COMPANY</th>

<th>DATE</th>

<th>ELIGIBILITY</th>

<th>STATUS</th>

<th>ACTIONS</th>

</tr>

</thead>

<tbody>

{
filteredDrives.length > 0 ?

filteredDrives.map((drive,index)=>(

<tr key={drive.id}>

<td>{index + 1}</td>

<td>

<div className="drives-table-name-cell">

<span className="drives-table-icon"><FaBriefcase/></span>

{drive.job_title}

</div>

</td>

<td>

<div className="drives-table-company-cell">

<FaBuilding/> {drive.company_name}

</div>

</td>

<td><FaCalendarAlt/> {drive.drive_date}</td>

<td>{drive.eligibility || "N/A"}</td>

<td>

<span className={"drives-table-status-pill " + (drive.status||"upcoming").toLowerCase()}>

{drive.status || "Upcoming"}

</span>

</td>

<td>

<div className="drives-table-actions">

<button title="Edit" onClick={()=>handleEdit(drive)}><FaEdit/></button>

<button title="Delete" onClick={()=>handleDelete(drive.id)}><FaTrash/></button>

<button title="Mark Upcoming" onClick={()=>changeStatus(drive.id,"upcoming")}><FaClock/></button>

<button title="Mark Ongoing" onClick={()=>changeStatus(drive.id,"ongoing")}><FaUsers/></button>

<button title="Mark Completed" onClick={()=>changeStatus(drive.id,"completed")}><FaCheckCircle/></button>

<button title="Cancel Drive" onClick={()=>changeStatus(drive.id,"cancelled")}><FaTimesCircle/></button>

</div>

</td>

</tr>

))

:

<tr>

<td colSpan="7">

<div className="empty-drives">

<h3>No Placement Drives</h3>

<p>Create a drive to start recruitment.</p>

</div>

</td>

</tr>

}

</tbody>

</table>

</div>

<div className="drives-charts-row">


<div className="drives-chart-panel">

<div className="drives-chart-header">

<h2>Upcoming Drives</h2>

<span>View All</span>

</div>

<div className="drives-upcoming-list">

{
drives

.filter(d=>(d.status||"").toLowerCase()==="upcoming")

.slice(0,3)

.map(drive=>(

<div className="drives-upcoming-row" key={drive.id}>

<div className="drives-upcoming-date">

<span>{drive.drive_date ? drive.drive_date.split("-")[2] || drive.drive_date : "--"}</span>

</div>

<div className="drives-upcoming-info">

<strong>{drive.job_title}</strong>

<p>{drive.company_name}</p>

</div>

</div>

))
}

{
drives.filter(d=>(d.status||"").toLowerCase()==="upcoming").length===0 &&

<p className="drives-upcoming-empty">No upcoming drives</p>
}

</div>

</div>


<div className="drives-chart-panel">

<div className="drives-chart-header">

<h2>Drive Analytics</h2>

<span>This Month</span>

</div>

<div className="drives-bar-chart">

{
drives.slice(0,6).map(drive=>{

const registered = drive.registered_count || drive.applied_count || 0;

const maxVal = Math.max(...drives.map(d=>d.registered_count||d.applied_count||0), 1);

const heightPct = Math.round((registered/maxVal)*100);

return(

<div className="drives-bar-col" key={drive.id}>

<div className="drives-bar-track">

<div className="drives-bar-fill" style={{height: heightPct + "%"}}></div>

</div>

<span>{(drive.job_title||"").slice(0,6)}</span>

</div>

);

})
}

{
drives.length===0 &&

<p className="drives-upcoming-empty">No data available</p>
}

</div>

</div>


<div className="drives-chart-panel">

<div className="drives-chart-header">

<h2>Drive Status</h2>

</div>

<div className="drives-status-body">

<div className="drives-status-donut-wrap">

<svg viewBox="0 0 100 100" className="drives-status-donut-svg">

<circle cx="50" cy="50" r="40" className="drives-status-donut-track"/>

{
(()=>{

const counts = { Upcoming:0, Ongoing:0, Completed:0 };

drives.forEach(d=>{

const s = (d.status||"").toLowerCase();

if(s==="upcoming") counts.Upcoming++;

else if(s==="ongoing") counts.Ongoing++;

else if(s==="completed" || s==="closed") counts.Completed++;

});

const colors = { Upcoming:"#2563eb", Ongoing:"#f59e0b", Completed:"#16a34a" };

const total = drives.length || 1;

let offset = 0;

return Object.entries(counts).map(([label,count])=>{

const pct = (count/total)*100;

const dash = pct + " " + (100-pct);

const el = (

<circle

key={label}

cx="50" cy="50" r="40"

fill="none"

stroke={colors[label]}

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

<div className="drives-status-donut-center">

<strong>{drives.length}</strong>

<span>Drives</span>

</div>

</div>

<ul className="drives-status-legend">

<li><span className="drives-status-dot" style={{background:"#2563eb"}}></span> Upcoming <b>{drives.filter(d=>(d.status||"").toLowerCase()==="upcoming").length}</b></li>

<li><span className="drives-status-dot" style={{background:"#f59e0b"}}></span> Ongoing <b>{drives.filter(d=>(d.status||"").toLowerCase()==="ongoing").length}</b></li>

<li><span className="drives-status-dot" style={{background:"#16a34a"}}></span> Completed <b>{drives.filter(d=>{const s=(d.status||"").toLowerCase(); return s==="completed"||s==="closed";}).length}</b></li>

</ul>

</div>

</div>


</div>










</div>


);



};



export default Drives;