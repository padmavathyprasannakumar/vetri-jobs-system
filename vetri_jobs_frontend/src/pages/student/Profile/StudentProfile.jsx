import React, {

    useEffect,

    useState

} from "react";


import {

    getStudentProfile,

    updateStudentProfile,

    uploadResume

} from "../../../api/studentApi";


import {

    getSiteBranding

} from "../../../api/brandingApi";



import {

    FaUser,

    FaEnvelope,

    FaPhone,

    FaGraduationCap,

    FaFileUpload,

    FaSave,

    FaChartLine

} from "react-icons/fa";



import Avatar from "../../../components/Avatar/Avatar";

import "./StudentProfile.css";








const StudentProfile = ()=>{


const [branding,setBranding] = useState({ profile_hero_image_url:null });


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);





const [profile,setProfile]=useState(null);

const [countryCode,setCountryCode]=useState("+91");


const [loading,setLoading]=useState(true);


const [saving,setSaving]=useState(false);

const [isEditing,setIsEditing]=useState(false);


const [resume,setResume]=useState(null);


const [message,setMessage]=useState("");









// ================================
// LOAD PROFILE
// ================================


useEffect(()=>{


    loadProfile();


},[]);









const loadProfile=async()=>{


try{


const response =

await getStudentProfile();



const KNOWN_CODES = [

"+971","+974","+966","+880","+92","+63","+27","+49","+33","+81","+86",

"+91","+65","+60","+61","+94","+44","+1"

];

let phoneValue = response.data?.phone || "";

let detectedCode = "+91";

for(const code of KNOWN_CODES){

if(phoneValue.startsWith(code)){

detectedCode = code;

phoneValue = phoneValue.slice(code.length).trim();

break;

}

}

setCountryCode(detectedCode);

setProfile({...response.data, phone: phoneValue});



}


catch(error){


console.log(

"PROFILE LOAD ERROR",

error

);


}


finally{


setLoading(false);


}



};












// ================================
// HANDLE INPUT
// ================================


const handleChange=(e)=>{


setProfile({


    ...profile,


    [e.target.name]:

    e.target.value


});


};












// ================================
// UPDATE PROFILE
// ================================


const handleUpdate=async()=>{


try{


setSaving(true);



await updateStudentProfile(

{

...profile,

phone: profile.phone

? `${countryCode}${profile.phone}`

: profile.phone,

}

);



setMessage(

"Profile updated successfully"

);


setIsEditing(false);




setTimeout(()=>{


setMessage("");

},3000);



}


catch(error){


console.log(error);


const data = error.response?.data;

let friendlyMessage = "Profile update failed";

if(data){

if(typeof data === "string"){

friendlyMessage = data;

}
else if(data.error){

friendlyMessage = data.error;

}
else if(data.detail){

friendlyMessage = data.detail;

}
else if(typeof data === "object"){

// DRF validation errors come back as { field_name: ["message"] } -
// surface the actual reason instead of a generic failure message.

const fieldErrors = Object.entries(data)

.map(([field,messages])=>

`${field.replace(/_/g," ")}: ${Array.isArray(messages) ? messages.join(", ") : messages}`

);

if(fieldErrors.length > 0){

friendlyMessage = fieldErrors.join(" | ");

}

}

}

setMessage(friendlyMessage);


}


finally{


setSaving(false);


}



};












// ================================
// RESUME UPLOAD
// ================================


const handleResumeUpload=async()=>{


if(!resume)

return;



try{


await uploadResume(

resume

);



setMessage(

"Resume uploaded successfully"

);



loadProfile();



}


catch(error){


console.log(

"RESUME ERROR",

error

);



setMessage(

"Resume upload failed"

);



}



};














if(loading){


return(


<div className="profile-loading">


<div className="loader"></div>


<p>

Loading profile...

</p>



</div>


);


}









