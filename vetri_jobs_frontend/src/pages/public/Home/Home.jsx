import React, { useState, useEffect } from "react";

import { useNavigate, Link } from "react-router-dom";

import { useAuth } from "../../../context/AuthContext";

import { getSiteBranding } from "../../../api/brandingApi";

import { checkCompanyApplicationStatus, requestPasswordReset, confirmPasswordReset } from "../../../api/authApi";

import {

    FaBolt,
    FaBriefcase,
    FaFileAlt,
    FaComments,
    FaBuilding,
    FaUserGraduate,
    FaUserTie,
    FaEye,
    FaEyeSlash,
    FaArrowRight,
    FaRobot,
    FaBullseye,
    FaCheckCircle,
    FaTimes,
    FaClock,
    FaExclamationCircle,
    FaLock,

} from "react-icons/fa";

import "./Home.css";




const FEATURES = [

    {
        icon: <FaBriefcase/>,
        title: "AI Job Matching",
        desc: "Get jobs that match your skills",
    },
    {
        icon: <FaFileAlt/>,
        title: "Resume Analysis",
        desc: "Improve your profile with AI insights",
    },
    {
        icon: <FaComments/>,
        title: "Interview Preparation",
        desc: "Practice with AI-powered questions",
    },
    {
        icon: <FaBuilding/>,
        title: "Connect with Top Companies",
        desc: "Get placed in your dream company",
    },

];




const STATS = [

    { value: "1,500+", label: "Student Placed" },
    { value: "300+", label: "Partner Companies" },
    { value: "95%", label: "Success Rate" },
    { value: "24/7", label: "AI Support" },

];




const TABS = [

    { key: "student", label: "Student", icon: <FaUserGraduate/> },
    { key: "company", label: "Company", icon: <FaBuilding/> },
    { key: "placement_admin", label: "Placement Admin", icon: <FaUserTie/> },

];




const Home = ()=>{


const navigate = useNavigate();

const { login } = useAuth();


const [branding,setBranding] = useState({

homepage_badge_text: "AI Powered Placement Portal",

homepage_headline: "Smarter Careers",

homepage_headline_highlight: "Start Here",

homepage_subtext:
"Find internships, jobs and placement opportunities with the power "
+ "of AI. Get personalized job matches, resume insights and "
+ "interview preparation - all in one platform.",

homepage_hero_image_url: null,

});


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);




const [activeTab,setActiveTab] = useState("student");

const [form,setForm] = useState({ email:"", password:"" });

const [remember,setRemember] = useState(true);

const [showPassword,setShowPassword] = useState(false);

const [loading,setLoading] = useState(false);

const [error,setError] = useState("");


const [showStatusModal,setShowStatusModal] = useState(false);

const [statusForm,setStatusForm] = useState({ username:"", password:"" });

const [statusLoading,setStatusLoading] = useState(false);

const [statusError,setStatusError] = useState("");

const [statusResult,setStatusResult] = useState(null);


const handleCheckStatus = async(e)=>{

e.preventDefault();

setStatusError("");

setStatusResult(null);

setStatusLoading(true);

try{

const res = await checkCompanyApplicationStatus(statusForm);

setStatusResult(res.data);

}

catch(err){

setStatusError(

err.response?.data?.error ||

"Could not check status. Please check your credentials."

);

}

finally{

setStatusLoading(false);

}

};


const closeStatusModal = ()=>{

setShowStatusModal(false);

setStatusForm({ username:"", password:"" });

setStatusError("");

setStatusResult(null);

};


const [showForgotModal,setShowForgotModal] = useState(false);

const [forgotStep,setForgotStep] = useState(1);

const [forgotEmail,setForgotEmail] = useState("");

const [forgotOtp,setForgotOtp] = useState("");

const [forgotNewPassword,setForgotNewPassword] = useState("");

const [forgotConfirmPassword,setForgotConfirmPassword] = useState("");

