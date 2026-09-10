import React, {

    useState,

    useEffect

} from "react";


import {

    useNavigate,

    Link

} from "react-router-dom";


import {

    useAuth

} from "../../../context/AuthContext";


import {

    getSiteBranding

} from "../../../api/brandingApi";


import {

    FaUserShield,

    FaLock,

    FaEnvelope,

    FaEye,

    FaEyeSlash,

    FaSignInAlt,

    FaChartBar,

    FaUsers

} from "react-icons/fa";


import "./PlacementLogin.css";




const PlacementLogin = ()=>{


const navigate = useNavigate();


const { login } = useAuth();


const [branding,setBranding] = useState({

site_name:"Vetri Jobs",

tagline:"Career Portal",

logo_url:null,

placement_login_hero_image_url:null,

placement_login_headline:"Manage Placements Create Impact",

placement_login_subheadline:"Streamline drives, track progress and empower student success.",

});


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);


const [form,setForm]=useState({ email:"", password:"" });


const [showPassword,setShowPassword]=useState(false);


const [error,setError]=useState("");


const [loading,setLoading]=useState(false);




const handleChange=(e)=>{

setForm({ ...form, [e.target.name]: e.target.value });

};




const handleSubmit=async(e)=>{

e.preventDefault();

setError("");

setLoading(true);


try{


const result = await login({

email: form.email.trim(),

password: form.password

});


if(result.success){


const userRole = String(result.user.role || "").toLowerCase().trim();


if(userRole==="placement_admin"){

navigate("/placement/dashboard", { replace:true });

}

else if(userRole==="super_admin"){

navigate("/admin/dashboard", { replace:true });

}

else{

setError("This is not a placement administrator account");

}


}

else{

setError(result.message || "Invalid email or password");

}


}

catch(error){

console.error("PLACEMENT LOGIN ERROR", error);

setError(

error.response?.data?.detail ||

"Invalid email or password"

);

}

finally{

setLoading(false);

}


};








return(



<div className="placement-split-page">


<div className="placement-split-card">


<div className="placement-split-left">


<div className="student-login-topbar">

<div className="student-login-logo-badge">

{
branding.logo_url ?
<img src={branding.logo_url} alt={branding.site_name}/>
:
<FaUserShield/>
}

</div>

<div>

<h2>{branding.site_name || "Vetri Jobs"}</h2>

<span>{branding.tagline || "Career Portal"}</span>

</div>

</div>


<h1 className="student-login-headline">

{
(branding.placement_login_headline || "Manage Placements Create Impact")
    .split(" ")
    .map((word,index,arr)=>(

    <span key={index} className={index>=arr.length-2 ? "accent" : ""}>

    {word}{" "}

    </span>

    ))
}

</h1>


<p className="student-login-sub">

{

branding.placement_login_subheadline ||

"Streamline drives, track progress and empower student success."

}

</p>


<div className="placement-split-illustration">

{
branding.placement_login_hero_image_url ?

<img

src={branding.placement_login_hero_image_url}

alt="Vetri Jobs"

className="student-login-hero-img"

/>

:

<div className="placement-split-fallback">

<FaUserShield/>

</div>
}

<span className="floating-chip chip-1"><FaChartBar/></span>

<span className="floating-chip chip-2"><FaUsers/></span>

</div>


</div>




<div className="placement-split-right">


<h1>Placement Administrator</h1>

<p>Login to manage placements, drives and candidates.</p>


{
error &&

<div className="placement-login-error">{error}</div>

}


<form onSubmit={handleSubmit}>


<label>Email</label>

<div className="placement-input">

<FaEnvelope/>

<input

type="email"

name="email"

value={form.email}

onChange={handleChange}

placeholder="Enter your email"

required

/>

</div>


<label>Password</label>

<div className="placement-input">

<FaLock/>

<input

type={showPassword ? "text" : "password"}

name="password"

value={form.password}

onChange={handleChange}

placeholder="Enter your password"

required

/>

<button

type="button"

className="toggle-password"

onClick={()=>setShowPassword(!showPassword)}

>

{showPassword ? <FaEyeSlash/> : <FaEye/>}

</button>

</div>


<button

type="submit"

className="placement-login-btn"

disabled={loading}

>

<FaSignInAlt/> {loading ? "Signing in..." : "Login"}

</button>


</form>


<div className="placement-login-footer">

<Link to="/">Back to Home</Link>

</div>


</div>


</div>


</div>


);



};




export default PlacementLogin;
