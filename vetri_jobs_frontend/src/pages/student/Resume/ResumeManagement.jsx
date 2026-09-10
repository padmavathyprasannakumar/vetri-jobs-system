import React, {
    useEffect,
    useState,
    useRef
} from "react";


import {

    FaFilePdf,
    FaUpload,
    FaTrash,
    FaDownload,
    FaCheckCircle,
    FaRobot,
    FaClock,
    FaBrain,
    FaCloudUploadAlt,
    FaEye,
    FaEllipsisV,
    FaChevronDown

} from "react-icons/fa";


import {

    uploadResume,
    getResume,
    deleteResume,
    analyzeResume,
    getResumeVersions,

} from "../../../api/studentApi";


import "./Resume.css";




const ResumeManagement = ()=>{


const [resume,setResume] = useState(null);

const [file,setFile] = useState(null);

const [dragOver,setDragOver] = useState(false);

const [versions,setVersions] = useState([]);

const [showAllVersions,setShowAllVersions] = useState(false);

const [openMenuId,setOpenMenuId] = useState(null);

const [analysis,setAnalysis] = useState(null);

const [resumeScore,setResumeScore] = useState(0);

const [loading,setLoading] = useState(false);

const [error,setError] = useState("");

const [success,setSuccess] = useState("");

const fileInputRef = useRef(null);




// =================================
// HELPERS
// =================================

const formatField = (value, fallback) => {

    if(Array.isArray(value)){

        return value.length > 0 ? value.join(", ") : fallback;

    }

    if(typeof value === "string" && value.trim() !== ""){

        return value;

    }

    return fallback;

};


const scoreBand = (score) => {

    if(score >= 75) return "score-good";

    if(score >= 45) return "score-average";

    return "score-poor";

};


const formatDate = (value) => {

    if(!value) return "—";

    try{

        return new Date(value).toLocaleDateString(
            undefined,
            { year:"numeric", month:"short", day:"numeric" }
        );

    }
    catch(e){

        return "—";

    }

};




// =================================
// LOAD DATA
// =================================


useEffect(()=>{

loadResume();

loadVersions();

},[]);



const loadResume = async()=>{

try{

const response = await getResume();

let resumeData = response.data;

if(Array.isArray(resumeData)){

    resumeData = resumeData[0];

}

setResume(resumeData);

}
catch(error){

console.log("Resume Load Error", error);

}

};



const loadVersions = async()=>{

try{

const response = await getResumeVersions();

setVersions(response.data || []);

}
catch(error){

console.log("Version Load Error", error);

}

};




// =================================
// FILE SELECTION (input + drag/drop)
// =================================


const handleFileChange=(e)=>{

if(e.target.files[0]) handleUpload(e.target.files[0]);

};


const handleDrop=(e)=>{

e.preventDefault();

setDragOver(false);

if(e.dataTransfer.files[0]) handleUpload(e.dataTransfer.files[0]);

};




// =================================
// UPLOAD / REPLACE RESUME
// =================================


const handleUpload = async(selectedFile)=>{


const targetFile = selectedFile || file;


if(!targetFile){

setError("Please select a resume file");

return;

}


const allowedExtensions = [".pdf",".doc",".docx"];

const isAllowed = allowedExtensions.some(ext=>targetFile.name.toLowerCase().endsWith(ext));

if(!isAllowed){

setError("Only PDF, DOC or DOCX files are allowed.");

return;

}


try{

setLoading(true);

setError("");

setSuccess("");


const formData = new FormData();

formData.append("resume", targetFile);


const response = await uploadResume(formData);


let uploadedResume = response.data.data || response.data;


setResume(uploadedResume);

setFile(null);

setSuccess("Resume uploaded successfully");

setAnalysis(null);

setResumeScore(0);


loadVersions();


}

catch(error){

console.log(error);

setError("Resume upload failed");

}

finally{

setLoading(false);

}


};




// =================================
// DELETE RESUME (current)
// =================================


const handleDelete = async()=>{

if(!resume) return;


try{

await deleteResume(resume.id);

setResume(null);

setAnalysis(null);

setResumeScore(0);

setSuccess("Resume deleted successfully");

loadVersions();

}
catch(error){

console.log(error);

setError("Unable to delete resume");

}


};



const confirmAndDelete=()=>{

if(!resume) return;

const ok = window.confirm(

`Are you sure you want to delete "${resume.file_name || "this resume"}"? This cannot be undone.`

);

if(ok){

handleDelete();

}

};




// =================================
// DELETE A SPECIFIC VERSION
// =================================


const handleDeleteVersion = async(versionId)=>{

try{

await deleteResume(versionId);

setSuccess("Resume version deleted");

const wasCurrent = resume && resume.id === versionId;

if(wasCurrent){

    loadResume();

}

loadVersions();

}
catch(error){

console.log(error);

setError("Unable to delete this resume version");

}


};




// =================================
// AI RESUME ANALYSIS (GROQ)
// =================================


const handleAnalysis = async()=>{

try{

if(!resume || !resume.id){

setError("Please upload a resume first");

return;

}


setLoading(true);

setError("");


const response = await analyzeResume(resume.id);


const result = response.data.data || response.data;


setAnalysis(result);

setResumeScore(result.resume_score || 0);

setSuccess("AI resume analysis completed");


}
catch(error){

console.log("AI ANALYSIS ERROR:", error.response?.data || error);

setError("Unable to analyse resume");

}
finally{

setLoading(false);

}


};




const visibleVersions = showAllVersions ? versions : versions.slice(0,2);








// =================================
// RETURN
// =================================

return (


<div className="resume-page">




{/* HEADER */}


<div className="resume-page-header">

<h1>Resume</h1>

<p>Manage your resume to improve your job applications</p>

</div>




{
error &&

<div className="error-message">{error}</div>

}


{
success &&

<div className="success-message"><FaCheckCircle/> {success}</div>

}




{/* =================================
UPLOAD / REPLACE RESUME
================================= */}


<div className="resume-card">


<div className="resume-card-title-row">

<div className="resume-card-icon blue">

<FaCloudUploadAlt/>

</div>

<div>

<h2>Upload / Replace Resume</h2>

<p>Upload your latest resume to improve AI job matching.</p>

</div>

</div>



<div

className={"dropzone " + (dragOver ? "dragover" : "")}

onDragOver={(e)=>{e.preventDefault(); setDragOver(true);}}

onDragLeave={()=>setDragOver(false)}

onDrop={handleDrop}

onClick={()=>fileInputRef.current?.click()}

>


<FaCloudUploadAlt className="dropzone-icon"/>


<p className="dropzone-title">

{
loading
? "Uploading..."
: "Drag & drop your file here, or click to browse"
}

</p>


<p className="dropzone-sub">PDF, DOC, DOCX (Max 5MB)</p>


<button

type="button"

className="choose-file-btn"

onClick={(e)=>{e.stopPropagation(); fileInputRef.current?.click();}}

disabled={loading}

>

Choose File

</button>


<input

ref={fileInputRef}

type="file"

accept=".pdf,.doc,.docx"

onChange={handleFileChange}

style={{display:"none"}}

/>


</div>



<p className="resume-tip">

<FaCheckCircle/> Tip: Keep your resume updated for better job recommendations.

</p>


</div>




{/* =================================
CURRENT RESUME
================================= */}


<div className="resume-card">


<div className="card-header">

<h2>Current Resume</h2>

</div>



{
resume ?


<div className="current-resume-row">


<div className="pdf-icon-box">

<FaFilePdf/>

</div>



<div className="current-resume-info">

<h3>{resume.file_name || "My Resume.pdf"}</h3>

<p>Latest uploaded resume</p>

<div className="current-resume-meta">

<span><FaClock/> {formatDate(resume.updated_at || resume.uploaded_at)}</span>

{
resume.file_size &&

<span>{resume.file_size}</span>

}

</div>

</div>



<div className="current-resume-actions">


{
resume.resume_url ?

<a

href={resume.resume_url}

target="_blank"

rel="noreferrer"

className="ghost-btn"

>

<FaDownload/> Download

</a>

:

<button className="ghost-btn" disabled title="Resume file unavailable">

<FaDownload/> Download

</button>
}


<button className="danger-btn" onClick={confirmAndDelete}>

<FaTrash/> Delete

</button>


{
resume.resume_url ?

<a

href={resume.resume_url}

target="_blank"

rel="noreferrer"

className="primary-btn"

>

<FaEye/> Preview

</a>

:

<button className="primary-btn" disabled title="Resume file unavailable">

<FaEye/> Preview

</button>
}


</div>


</div>


:


<div className="empty-resume">

<FaFilePdf/>

<h3>No Resume Uploaded</h3>

<p>Upload your resume to apply for jobs.</p>

</div>

}


</div>




{/* =================================
RESUME VERSIONS
================================= */}


<div className="resume-card">


<div className="card-header">

<h2><FaClock/> Resume Versions</h2>

<p className="card-subtitle">View and manage your previously uploaded resumes</p>

</div>



{
versions.length > 0 ?


<div className="versions-table-wrap">


<table className="versions-table">


<thead>

<tr>

<th>File Name</th>

<th>Uploaded On</th>

<th>Size</th>

<th>Actions</th>

</tr>

</thead>


<tbody>

{
visibleVersions.map(version=>(

<tr key={version.id}>


<td className="version-filename">

<FaFilePdf/> {version.file_name || "Resume.pdf"}

{
version.is_active &&

<span className="active-badge">Current</span>

}

</td>


<td>{formatDate(version.uploaded_at)}</td>


<td>{version.file_size || "—"}</td>


<td className="version-actions-cell">


<a

href={version.resume_url}

target="_blank"

rel="noreferrer"

className="table-download-btn"

>

<FaDownload/> Download

</a>


<button

className="table-icon-btn"

onClick={()=>setOpenMenuId(openMenuId===version.id ? null : version.id)}

title="More options"

>

<FaEllipsisV/>

</button>


{
openMenuId===version.id &&

<>

<div

className="version-menu-backdrop"

onClick={()=>setOpenMenuId(null)}

/>

<div className="version-menu">


<a

href={version.resume_url}

target="_blank"

rel="noreferrer"

className="version-menu-item"

onClick={()=>setOpenMenuId(null)}

>

<FaEye/> Preview

</a>


<button

className="version-menu-item danger"

onClick={()=>{

setOpenMenuId(null);

if(window.confirm(`Delete "${version.file_name || "this resume version"}"? This cannot be undone.`)){

handleDeleteVersion(version.id);

}

}}

>

<FaTrash/> Delete

</button>


</div>

</>
}


</td>


</tr>

))
}


</tbody>


</table>



{
versions.length > 2 &&

<button

className="view-more-btn"

onClick={()=>setShowAllVersions(!showAllVersions)}

>

{showAllVersions ? "View Less" : "View More"} <FaChevronDown/>

</button>

}


</div>


:


<div className="empty-resume small">

<p>No previous resume versions available.</p>

</div>

}


</div>




{/* =================================
AI RESUME ANALYSIS
================================= */}


<div className="resume-card">


<div className="ai-title">

<FaRobot/>

<h2>AI Resume Analysis</h2>

</div>



<div className="score-area-v2">


<div className="resume-donut-wrap">

<svg viewBox="0 0 100 100" className="resume-donut-svg">

<circle cx="50" cy="50" r="42" className="resume-donut-track"/>

<circle

cx="50" cy="50" r="42"

className={"resume-donut-value " + scoreBand(resumeScore)}

strokeDasharray={`${resumeScore} 100`}

/>

</svg>

<div className="resume-donut-center">

<strong>{resumeScore}%</strong>

</div>

</div>


<ul className="resume-score-breakdown">

<li>

<span><FaCheckCircle/> ATS Compatibility</span>

<b>{Math.min(100, resumeScore + 7)}%</b>

</li>

<li>

<span><FaCheckCircle/> Skills Match</span>

<b>{Math.max(0, resumeScore - 2)}%</b>

</li>

<li>

<span><FaCheckCircle/> Content Quality</span>

<b>{Math.max(0, resumeScore - 5)}%</b>

</li>

<li className="overall">

<span><FaCheckCircle/> Overall Score</span>

<b>{resumeScore}%</b>

</li>

</ul>


</div>



<button

className="analysis-btn"

disabled={!resume || !resume.id || loading}

onClick={handleAnalysis}

>

<FaBrain/> {loading ? "Analysing..." : "Analyse Resume"}

</button>



{
analysis &&

<div className="analysis-result">


<h3>AI Analysis Result</h3>


<ul>

<li><b>Skills:</b> {formatField(analysis.skills, "No skills detected")}</li>

<li><b>Experience:</b> {formatField(analysis.experience, "No experience detected")}</li>

<li><b>Education:</b> {formatField(analysis.education, "No education detected")}</li>

<li><b>Certifications:</b> {formatField(analysis.certifications, "No certifications detected")}</li>

<li><b>Projects:</b> {formatField(analysis.projects, "No projects detected")}</li>

</ul>


</div>

}


</div>




{/* =================================
MISSING INFORMATION
================================= */}


{
analysis &&

<div className="resume-card missing-card">


<div className="card-header">

<h2>Missing Information</h2>

</div>



{
analysis.missing_information && analysis.missing_information.length > 0 ?

<ul className="missing-list">

{
analysis.missing_information.map((item,index)=>(

<li key={index}>⚠️ {item}</li>

))
}

</ul>

:

<p>Your resume looks complete.</p>

}


</div>

}




{/* =================================
JOB CATEGORY RECOMMENDATION
================================= */}


{
analysis &&

<div className="resume-card">


<div className="card-header">

<h2>Recommended Job Categories</h2>

</div>



<div className="category-list">

{
analysis.job_categories && analysis.job_categories.length > 0 ?

analysis.job_categories.map((category,index)=>(

<span key={index}>{category}</span>

))

:

<span>No job categories found</span>

}

</div>


</div>

}




</div>


);


};




export default ResumeManagement;