const [forgotLoading,setForgotLoading] = useState(false);

const [forgotError,setForgotError] = useState("");

const [forgotSuccess,setForgotSuccess] = useState(false);


const closeForgotModal = ()=>{

setShowForgotModal(false);

setForgotStep(1);

setForgotEmail("");

setForgotOtp("");

setForgotNewPassword("");

setForgotConfirmPassword("");

setForgotError("");

setForgotSuccess(false);

};


const handleSendOtp = async(e)=>{

e.preventDefault();

setForgotError("");

setForgotLoading(true);

try{

await requestPasswordReset(forgotEmail);

setForgotStep(2);

}

catch(err){

setForgotError(

err.response?.data?.error ||

"Could not send verification code. Please try again."

);

}

finally{

setForgotLoading(false);

}

};


const handleResetWithOtp = async(e)=>{

e.preventDefault();

setForgotError("");

if(forgotNewPassword !== forgotConfirmPassword){

setForgotError("Passwords do not match");

return;

}

if(forgotNewPassword.length < 8){

setForgotError("Password must be at least 8 characters");

return;

}

setForgotLoading(true);

try{

await confirmPasswordReset({

email: forgotEmail,

otp: forgotOtp,

new_password: forgotNewPassword,

confirm_password: forgotConfirmPassword,

});

setForgotSuccess(true);

}

catch(err){

setForgotError(

err.response?.data?.error ||

"Could not reset password. Please check your code and try again."

);

}

finally{

setForgotLoading(false);

}

};


const REDIRECTS = {

student: "/student/dashboard",

company: "/company/dashboard",

placement_admin: "/placement/dashboard",

};


// Student self-registration no longer exists - accounts are
// created only by a placement admin (Django Admin, or
// Placement > Students > Add Student). Setting this to null
// hides the "Don't have an account? Register Here" line
// beneath the login form whenever the Student tab is active,
// since the "REGISTER_LINKS[activeTab] &&" check below already
// treats a falsy value as "nothing to show here".

const REGISTER_LINKS = {

student: null,

company: "/company/register",

placement_admin: null,

};




const handleChange = (e)=>{

setForm({ ...form, [e.target.name]: e.target.value });

};




const handleTabChange = (key)=>{

setActiveTab(key);

setError("");

};




const handleSubmit = async(e)=>{

e.preventDefault();

setError("");

setLoading(true);


try{


const result = await login({

email: form.email,

password: form.password,

});


if(result.success){

const userRole = String(result.user.role || "").toLowerCase().trim();

if(userRole === activeTab){

navigate(REDIRECTS[activeTab], { replace:true });

}

else{

setError(`This account is not a ${TABS.find(t=>t.key===activeTab).label} account`);

}

}


}

catch(err){

console.log("HOME LOGIN ERROR", err);

setError(

err.response?.data?.message ||

err.response?.data?.error ||

"Invalid email or password"

);

}

finally{

setLoading(false);

}


};