return(



<div className="student-profile">








{/* ============================
PROFILE HEADER
============================ */}



<div className="profile-header">



<div className="profile-avatar">


<Avatar name={profile?.full_name} size={80}/>


</div>





<div>


<h1>


{

profile?.full_name

||

"Student Profile"


}


</h1>



<p>

Build your professional profile
and improve job opportunities

</p>



</div>







{
branding.profile_hero_image_url &&

<img

src={branding.profile_hero_image_url}

alt="Vetri Jobs"

className="profile-header-illustration"

/>
}



{
!isEditing &&

<button

className="edit-profile-btn"

onClick={()=>setIsEditing(true)}

>

<FaSave/> Edit Profile

</button>
}

</div>

<fieldset disabled={!isEditing} className="profile-fieldset">













{

message &&


<div className="profile-message">


{message}


</div>


}












{/* ============================
PROFILE COMPLETION
============================ */}




<div className="completion-card">



<div>


<h3>

Profile Completion

</h3>



<p>

Complete your profile to get better
job recommendations

</p>


</div>





<div className="completion-circle">


{

profile?.profile_completion || 0

}%

</div>




</div>













{/* ============================
PERSONAL INFORMATION
============================ */}



<div className="profile-card">



<h2>


<FaUser/>

Personal Information


</h2>





<div className="form-grid">







<div className="form-group">


<label>

Full Name

</label>



<div className="input-icon">


<FaUser/>


<input


type="text"


name="full_name"


value={

profile?.full_name || ""

}


onChange={handleChange}


/>


</div>



</div>









<div className="form-group">


<label>

Student ID

</label>



<input


type="text"


name="student_id"


value={

profile?.student_id || ""

}


onChange={handleChange}


/>



</div>









<div className="form-group">


<label>

Email

</label>



<div className="input-icon">


<FaEnvelope/>


<input


type="email"


name="email"


value={

profile?.email || ""

}


onChange={handleChange}


/>



</div>



</div>









<div className="form-group">


<label>

Phone

</label>



<div className="input-icon phone-input-with-code">


<FaPhone/>

<select

className="phone-country-code-select"

value={countryCode}

onChange={(e)=>setCountryCode(e.target.value)}

>

<option value="+91">🇮🇳 +91</option>

<option value="+1">🇺🇸 +1</option>

<option value="+44">🇬🇧 +44</option>

<option value="+61">🇦🇺 +61</option>

<option value="+65">🇸🇬 +65</option>

<option value="+60">🇲🇾 +60</option>

<option value="+971">🇦🇪 +971</option>

<option value="+974">🇶🇦 +974</option>

<option value="+966">🇸🇦 +966</option>

<option value="+94">🇱🇰 +94</option>

<option value="+880">🇧🇩 +880</option>

<option value="+92">🇵🇰 +92</option>

<option value="+63">🇵🇭 +63</option>

<option value="+27">🇿🇦 +27</option>

<option value="+49">🇩🇪 +49</option>

<option value="+33">🇫🇷 +33</option>

<option value="+81">🇯🇵 +81</option>

<option value="+86">🇨🇳 +86</option>

</select>


<input


type="text"


name="phone"


value={

profile?.phone || ""

}


onChange={handleChange}

placeholder="12-345 6789"


/>


</div>



</div>









<div className="form-group">


<label>

Date Of Birth

</label>


<input


type="date"


name="date_of_birth"


value={

profile?.date_of_birth || ""

}


onChange={handleChange}


/>


</div>









<div className="form-group">


<label>

Gender

</label>



<input


type="text"


name="gender"


value={

profile?.gender || ""

}


onChange={handleChange}


/>



</div>









<div className="form-group">


<label>

Location

</label>



<input


type="text"


name="location"


value={

profile?.location || ""

}


onChange={handleChange}


/>



</div>








</div>



</div>

{/* ============================
ACADEMIC INFORMATION
============================ */}



<div className="profile-card">



<h2>


<FaGraduationCap/>

Academic Details


</h2>






<div className="form-grid">







<div className="form-group">


<label>

Institution

</label>


<input


type="text"


name="institution"


value={

profile?.institution || ""

}


onChange={handleChange}


/>


</div>








<div className="form-group">


<label>

Course

</label>



<input


type="text"


name="course"


value={

profile?.course || ""

}


onChange={handleChange}


/>



</div>








<div className="form-group">


<label>

Department

</label>



<input


type="text"


name="department"


value={

profile?.department || ""

}


onChange={handleChange}


/>



</div>








<div className="form-group">


<label>

Graduation Year

</label>



<input


type="number"


name="graduation_year"


value={

profile?.graduation_year || ""

}


onChange={handleChange}


/>



</div>








<div className="form-group">


<label>

10th Percentage

</label>



<input


type="number"


name="tenth_percentage"


value={

profile?.tenth_percentage || ""

}


onChange={handleChange}


/>



</div>








<div className="form-group">


<label>

12th Percentage

</label>



<input


type="number"


name="twelfth_percentage"


value={

profile?.twelfth_percentage || ""

}


onChange={handleChange}


/>



</div>








<div className="form-group">


<label>

UG CGPA / Percentage

</label>



<input


type="number"


step="0.01"


name="ug_cgpa"


value={

profile?.ug_cgpa || ""

}


onChange={handleChange}


/>



</div>






</div>









<label className="section-field-label">Diploma Details</label>

<textarea


name="diploma_details"


value={

profile?.diploma_details || ""

}


onChange={handleChange}


placeholder="Diploma Details"



/>








<label className="section-field-label">PG Details</label>

<textarea


name="pg_details"


value={

profile?.pg_details || ""

}


onChange={handleChange}


placeholder="PG Details"



/>





</div>













{/* ============================
PROFESSIONAL INFORMATION
============================ */}



<div className="profile-card">



<h2>

Professional Details

</h2>









<label className="section-field-label">Skills</label>

<textarea


name="skills"


value={

profile?.skills || ""

}


onChange={handleChange}


placeholder="Skills (React, Python, Java, SQL...)"



/>








<label className="section-field-label">Certifications</label>

<textarea


name="certifications"


value={

profile?.certifications || ""

}


onChange={handleChange}


placeholder="Certifications"



/>








<label className="section-field-label">Projects</label>

<textarea


name="projects"


value={

profile?.projects || ""

}


onChange={handleChange}


placeholder="Projects"



/>








<label className="section-field-label">Internships</label>

<textarea


name="internships"


value={

profile?.internships || ""

}


onChange={handleChange}


placeholder="Internships"



/>








<label className="section-field-label">Experience</label>

<textarea


name="experience"


value={

profile?.experience || ""

}


onChange={handleChange}


placeholder="Work Experience"



/>








<label className="section-field-label">Languages</label>

<textarea


name="languages"


value={

profile?.languages || ""

}


onChange={handleChange}


placeholder="Languages"



/>










<div className="form-grid">






<div className="form-group">


<label>

Portfolio

</label>


<input


type="url"


name="portfolio"


value={

profile?.portfolio || ""

}


onChange={handleChange}


placeholder="Portfolio URL"



/>



</div>









<div className="form-group">


<label>

GitHub

</label>



<input


type="url"


name="github"


value={

profile?.github || ""

}


onChange={handleChange}


placeholder="GitHub URL"



/>



</div>









<div className="form-group">


<label>

LinkedIn

</label>



<input


type="url"


name="linkedin"


value={

profile?.linkedin || ""

}


onChange={handleChange}


placeholder="LinkedIn URL"



/>



</div>






</div>





</div>












{/* ============================
RESUME MANAGEMENT
============================ */}



<div className="profile-card">



<h2>

Resume Management

</h2>







<div className="resume-area">



<input


type="file"


accept=".pdf,.doc,.docx"


onChange={(e)=>{


setResume(

e.target.files[0]

);


}}


/>






<button


onClick={handleResumeUpload}



>


<FaFileUpload/>


Upload Resume


</button>





</div>









{

profile?.resume &&



<div className="resume-preview">


<a


href={profile.resume}


target="_blank"


rel="noreferrer"


>


View Current Resume


</a>



</div>



}







</div>













</fieldset>


{/* ============================
SAVE PROFILE
============================ */}


{
isEditing &&

<div className="profile-save-row">


<button

className="cancel-btn"

onClick={()=>{

loadProfile();

setIsEditing(false);

}}

>

Cancel

</button>


<button


className="save-profile"


onClick={handleUpdate}


disabled={saving}



>


<FaSave/>


{


saving

?

"Saving..."

:

"Save Profile"


}



</button>


</div>
}









</div>


);


};



export default StudentProfile;