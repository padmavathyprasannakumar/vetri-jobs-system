import React, { useState, useEffect } from "react";

import { getSiteBranding } from "../../../api/brandingApi";

import { useNavigate, Link } from "react-router-dom";

import { registerCompany } from "../../../api/authApi";

import {
    FaBuilding,
    FaFilePdf,
    FaImages,
    FaLinkedin,
    FaGlobe,
    FaInstagram,
    FaFacebook,
    FaLock,
    FaEye,
    FaEyeSlash,
    FaEnvelope,
    FaMapMarkerAlt,
    FaAt,
    FaPaperPlane,
    FaCheckCircle,
} from "react-icons/fa";

import "./CompanyRegister.css";




const STEPS = [

    { n: 1, title: "Company Details", desc: "Fill in basic information" },

    { n: 2, title: "Upload Documents", desc: "Reg. cert, GST, photos" },

    { n: 3, title: "Admin Approval", desc: "Wait for verification" },

    { n: 4, title: "Get Access", desc: "Login to dashboard" },

];




const CompanyRegister = ()=>{


const navigate = useNavigate();


const [branding,setBranding] = useState({

site_name: "Vetri Jobs",

logo_url: null,

});


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);


const [form,setForm] = useState({

company_name: "",

username: "",

email: "",

address: "",

password: "",

confirm_password: "",

linkedin: "",

website: "",

instagram: "",

facebook: "",

});


const [registrationDoc,setRegistrationDoc] = useState(null);

const [gstDoc,setGstDoc] = useState(null);

const [photos,setPhotos] = useState([]);


const [showPassword,setShowPassword] = useState(false);

const [showConfirm,setShowConfirm] = useState(false);


const [agreed,setAgreed] = useState(false);


const [loading,setLoading] = useState(false);

const [error,setError] = useState("");

const [success,setSuccess] = useState("");




const handleChange = (e)=>{

setForm({ ...form, [e.target.name]: e.target.value });

};




const handlePhotosChange = (e)=>{

const newFiles = Array.from(e.target.files || []);

setPhotos(prev=>[...prev, ...newFiles].slice(0,5));

// reset the input so selecting the same file again (after
// removing it) still fires onChange

e.target.value = "";

};




const clearPhotos = ()=>{

setPhotos([]);

};




const getErrorMessage = (data)=>{

if(!data) return "Registration failed. Please try again.";

if(data.error) return data.error;

if(data.detail) return data.detail;

if(typeof data === "string") return data;

return Object.values(data).flat().join(" ");

};




const handleSubmit = async(e)=>{

e.preventDefault();

setError("");

setSuccess("");


if(form.password !== form.confirm_password){

setError("Password and confirm password do not match");

return;

}


if(!registrationDoc){

setError("Please upload your company registration document");

return;

}


if(!gstDoc){

setError("Please upload your GST document");

return;

}


if(photos.length === 0){

setError("Please upload at least one company photo with location");

return;

}


if(!agreed){

setError("Please agree to the Terms and Conditions");

return;

}


setLoading(true);


try{


const formData = new FormData();


formData.append("company_name", form.company_name.trim());

formData.append("username", form.username.trim());

formData.append("email", form.email.trim());

formData.append("address", form.address.trim());

formData.append("password", form.password);

formData.append("confirm_password", form.confirm_password);

formData.append("linkedin", form.linkedin.trim());

formData.append("website", form.website.trim());

formData.append("instagram", form.instagram.trim());

formData.append("facebook", form.facebook.trim());

formData.append("registration_document", registrationDoc);

formData.append("gst_document", gstDoc);


photos.forEach(photo=>{

formData.append("company_photos", photo);

});


const response = await registerCompany(formData);


setSuccess(

response.data?.message ||

"Your application has been submitted for review. You'll be able to log in once an admin approves it."

);


setTimeout(()=>{

navigate("/company/login", { replace: true });

}, 3000);


}

catch(error){


setError(getErrorMessage(error.response?.data));


}

finally{


setLoading(false);


}


};




