import React, {

    useEffect,

    useState

} from "react";


import {

    getPlacementStudents

} from "../../../api/placementApi";


import {

    FaFileAlt,

    FaSearch,

    FaFilePdf,

    FaUserGraduate,

    FaCheckCircle,

    FaExclamationCircle

} from "react-icons/fa";


import "./ManageResumes.css";




const ManageResumes = ()=>{


const [students,setStudents] = useState([]);

const [loading,setLoading] = useState(true);

const [search,setSearch] = useState("");




useEffect(()=>{

getPlacementStudents()

.then(res=>{

const list = res.data?.results || res.data || [];

setStudents(list);

})

.catch(err=>console.log("RESUMES LOAD ERROR", err))

.finally(()=>setLoading(false));

},[]);




const filtered = students.filter(s=>{

const term = search.toLowerCase();

return (

(s.full_name||"").toLowerCase().includes(term) ||

(s.email||"").toLowerCase().includes(term) ||

(s.course||"").toLowerCase().includes(term)

);

});




const totalStudents = students.length;

const withResume = students.filter(s=>s.resume).length;

const withoutResume = totalStudents - withResume;

const avgScore = withResume > 0

? Math.round(

students.reduce((sum,s)=>sum + (s.resume ? (s.resume_score||0) : 0), 0) / withResume

)

: 0;




return(


<div className="manage-resumes-page">


<div className="mr-header">

<div className="mr-header-icon"><FaFileAlt/></div>

<div>

<h1>Manage Resumes</h1>

<p>Review and access every student's uploaded resume</p>

</div>

</div>


<div className="mr-stats">

<div className="mr-stat-card blue">

<div className="mr-stat-icon"><FaUserGraduate/></div>

<div>

<p>Total Students</p>

<h3>{totalStudents}</h3>

</div>

</div>

<div className="mr-stat-card green">

<div className="mr-stat-icon"><FaCheckCircle/></div>

<div>

<p>Resumes Uploaded</p>

<h3>{withResume}</h3>

</div>

</div>

<div className="mr-stat-card orange">

<div className="mr-stat-icon"><FaExclamationCircle/></div>

<div>

<p>Missing Resumes</p>

<h3>{withoutResume}</h3>

</div>

</div>

<div className="mr-stat-card purple">

<div className="mr-stat-icon"><FaFileAlt/></div>

<div>

<p>Average Resume Score</p>

<h3>{avgScore}%</h3>

</div>

</div>

</div>


<div className="mr-search-bar">

<FaSearch/>

<input

placeholder="Search by name, email, or course..."

value={search}

onChange={(e)=>setSearch(e.target.value)}

/>

</div>


<div className="mr-table-wrap">

<table className="mr-table">

<thead>

<tr>

<th>Student</th>

<th>Course</th>

<th>Verified</th>

<th>Resume Score</th>

<th>Resume</th>

</tr>

</thead>

<tbody>

{
loading ? (

<tr><td colSpan="5" className="mr-empty">Loading students...</td></tr>

) : filtered.length > 0 ? (

filtered.map(student=>(

<tr key={student.id}>

<td>

<div className="mr-student-cell">

<div className="mr-avatar"><FaUserGraduate/></div>

<div>

<strong>{student.full_name}</strong>

<p>{student.email}</p>

</div>

</div>

</td>

<td>{student.course || "—"}</td>

<td>

<span className={"mr-verified-pill " + (student.verified ? "yes" : "no")}>

{student.verified ? "Verified" : "Pending"}

</span>

</td>

<td>

{
student.resume ?

<span className="mr-score-pill">{student.resume_score || 0}%</span>

:

<span className="mr-score-pill dim">—</span>
}

</td>

<td>

{
student.resume ?

<a

href={student.resume}

target="_blank"

rel="noreferrer"

className="mr-view-link"

>

<FaFilePdf/> View / Download

</a>

:

<span className="mr-no-resume">Not uploaded</span>
}

</td>

</tr>

))

) : (

<tr><td colSpan="5" className="mr-empty">No students found</td></tr>

)
}

</tbody>

</table>

</div>


</div>


);


};




export default ManageResumes;
