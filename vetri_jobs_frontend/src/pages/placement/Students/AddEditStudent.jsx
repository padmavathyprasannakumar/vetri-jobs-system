import React, {

    useState,

    useRef,

    useEffect

} from "react";


import {

    useNavigate,

    useSearchParams

} from "react-router-dom";


import {

    getPlacementStudents,

    updatePlacementStudent,

    createPlacementStudent,

    verifyStudent

} from "../../../api/placementApi";


import {

    FaUserPlus,

    FaCamera,

    FaMagic,

    FaLightbulb,

    FaCheck,

    FaFilePdf,

    FaArrowRight,

    FaShieldAlt

} from "react-icons/fa";


import "./AddEditStudent.css";




const TABS = [

    "Personal Information",

    "Academic Details",

    "Skills & Interests",

    "Placement Preferences",

    "Documents",

    "Additional Info",

];




const AddEditStudent = ()=>{


const navigate = useNavigate();

const [searchParams] = useSearchParams();

const editingId = searchParams.get("id");

const [isEditMode] = useState(!!editingId);


const [isVerified,setIsVerified] = useState(false);


useEffect(()=>{

if(!editingId) return;

getPlacementStudents()

.then(res=>{

const list = res.data?.results || res.data || [];

const match = list.find(s=>String(s.id)===String(editingId));

if(match){

setForm(prev=>({

...prev,

full_name: match.full_name || prev.full_name,

email: match.email || prev.email,

phone: match.phone || prev.phone,

student_id: match.student_id || prev.student_id,

gender: match.gender || prev.gender,

address1: match.location || prev.address1,

}));

setIsVerified(!!match.verified);

}

})

.catch(err=>console.log("LOAD STUDENT ERROR", err));

// eslint-disable-next-line react-hooks/exhaustive-deps

},[editingId]);



const [activeTab,setActiveTab] = useState(0);


const [form,setForm] = useState({

full_name:"",

email:"",

phone:"",

student_id:"",

gender:"",

address1:"",

address2:"",

city:"",

state:"",

postcode:"",

country:"India",

emergency_name:"",

emergency_phone:"",

emergency_relationship:"",

});


const photoInputRef = useRef(null);

const [photoPreview,setPhotoPreview] = useState(null);

const [photoError,setPhotoError] = useState("");


const handlePhotoSelected = (e)=>{

const file = e.target.files[0];

if(!file) return;

if(!["image/jpeg","image/png"].includes(file.type)){

setPhotoError("Please upload a JPG or PNG image.");

return;

}

if(file.size > 2 * 1024 * 1024){

setPhotoError("Image must be under 2MB.");

return;

}

setPhotoError("");

const reader = new FileReader();

reader.onload = ()=>setPhotoPreview(reader.result);

reader.readAsDataURL(file);

};


const resumeInputRef = useRef(null);

const [resumeFile,setResumeFile] = useState(null);

const [resumeError,setResumeError] = useState("");


const handleResumeSelected = (e)=>{

const file = e.target.files[0];

if(!file) return;

const allowed = [".pdf",".doc",".docx"];

const isAllowed = allowed.some(ext=>file.name.toLowerCase().endsWith(ext));

if(!isAllowed){

setResumeError("Please upload a PDF, DOC or DOCX file.");

return;

}

if(file.size > 5 * 1024 * 1024){

setResumeError("File must be under 5MB.");

return;

}

setResumeError("");

setResumeFile(file);

};





const handleChange = (e)=>{

setForm({ ...form, [e.target.name]: e.target.value });

};




const filledCount = Object.values(form).filter(v=>v && v.trim()).length;

const totalFields = Object.keys(form).length;

const completionPct = Math.round((filledCount / totalFields) * 100);




const goNext = ()=>{

if(activeTab < TABS.length - 1){

setActiveTab(activeTab + 1);

}

};




const [saving,setSaving] = useState(false);

const [saveError,setSaveError] = useState("");

const [verifying,setVerifying] = useState(false);




const handleSaveStudent = async()=>{

setSaving(true);

setSaveError("");

try{

const payload = {

full_name: form.full_name,

phone: form.phone,

student_id: form.student_id,

gender: form.gender,

location: [form.address1, form.address2, form.city, form.state, form.postcode, form.country]

.filter(Boolean)

.join(", "),

};

if(isEditMode){

await updatePlacementStudent(editingId, payload);

}

else{

if(!form.full_name.trim() || !form.email.trim()){

setSaveError("Full name and email are required.");

setSaving(false);

return;

}

await createPlacementStudent({

...payload,

email: form.email.trim(),

});

}

navigate("/placement/students");

}

catch(error){

console.log("SAVE STUDENT ERROR", error);

const backendMessage =

error.response?.data?.error ||

error.response?.data?.message ||

"Unable to save student. Please try again.";

const debugDetail = error.response?.data?.debug_detail;

setSaveError(

debugDetail ? `${backendMessage} (${debugDetail})` : backendMessage

);

}

finally{

setSaving(false);

}

};




const handleVerifyStudent = async()=>{

if(!editingId) return;

setVerifying(true);

try{

await verifyStudent(editingId);

setIsVerified(true);

}

catch(error){

console.log("VERIFY STUDENT ERROR", error);

}

finally{

setVerifying(false);

}

};




return(


<div className="add-edit-student-page">


<button className="back-to-students-link" onClick={()=>navigate("/placement/students")}>

← Back to Students

</button>


<div className="aes-header">

<div className="aes-header-icon"><FaUserPlus/></div>

<div>

<h1>{isEditMode ? "Edit Student" : "Add Student"}</h1>

<p>Fill in the student information</p>

</div>

{
isEditMode &&

<div className="aes-verify-area">

<span className={"aes-verify-badge " + (isVerified ? "verified" : "pending")}>

{isVerified ? "Verified" : "Pending Verification"}

</span>

{
!isVerified &&

<button

type="button"

className="aes-verify-btn"

disabled={verifying}

onClick={handleVerifyStudent}

>

<FaShieldAlt/>

{verifying ? "Verifying..." : "Verify Student"}

</button>
}

</div>
}

</div>


{
saveError &&

<div className="aes-save-error">{saveError}</div>
}


<div className="aes-tabs">

{
TABS.map((tab,index)=>(

<button

key={index}

className={activeTab===index ? "active" : ""}

onClick={()=>setActiveTab(index)}

>

{tab}

</button>

))
}

</div>


<div className="aes-layout">


<div className="aes-main">


{
activeTab===0 &&

<>

<h2>Personal Information</h2>

<p className="aes-section-sub">Basic details about the student</p>


<div className="aes-form-grid">


<div className="aes-photo-upload">

<input

type="file"

accept="image/jpeg,image/png"

ref={photoInputRef}

style={{display:"none"}}

onChange={handlePhotoSelected}

/>

<div

className="aes-photo-circle"

onClick={()=>photoInputRef.current?.click()}

>

{
photoPreview ?
<img src={photoPreview} alt="Student"/>
:
<FaUserPlus/>
}

</div>

<span

className="aes-photo-camera"

onClick={()=>photoInputRef.current?.click()}

>

<FaCamera/>

</span>

<p>Upload Photo</p>

<small>JPG, PNG (Max 2MB)</small>

{
photoError &&

<small className="aes-photo-error">{photoError}</small>
}

</div>


<div className="aes-fields">


<label>Full Name *</label>

<input name="full_name" value={form.full_name} onChange={handleChange} placeholder="Enter full name"/>


<div className="aes-two-col">

<div>

<label>Email Address *</label>

<input name="email" value={form.email} onChange={handleChange} placeholder="student@example.com"/>

</div>

<div>

<label>Phone Number *</label>

<input name="phone" value={form.phone} onChange={handleChange} placeholder="12-345 6789"/>

</div>

</div>


<div className="aes-two-col">

<div>

<label>NRIC / Student ID</label>

<input name="student_id" value={form.student_id} onChange={handleChange} placeholder="Enter NRIC or Student ID"/>

</div>

<div>

<label>Gender *</label>

<select name="gender" value={form.gender} onChange={handleChange}>

<option value="">Select gender</option>

<option value="male">Male</option>

<option value="female">Female</option>

<option value="other">Other</option>

</select>

</div>

</div>


<h4>Address</h4>


<div className="aes-two-col">

<div>

<label>Address Line 1</label>

<input name="address1" value={form.address1} onChange={handleChange} placeholder="Enter address line 1"/>

</div>

<div>

<label>Address Line 2</label>

<input name="address2" value={form.address2} onChange={handleChange} placeholder="Enter address line 2 (optional)"/>

</div>

</div>


<div className="aes-four-col">

<div>

<label>City</label>

<input name="city" value={form.city} onChange={handleChange} placeholder="Enter city"/>

</div>

<div>

<label>State</label>

<input name="state" value={form.state} onChange={handleChange} placeholder="Select state"/>

</div>

<div>

<label>Postcode</label>

<input name="postcode" value={form.postcode} onChange={handleChange} placeholder="Enter postcode"/>

</div>

<div>

<label>Country *</label>

<input name="country" value={form.country} onChange={handleChange}/>

</div>

</div>


<h4>Contact Information</h4>


<div className="aes-two-col">

<div>

<label>Emergency Contact Name</label>

<input name="emergency_name" value={form.emergency_name} onChange={handleChange} placeholder="Enter emergency contact name"/>

</div>

<div>

<label>Emergency Contact Number</label>

<input name="emergency_phone" value={form.emergency_phone} onChange={handleChange} placeholder="12-345 6789"/>

</div>

</div>


<label>Relationship</label>

<input name="emergency_relationship" value={form.emergency_relationship} onChange={handleChange} placeholder="e.g. Parent, Guardian"/>


</div>


</div>

</>
}


{
activeTab===4 &&

<div className="aes-documents-tab">

<h2>Documents</h2>

<p className="aes-section-sub">Upload the student's resume and certificates</p>


<div className="aes-document-upload-row">

<input

type="file"

accept=".pdf,.doc,.docx"

ref={resumeInputRef}

style={{display:"none"}}

onChange={handleResumeSelected}

/>

<div className="aes-document-upload-icon"><FaFilePdf/></div>

<div className="aes-document-upload-text">

<h4>{resumeFile ? resumeFile.name : "Resume"}</h4>

<p>{resumeFile ? "Ready to upload" : "PDF, DOC or DOCX (Max 5MB)"}</p>

{
resumeError &&

<small className="aes-photo-error">{resumeError}</small>
}

</div>

<button

className="aes-document-upload-btn"

onClick={()=>resumeInputRef.current?.click()}

>

{resumeFile ? "Replace" : "Choose File"}

</button>

</div>


<p className="aes-documents-note">

Certificates and other supporting documents can be added once the student profile is saved.

</p>

</div>
}


{
activeTab > 0 && activeTab !== 4 &&

<div className="aes-placeholder-tab">

<h2>{TABS[activeTab]}</h2>

<p>This section is being finalized. You'll be able to fill in {TABS[activeTab].toLowerCase()} here shortly.</p>

</div>
}


<div className="aes-form-actions">

<button className="aes-cancel-btn" onClick={()=>navigate("/placement/students")}>Cancel</button>

{
activeTab < TABS.length - 1 &&

<button className="aes-next-btn aes-next-btn-secondary" disabled={saving} onClick={goNext}>

Next <FaArrowRight/>

</button>
}

<button className="aes-next-btn" disabled={saving} onClick={handleSaveStudent}>

{saving ? "Saving..." : (isEditMode ? "Save Changes" : "Save Student")}

</button>

</div>


</div>




<div className="aes-sidebar">


<div className="aes-insights-card">

<h4><FaMagic/> AI Profile Insights</h4>

<p>Our AI analyzes the student profile and suggests improvements.</p>

<div className="aes-insights-placeholder">

<FaMagic/>

<span>Add basic information to get AI insights and recommendations.</span>

</div>

</div>


<div className="aes-completion-card">

<div className="aes-completion-header">

<h4>Profile Completion</h4>

<b>{completionPct}%</b>

</div>

<div className="aes-completion-bar">

<div className="aes-completion-fill" style={{width:`${completionPct}%`}}></div>

</div>

</div>


<div className="aes-tips-card">

<h4><FaLightbulb/> Quick Tips</h4>

<ul>

<li><FaCheck/> Complete all required fields</li>

<li><FaCheck/> Upload a clear profile photo</li>

<li><FaCheck/> Add academic details and skills</li>

<li><FaCheck/> Set placement preferences</li>

<li><FaCheck/> Upload relevant documents (resume, certificates)</li>

</ul>

</div>


</div>


</div>


</div>


);



};




export default AddEditStudent;
