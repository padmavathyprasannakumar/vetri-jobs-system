import React, { useState } from "react";

import { useParams, useNavigate, Link } from "react-router-dom";

import { confirmPasswordReset } from "../../../api/authApi";

import {

    FaLock,
    FaEye,
    FaEyeSlash,
    FaCheckCircle,

} from "react-icons/fa";

import "./ResetPassword.css";




const ResetPassword = ()=>{


const { uidb64, token } = useParams();

const navigate = useNavigate();


const [newPassword,setNewPassword] = useState("");

const [confirmPassword,setConfirmPassword] = useState("");

const [showPassword,setShowPassword] = useState(false);

const [loading,setLoading] = useState(false);

const [error,setError] = useState("");

const [success,setSuccess] = useState(false);




const handleSubmit = async(e)=>{

e.preventDefault();

setError("");


if(newPassword !== confirmPassword){

setError("Passwords do not match");

return;

}


if(newPassword.length < 8){

setError("Password must be at least 8 characters");

return;

}


setLoading(true);


try{


await confirmPasswordReset({

uidb64,

token,

new_password: newPassword,

confirm_password: confirmPassword,

});


setSuccess(true);


setTimeout(()=>{

navigate("/", { replace:true });

}, 2500);


}

catch(err){


setError(

err.response?.data?.error ||

"This reset link is invalid or has expired. Please request a new one."

);


}

finally{


setLoading(false);


}


};




return(


<div className="reset-pw-page">


<div className="reset-pw-card">


{
success ? (

<div className="reset-pw-success">

<FaCheckCircle/>

<h2>Password Reset!</h2>

<p>Your password has been changed successfully. Redirecting you to login...</p>

</div>

) : (

<>

<h2>Set a New Password</h2>

<p className="reset-pw-sub">Choose a new password for your Vetri Jobs account.</p>


<form onSubmit={handleSubmit}>


<label>New Password</label>

<div className="reset-pw-input">

<FaLock/>

<input

type={showPassword ? "text" : "password"}

placeholder="Enter new password"

value={newPassword}

onChange={(e)=>setNewPassword(e.target.value)}

required

/>

<button type="button" onClick={()=>setShowPassword(!showPassword)}>

{showPassword ? <FaEyeSlash/> : <FaEye/>}

</button>

</div>


<label>Confirm Password</label>

<div className="reset-pw-input">

<FaLock/>

<input

type={showPassword ? "text" : "password"}

placeholder="Confirm new password"

value={confirmPassword}

onChange={(e)=>setConfirmPassword(e.target.value)}

required

/>

</div>


{
error &&

<div className="reset-pw-error">{error}</div>
}


<button type="submit" className="reset-pw-submit" disabled={loading}>

{loading ? "Resetting..." : "Reset Password"}

</button>


</form>


<p className="reset-pw-back">

<Link to="/">Back to Login</Link>

</p>


</>

)
}


</div>


</div>


);


};




export default ResetPassword;
