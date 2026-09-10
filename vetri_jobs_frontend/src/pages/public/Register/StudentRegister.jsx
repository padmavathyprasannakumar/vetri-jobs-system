import React, {

    useState,

    useEffect

} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    registerUser

} from "../../../api/authApi";


import {

    getLookupLists

} from "../../../api/lookupApi";


import {

    getSiteBranding

} from "../../../api/brandingApi";


import {

    FaUserGraduate,
    FaUser,
    FaEnvelope,
    FaLock,
    FaPhone,
    FaEye,
    FaEyeSlash,
    FaArrowRight,
    FaUniversity

} from "react-icons/fa";


import "./StudentRegister.css";







function StudentRegister(){



const navigate = useNavigate();


// Departments / Courses configured by the Super Admin
// (Django Admin) - powers the dropdowns below instead of
// free-text typing.

const [lookups,setLookups]=useState({

    departments:[],

    courses:[],

});


const [branding,setBranding]=useState({

site_name:"Vetri Jobs",

tagline:"Career Portal",

logo_url:null,

register_hero_image_url:null,

register_headline:"Your Future Starts Here",

register_subheadline:"Join thousands of students and discover your dream career.",

});


useEffect(()=>{

getSiteBranding()

.then(res=>setBranding(prev=>({...prev, ...res.data})))

.catch(()=>{});

},[]);



useEffect(()=>{

const loadLookups=async()=>{

try{

const response = await getLookupLists();

setLookups({

departments: response.data?.departments || [],

courses: response.data?.courses || [],

});

}
catch(error){

console.log("LOOKUP LOAD ERROR", error);

}

};

loadLookups();

},[]);




const [form,setForm]=useState({

    full_name:"",

    student_id:"",

    course:"",

    department:"",

    graduation_year:"",

    username:"",

    email:"",

    phone:"",

    password:"",

    confirm_password:""

});


const [countryCode,setCountryCode]=useState("+91");







const [showPassword,setShowPassword]=useState(false);


const [showConfirm,setShowConfirm]=useState(false);



const [loading,setLoading]=useState(false);



const [error,setError]=useState("");


const [success,setSuccess]=useState("");









// =====================================================
// HANDLE INPUT
// =====================================================


const handleChange=(e)=>{


    setForm({

        ...form,


        [e.target.name]:

        e.target.value


    });


};









// =====================================================
// ERROR FORMATTER
// =====================================================


const getBackendError=(data)=>{


    if(!data)

        return "Registration failed";




    if(typeof data === "string")

        return data;




    if(data.message)

        return data.message;




    if(data.errors){


        const first =

        Object.values(data.errors)[0];


        return Array.isArray(first)

        ?

        first[0]

        :

        first;


    }





    const firstError =

    Object.values(data)[0];



    if(Array.isArray(firstError))

        return firstError[0];



    return firstError || "Registration failed";


};












// =====================================================
// SUBMIT REGISTER
// =====================================================


const handleSubmit=async(e)=>{


e.preventDefault();




if(loading)

    return;





setError("");

setSuccess("");







if(

form.password !==

form.confirm_password

){


    setError(

        "Password and confirm password do not match"

    );


    return;


}







setLoading(true);








try{


const payload={


username:
form.username.trim(),


email:
form.email.trim(),


phone:
`${countryCode}${form.phone.trim()}`,


password:
form.password,


confirm_password:
form.confirm_password,


role:
"student",



full_name:
form.full_name.trim(),



student_id:
form.student_id.trim(),



course:
form.course.trim(),



department:
form.department.trim(),



graduation_year:
Number(form.graduation_year)



};







console.log(

"REGISTER PAYLOAD:",

payload

);









const response = await registerUser(

    payload

);









console.log(

"REGISTER RESPONSE:",

response.data

);








if(

response.status === 200

||

response.status === 201

){



    setSuccess(

        "Account created successfully. Redirecting..."

    );







    setTimeout(()=>{



        navigate(

            "/student/login",

            {

                replace:true

            }

        );



    },1500);





}

else{


    setError(

        "Registration failed"

    );


}





}

catch(error){



console.error(

"REGISTER ERROR:",

error

);





setError(

getBackendError(

    error.response?.data

)

);




}

finally{


setLoading(false);



}



};









return(



<div className="student-register-page">





<div className="student-register-card">







{/* LEFT SIDE */}



<div className="student-register-left">


<div className="student-login-topbar">

    <div className="student-login-logo-badge">

        {
        branding.logo_url ?
        <img src={branding.logo_url} alt={branding.site_name}/>
        :
        <FaUserGraduate/>
        }

    </div>

    <div>

        <h2>{branding.site_name || "Vetri Jobs"}</h2>

        <span>{branding.tagline || "Career Portal"}</span>

    </div>

</div>


<h1 className="student-login-headline">

    {
    (branding.register_headline || "Your Future Starts Here")
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

    branding.register_subheadline ||

    "Join thousands of students and discover your dream career."

    }

</p>


<div className="student-login-illustration large">

    {
    branding.register_hero_image_url ?

    <img

    src={branding.register_hero_image_url}

    alt="Vetri Jobs"

    className="student-login-hero-img"

    />

    :

    <div className="student-login-bot vj-float-icon">

        <div className="bot-head">

            <div className="bot-face">^_^</div>

        </div>

        <div className="bot-body">VJ</div>

    </div>
    }

    <span className="floating-chip chip-1">🏢</span>

    <span className="floating-chip chip-2">🎓</span>

</div>



</div>









{/* RIGHT SIDE */}



<div className="student-register-right">





<h2>

Create Student Account

</h2>



<p>

Register to apply for jobs.

</p>









<form

onSubmit={handleSubmit}

>







<div className="two-column">







<div>


<label>
Course
</label>


<div className="input-box">

<FaUniversity/>

<input

type="text"

name="course"

value={form.course}

onChange={handleChange}

placeholder="Enter your course (e.g. B.Tech Computer Science)"

required

/>


</div>


<label>
Department
</label>


<div className="input-box">

<FaUniversity/>

<input

type="text"

name="department"

value={form.department}

onChange={handleChange}

placeholder="Enter your department (e.g. Computer Science)"

required

/>


</div>

<label>
Graduation Year
</label>


<div className="input-box">


<input

type="number"

name="graduation_year"

value={form.graduation_year}

onChange={handleChange}

placeholder="2027"

required

/>


</div>



<label>
Full Name
</label>


<div className="input-box">


<FaUser/>



<input


type="text"


name="full_name"


value={form.full_name}


onChange={handleChange}


placeholder="Full name"


required


/>



</div>



</div>









<div>


<label>

Education

</label>



<div className="input-box">


<FaUniversity/>



<input


type="text"


name="education"


value={form.education}


onChange={handleChange}


placeholder="Degree / Course"


required


/>



</div>



</div>





</div>









<label>

Username

</label>



<div className="input-box">


<FaUser/>



<input


type="text"


name="username"


value={form.username}


onChange={handleChange}


placeholder="Username"


required


/>



</div>









<label>

Email

</label>



<div className="input-box">


<FaEnvelope/>



<input


type="email"


name="email"


value={form.email}


onChange={handleChange}


placeholder="Email"


required


/>



</div>









<label>

Phone Number

</label>



<div className="input-box">


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


value={form.phone}


onChange={handleChange}


placeholder="Phone number"


required


/>



</div>









<label>

Password

</label>



<div className="input-box">


<FaLock/>




<input


type={showPassword ? "text":"password"}


name="password"


value={form.password}


onChange={handleChange}


placeholder="Password"


required


/>



<span

onClick={()=>setShowPassword(!showPassword)}

>



{

showPassword

?

<FaEyeSlash/>

:

<FaEye/>

}



</span>



</div>









<label>

Confirm Password

</label>



<div className="input-box">


<FaLock/>




<input


type={showConfirm ? "text":"password"}


name="confirm_password"


value={form.confirm_password}


onChange={handleChange}


placeholder="Confirm password"


required


/>



<span

onClick={()=>setShowConfirm(!showConfirm)}

>



{

showConfirm

?

<FaEyeSlash/>

:

<FaEye/>

}



</span>



</div>









{
error &&

<div className="error-box">

{error}

</div>

}







{
success &&

<div className="success-box">

{success}

</div>

}









<button


type="submit"


disabled={loading}


className="register-button"


>


<FaArrowRight/>





{

loading

?

"Creating Account..."

:

"Register Student"

}





</button>









</form>









<div className="login-link">


Already have account?



<span

onClick={()=>navigate("/student/login")}

>


Login


</span>



</div>







</div>







</div>





</div>



);



}



export default StudentRegister;