return(


<div className="home2-page">


<section className="home2-hero">


<div className="home2-left">


<span className="home2-badge"><FaBolt/> {branding.homepage_badge_text}</span>


<h1>

{branding.homepage_headline}
<br/>
<span className="home2-highlight">{branding.homepage_headline_highlight}</span>

</h1>


<p className="home2-subtext">{branding.homepage_subtext}</p>


<div className="home2-illustration">

{
branding.homepage_hero_image_url ?

<img src={branding.homepage_hero_image_url} alt="Vetri Jobs"/>

:

<div className="home2-illustration-fallback">

<FaRobot/>

</div>
}


<div className="home2-floating-badge home2-badge-score">

<div className="home2-badge-ring"><FaFileAlt/></div>

<div>

<strong>AI Resume Score</strong>

<span>85%</span>

</div>

</div>


<div className="home2-floating-badge home2-badge-match">

<div className="home2-badge-target"><FaBullseye/></div>

<div>

<strong>Job Match</strong>

<span>92%</span>

</div>

</div>


<div className="home2-floating-badge home2-badge-ready">

<div className="home2-badge-check"><FaCheckCircle/></div>

<span>Interview Ready</span>

</div>


<div className="home2-decorative-text">

Better Skills<br/>Brighter Future

</div>


</div>


<div className="home2-features">

{
FEATURES.map((f,i)=>(

<div className="home2-feature-item" key={i}>

<div className="home2-feature-icon">{f.icon}</div>

<div>

<strong>{f.title}</strong>

<p>{f.desc}</p>

</div>

</div>

))
}

</div>


<div className="home2-stats">

{
STATS.map((s,i)=>(

<div className="home2-stat" key={i}>

<h3>{s.value}</h3>

<p>{s.label}</p>

</div>

))
}

</div>


</div>




<div className="home2-right">


<div className="home2-login-card">


<h2>Welcome Back!</h2>

<p className="home2-login-sub">Login to your Vetri Jobs account</p>


<div className="home2-tabs">

{
TABS.map(tab=>(

<button

key={tab.key}

type="button"

className={activeTab===tab.key ? "active" : ""}

onClick={()=>handleTabChange(tab.key)}

>

{tab.icon} {tab.label}

</button>

))
}

</div>


<form onSubmit={handleSubmit}>


<div className="home2-input">

<input

type="email"

name="email"

placeholder="Enter your email address"

value={form.email}

onChange={handleChange}

required

/>

</div>


<div className="home2-input">

<input

type={showPassword ? "text" : "password"}

name="password"

placeholder="Enter your password"

value={form.password}

onChange={handleChange}

required

/>

<button type="button" className="home2-eye" onClick={()=>setShowPassword(!showPassword)}>

{showPassword ? <FaEyeSlash/> : <FaEye/>}

</button>

</div>


<div className="home2-row">

<label className="home2-remember">

<input

type="checkbox"

checked={remember}

onChange={(e)=>setRemember(e.target.checked)}

/>

Remember me

</label>


<button

type="button"

className="home2-forgot-link"

onClick={()=>setShowForgotModal(true)}

>

Forgot Password?

</button>

</div>


{
error &&

<div className="home2-error">{error}</div>
}


<button type="submit" className="home2-submit" disabled={loading}>

{loading ? "Logging in..." : `Login to ${TABS.find(t=>t.key===activeTab).label} Portal`} <FaArrowRight/>

</button>


</form>


{
REGISTER_LINKS[activeTab] &&

<p className="home2-register">

Don't have an account?{" "}

<Link to={REGISTER_LINKS[activeTab]}>Register Here</Link>

</p>
}


{
activeTab==="company" &&

<button

type="button"

className="home2-status-link"

onClick={()=>setShowStatusModal(true)}

>

Check application status

</button>
}


</div>


</div>


{
showStatusModal &&

<div className="home2-status-overlay" onClick={closeStatusModal}>

<div className="home2-status-modal" onClick={(e)=>e.stopPropagation()}>

<div className="home2-status-header">

<h2>Application Status</h2>

<button type="button" onClick={closeStatusModal}><FaTimes/></button>

</div>

<p className="home2-status-sub">

Enter your registered credentials to check your company's approval status.

</p>

{
!statusResult ?

<form onSubmit={handleCheckStatus}>

<label>Username</label>

<div className="home2-status-input">

<FaBuilding/>

<input

placeholder="Enter your username"

value={statusForm.username}

onChange={(e)=>setStatusForm({...statusForm, username:e.target.value})}

required

/>

</div>

<label>Password</label>

<div className="home2-status-input">

<FaLock/>

<input

type="password"

placeholder="Enter your password"

value={statusForm.password}

onChange={(e)=>setStatusForm({...statusForm, password:e.target.value})}

required

/>

</div>

{
statusError &&

<div className="home2-status-error">{statusError}</div>
}

<button type="submit" className="home2-status-submit" disabled={statusLoading}>

{statusLoading ? "Checking..." : "Check Status"}

</button>

</form>

:

<div className="home2-status-result">

{
statusResult.approval_status === "approved" &&

<div className="home2-status-pill approved">

<FaCheckCircle/> Approved - you can now log in

</div>
}

{
statusResult.approval_status === "pending" &&

<div className="home2-status-pill pending">

<FaClock/> Still under review

</div>
}

{
statusResult.approval_status === "rejected" &&

<div className="home2-status-pill rejected">

<FaExclamationCircle/> Rejected

</div>
}

<p className="home2-status-name">{statusResult.company_name}</p>

{
statusResult.approval_status === "rejected" && statusResult.rejection_reason &&

<p className="home2-status-reason">{statusResult.rejection_reason}</p>
}

<button

type="button"

className="home2-status-submit"

onClick={closeStatusModal}

>

Close

</button>

</div>
}

</div>

</div>
}


{
showForgotModal &&

<div className="home2-status-overlay" onClick={closeForgotModal}>

<div className="home2-status-modal" onClick={(e)=>e.stopPropagation()}>

<div className="home2-status-header">

<h2>Reset Password</h2>

<button type="button" onClick={closeForgotModal}><FaTimes/></button>

</div>

{
forgotSuccess ? (

<div className="home2-status-result">

<div className="home2-status-pill approved">

<FaCheckCircle/> Password Reset

</div>

<p className="home2-status-reason">

Your password has been reset successfully. You can now log in with your new password.

</p>

<button

type="button"

className="home2-status-submit"

onClick={closeForgotModal}

>

Close

</button>

</div>

) : forgotStep === 1 ? (

<>

<p className="home2-status-sub">

Enter your email address. We'll send you a 6-digit code to verify your identity.

</p>

<form onSubmit={handleSendOtp}>

<label>Email Address</label>

<div className="home2-status-input">

<input

type="email"

placeholder="e.g., user@example.com"

value={forgotEmail}

onChange={(e)=>setForgotEmail(e.target.value)}

required

/>

</div>

{
forgotError &&

<div className="home2-status-error">{forgotError}</div>
}

<button type="submit" className="home2-status-submit" disabled={forgotLoading}>

{forgotLoading ? "Sending..." : "Send Verification Code"}

</button>

</form>

</>

) : (

<>

<p className="home2-status-sub">

Enter the 6-digit code sent to <strong>{forgotEmail}</strong>, along with your new password.

</p>

<form onSubmit={handleResetWithOtp}>

<label>Verification Code</label>

<div className="home2-status-input">

<input

type="text"

inputMode="numeric"

maxLength={6}

placeholder="6-digit code"

value={forgotOtp}

onChange={(e)=>setForgotOtp(e.target.value.replace(/\D/g,""))}

required

/>

</div>

<label>New Password</label>

<div className="home2-status-input">

<input

type="password"

placeholder="Enter new password"

value={forgotNewPassword}

onChange={(e)=>setForgotNewPassword(e.target.value)}

required

/>

</div>

<label>Confirm Password</label>

<div className="home2-status-input">

<input

type="password"

placeholder="Confirm new password"

value={forgotConfirmPassword}

onChange={(e)=>setForgotConfirmPassword(e.target.value)}

required

/>

</div>

{
forgotError &&

<div className="home2-status-error">{forgotError}</div>
}

<button type="submit" className="home2-status-submit" disabled={forgotLoading}>

{forgotLoading ? "Resetting..." : "Reset Password"}

</button>

</form>

<button

type="button"

className="home2-status-link"

onClick={()=>setForgotStep(1)}

>

Didn't get a code? Try a different email

</button>

</>
)
}

</div>

</div>
}


</section>


</div>


);


};




export default Home;