return(


<div className="cr2-page">


<div className="cr2-card">


<aside className="cr2-sidebar">


<div className="cr2-logo">

{
branding.logo_url ?

<img src={branding.logo_url} alt={branding.site_name}/>

:

<FaBuilding/>
}

<span>{branding.site_name || "Vetri Jobs"}</span>

</div>


<p className="cr2-sidebar-label">Registration Steps</p>


<div className="cr2-steps">

{
STEPS.map(step=>(

<div className="cr2-step active" key={step.n}>

<div className="cr2-step-num">{step.n}</div>

<div>

<strong>{step.title}</strong>

<p>{step.desc}</p>

</div>

</div>

))
}

</div>


<div className="cr2-sidebar-footer">

<p>Need help? Contact our placement team for assistance with your registration.</p>

</div>


</aside>




<main className="cr2-main">


<div className="cr2-main-top">

<span className="cr2-badge"><FaBuilding/> Company Registration</span>

<Link to="/company/login" className="cr2-back-link">back</Link>

</div>


<h1>Register Your Company</h1>

<p className="cr2-sub">Submit your details for admin verification and approval.</p>


<div className="cr2-notice">

⚠️ After submission, admin will review your documents. You'll receive an update once approved. Only official company details are accepted.

</div>


{
error &&

<div className="cr2-error">{error}</div>
}


{
success &&

<div className="cr2-success"><FaCheckCircle/> {success}</div>
}


<form onSubmit={handleSubmit}>


<h3 className="cr2-section-title"><FaBuilding/> Company Information</h3>


<div className="cr2-grid">

<div>

<label>Company Name *</label>

<div className="cr2-input">

<FaBuilding/>

<input

name="company_name"

placeholder="Acme Pvt Ltd"

value={form.company_name}

onChange={handleChange}

required

/>

</div>

</div>


<div>

<label>Username *</label>

<div className="cr2-input">

<FaAt/>

<input

name="username"

placeholder="no spaces allowed"

value={form.username}

onChange={handleChange}

required

/>

</div>

</div>


<div>

<label>Company Email *</label>

<div className="cr2-input">

<FaEnvelope/>

<input

type="email"

name="email"

placeholder="hr@yourcompany.com"

value={form.email}

onChange={handleChange}

required

/>

</div>

</div>


<div>

<label>Location / Address *</label>

<div className="cr2-input">

<FaMapMarkerAlt/>

<input

name="address"

placeholder="Chennai, Tamil Nadu"

value={form.address}

onChange={handleChange}

required

/>

</div>

</div>


<div>

<label>Password *</label>

<div className="cr2-input">

<FaLock/>

<input

type={showPassword ? "text" : "password"}

name="password"

placeholder="Enter password"

value={form.password}

onChange={handleChange}

required

/>

<button type="button" className="cr2-eye" onClick={()=>setShowPassword(!showPassword)}>

{showPassword ? <FaEyeSlash/> : <FaEye/>}

</button>

</div>

</div>


<div>

<label>Confirm Password *</label>

<div className="cr2-input">

<FaLock/>

<input

type={showConfirm ? "text" : "password"}

name="confirm_password"

placeholder="Confirm password"

value={form.confirm_password}

onChange={handleChange}

required

/>

<button type="button" className="cr2-eye" onClick={()=>setShowConfirm(!showConfirm)}>

{showConfirm ? <FaEyeSlash/> : <FaEye/>}

</button>

</div>

</div>

</div>




<h3 className="cr2-section-title"><FaFilePdf/> Company Documents</h3>


<div className="cr2-grid">

<div>

<label>Company Registration Document *</label>

<label className="cr2-upload">

<FaFilePdf/>

<span>{registrationDoc ? registrationDoc.name : "Click to upload"}</span>

<small>PDF / JPG / PNG</small>

<input

type="file"

accept=".pdf,.jpg,.jpeg,.png"

onChange={(e)=>setRegistrationDoc(e.target.files?.[0] || null)}

hidden

/>

</label>

</div>


<div>

<label>GST Document *</label>

<label className="cr2-upload">

<FaFilePdf/>

<span>{gstDoc ? gstDoc.name : "Click to upload"}</span>

<small>PDF / JPG / PNG</small>

<input

type="file"

accept=".pdf,.jpg,.jpeg,.png"

onChange={(e)=>setGstDoc(e.target.files?.[0] || null)}

hidden

/>

</label>

</div>

</div>


<label>Company Photos with Location *</label>

<p className="cr2-hint">(1-5 photos with office / location)</p>

<label className="cr2-upload cr2-upload-wide">

<FaImages/>

<span>

{
photos.length > 0

? `${photos.length} photo(s) selected`

: "Click to upload company photos"
}

</span>

<small>JPG / PNG · Max 5 photos</small>

<input

type="file"

accept=".jpg,.jpeg,.png"

multiple

onChange={handlePhotosChange}

hidden

/>

</label>

{
photos.length > 0 &&

<button

type="button"

className="cr2-clear-photos-btn"

onClick={clearPhotos}

>

Clear selected photos

</button>
}




<h3 className="cr2-section-title"><FaGlobe/> Online Presence</h3>


<div className="cr2-grid">

<div>

<label>LinkedIn Profile</label>

<div className="cr2-input">

<FaLinkedin/>

<input

name="linkedin"

placeholder="https://linkedin.com/company/yourcompany"

value={form.linkedin}

onChange={handleChange}

/>

</div>

</div>


<div>

<label>Company Website</label>

<div className="cr2-input">

<FaGlobe/>

<input

name="website"

placeholder="https://yourcompany.com"

value={form.website}

onChange={handleChange}

/>

</div>

</div>


<div>

<label>Instagram (optional)</label>

<div className="cr2-input">

<FaInstagram/>

<input

name="instagram"

placeholder="https://instagram.com/yourcompany"

value={form.instagram}

onChange={handleChange}

/>

</div>

</div>


<div>

<label>Facebook (optional)</label>

<div className="cr2-input">

<FaFacebook/>

<input

name="facebook"

placeholder="https://facebook.com/yourcompany"

value={form.facebook}

onChange={handleChange}

/>

</div>

</div>

</div>


<label className="cr2-terms">

<input

type="checkbox"

checked={agreed}

onChange={(e)=>setAgreed(e.target.checked)}

/>

<span>I agree to the <Link to="/terms">Terms and Conditions</Link></span>

</label>


<button type="submit" className="cr2-submit" disabled={loading}>

<FaPaperPlane/> {loading ? "Submitting..." : "Submit for Approval"}

</button>


<p className="cr2-login-link">

Already approved? <Link to="/company/login">Company Login</Link>

</p>


</form>


</main>


</div>


</div>


);


};




export default CompanyRegister;
