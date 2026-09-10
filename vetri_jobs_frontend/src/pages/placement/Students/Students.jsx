import React, {

    useEffect,

    useState

} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    getPlacementStudents,

    updateStudentPlacementStatus,

    verifyStudent

} from "../../../api/placementApi";


import {

    FaSearch,

    FaUserGraduate,

    FaFilePdf,

    FaCheckCircle,

    FaTimesCircle,

    FaClock,

    FaTimes,

    FaShieldAlt,

    FaEdit,

    FaEnvelope,

    FaPhone,

    FaGraduationCap

} from "react-icons/fa";


import Avatar from "../../../components/Avatar/Avatar";

import "./Students.css";





const Students = ()=>{


const navigate = useNavigate();


const [students,setStudents]=useState([]);


const [filteredStudents,setFilteredStudents]=useState([]);


const [loading,setLoading]=useState(true);


const [search,setSearch]=useState("");


const [status,setStatus]=useState("All");


const [message,setMessage]=useState("");


const [selectedStudent,setSelectedStudent]=useState(null);


const [verifying,setVerifying]=useState(false);








useEffect(()=>{

    loadStudents();

},[]);








// ================================
// LOAD STUDENTS
// ================================


const loadStudents=async()=>{


try{


const response =

await getPlacementStudents();



setStudents(response.data);


setFilteredStudents(response.data);



}

catch(error){


console.log(error);


}

finally{


setLoading(false);


}



};









// ================================
// FILTER
// ================================


useEffect(()=>{


let data=[...students];




if(search){


data=data.filter(student=>



student.full_name

?.toLowerCase()

.includes(

search.toLowerCase()

)


||


student.email

?.toLowerCase()

.includes(

search.toLowerCase()

)



);



}






if(status!=="All"){


data=data.filter(student=>

student.placement_status===status

);


}





setFilteredStudents(data);



},[search,status,students]);











// ================================
// UPDATE STATUS
// ================================


const updateStatus=async(id,newStatus)=>{


try{


await updateStudentPlacementStatus(

id,

{

placement_status:newStatus

}

);



setMessage(

"Student status updated"

);



loadStudents();



}

catch(error){


console.log(error);


}



};




// ================================
// VIEW / EDIT / VERIFY PROFILE
// ================================


const handleViewProfile=(student)=>{

setSelectedStudent(student);

};



const closeProfile=()=>{

setSelectedStudent(null);

};



const handleEditStudent=(student)=>{

closeProfile();

navigate(`/placement/students/add?id=${student.id}`);

};



const handleVerifyStudent=async(student)=>{


try{


setVerifying(true);


await verifyStudent(student.id);


setMessage("Student verified successfully");


setSelectedStudent(prev=>

prev && prev.id===student.id

? {...prev, verified:true}

: prev

);


loadStudents();


}

catch(error){


console.log(error);


}

finally{


setVerifying(false);


}


};









if(loading){


return(


<div className="students-loading">


<div className="spinner-border"></div>


<p>

Loading students...

</p>


</div>


);


}









return(



<div className="placement-students">







{/* HEADER */}



<div className="students-header-banner">

<div>

<h1>Students</h1>

<p>Manage and track all students</p>

</div>

<div className="students-header-quote">

"Today's learners, tomorrow's leaders."

</div>

<div className="student-header-icon">

<FaUserGraduate/>

</div>

</div>


<div className="students-stat-cards">

<div className="students-stat-card blue">

<div className="students-stat-icon"><FaUserGraduate/></div>

<div>

<p>Total Students</p>

<h3>{students.length}</h3>

</div>

</div>

<div className="students-stat-card green">

<div className="students-stat-icon"><FaCheckCircle/></div>

<div>

<p>Verified Students</p>

<h3>{students.filter(s=>s.verified).length}</h3>

</div>

</div>

<div className="students-stat-card orange">

<div className="students-stat-icon"><FaUserGraduate/></div>

<div>

<p>Placed Students</p>

<h3>{students.filter(s=>(s.placement_status||"").toLowerCase()==="placed").length}</h3>

</div>

</div>

<div className="students-stat-card pink">

<div className="students-stat-icon"><FaTimesCircle/></div>

<div>

<p>Pending Verification</p>

<h3>{students.filter(s=>!s.verified).length}</h3>

</div>

</div>

</div>










{

message &&


<div className="student-message">


{message}


</div>


}









{/* SEARCH */}



<div className="students-filter">





<div className="student-search">


<FaSearch/>


<input


placeholder="Search student..."


value={search}


onChange={

e=>setSearch(e.target.value)

}


/>


</div>








<select


value={status}


onChange={

e=>setStatus(e.target.value)

}


>


<option>

All

</option>


<option>

Placed

</option>


<option>

Shortlisted

</option>


<option>

Looking

</option>


<option>

Not Placed

</option>



</select>








</div>









{/* STUDENTS GRID */}



<div className="students-table-wrap">

<table className="students-table">

<thead>

<tr>

<th><input type="checkbox"/></th>

<th>#</th>

<th>STUDENT</th>

<th>PROGRAM</th>

<th>CGPA</th>

<th>STATUS</th>

<th>PLACEMENT STATUS</th>

<th>ACTIONS</th>

</tr>

</thead>

<tbody>

{
filteredStudents.length > 0 ?

filteredStudents.map((student,index)=>(

<tr key={student.id}>

<td><input type="checkbox"/></td>

<td>{index + 1}</td>

<td>

<div className="students-table-name-cell">

<div className="students-table-avatar"><Avatar name={student.full_name} size={36}/></div>

<div>

<button

className="students-table-name-link"

onClick={()=>handleViewProfile(student)}

title="Click to view profile"

>

{student.full_name}

</button>

<p>{student.email}</p>

</div>

</div>

</td>

<td>{student.course || "—"}</td>

<td>{student.ug_cgpa || "N/A"}</td>

<td>

<span className={"students-table-status-pill " + (student.verified ? "placed" : "looking")}>

{student.verified ? "Verified" : "Pending"}

</span>

</td>

<td>

<span className={"students-table-status-pill " + (student.placement_status||"looking").toLowerCase().replace(" ","-")}>

{student.placement_status || "Looking"}

</span>

</td>

<td>

<div className="students-table-actions">

{
student.resume &&

<a href={student.resume} target="_blank" rel="noreferrer" title="Resume"><FaFilePdf/></a>
}

<button

title="Edit Profile"

onClick={()=>handleEditStudent(student)}

>

<FaEdit/>

</button>

{
!student.verified &&

<button

title="Verify Student"

onClick={()=>handleVerifyStudent(student)}

>

<FaShieldAlt/>

</button>
}

<button

title="Mark Placed"

onClick={()=>updateStatus(student.id,"Placed")}

>

<FaCheckCircle/>

</button>

<button

title="Mark Not Placed"

onClick={()=>updateStatus(student.id,"Not Placed")}

>

<FaTimesCircle/>

</button>

</div>

</td>

</tr>

))

:

<tr>

<td colSpan="8">

<div className="empty-students">

<h3>No Students Found</h3>

<p>Try adjusting your search or filters.</p>

</div>

</td>

</tr>

}

</tbody>

</table>

</div>




{
selectedStudent &&

<div
className="student-profile-overlay"
onClick={closeProfile}
>

<div
className="student-profile-modal"
onClick={(e)=>e.stopPropagation()}
>

<button
className="student-profile-close"
onClick={closeProfile}
>
<FaTimes/>
</button>

<div className="student-profile-header">

<div className="student-profile-avatar"><FaUserGraduate/></div>

<div>

<h2>{selectedStudent.full_name}</h2>

<span className={"students-table-status-pill " + (selectedStudent.verified ? "placed" : "looking")}>

{selectedStudent.verified ? "Verified" : "Pending Verification"}

</span>

</div>

</div>

<div className="student-profile-grid">

<div className="student-profile-item">
<FaEnvelope/>
<div>
<span className="student-profile-label">Email</span>
<span>{selectedStudent.email || "Not specified"}</span>
</div>
</div>

<div className="student-profile-item">
<FaPhone/>
<div>
<span className="student-profile-label">Phone</span>
<span>{selectedStudent.phone || "Not specified"}</span>
</div>
</div>

<div className="student-profile-item">
<FaGraduationCap/>
<div>
<span className="student-profile-label">Program</span>
<span>{selectedStudent.course || "Not specified"}</span>
</div>
</div>

<div className="student-profile-item">
<FaGraduationCap/>
<div>
<span className="student-profile-label">CGPA</span>
<span>{selectedStudent.ug_cgpa || "N/A"}</span>
</div>
</div>

<div className="student-profile-item">
<FaGraduationCap/>
<div>
<span className="student-profile-label">Department</span>
<span>{selectedStudent.department || "Not specified"}</span>
</div>
</div>

<div className="student-profile-item">
<FaGraduationCap/>
<div>
<span className="student-profile-label">Graduation Year</span>
<span>{selectedStudent.graduation_year || "Not specified"}</span>
</div>
</div>

</div>

<div className="student-profile-actions">

<button
className="student-profile-edit-btn"
onClick={()=>handleEditStudent(selectedStudent)}
>
<FaEdit/>
Edit Profile
</button>

{
!selectedStudent.verified &&

<button
className="student-profile-verify-btn"
disabled={verifying}
onClick={()=>handleVerifyStudent(selectedStudent)}
>
<FaShieldAlt/>
{verifying ? "Verifying..." : "Verify Student"}
</button>
}

<button
className="student-profile-close-btn"
onClick={closeProfile}
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



export default Students;