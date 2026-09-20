import React, {
    useState
} from "react";


import {
    Link,
    useNavigate
} from "react-router-dom";


import {
    FaBars,
    FaTimes,
    FaUserCircle
} from "react-icons/fa";

import BrandLogo from "../BrandLogo/BrandLogo";


import {
    useAuth
} from "../../context/AuthContext";


import "./Navbar.css";




const Navbar = ()=>{


const navigate = useNavigate();


const {
    user,
    logout
}=useAuth();



const [menuOpen,setMenuOpen]=useState(false);





const handleLogout=()=>{


logout();


navigate("/");


};







return (


<nav className="navbar">



{/* LOGO - also serves as the "go home / login" entry point,
    since clicking it already navigates to "/", where the
    Student/Company/Placement Admin login tabs all live. */}

<BrandLogo onClick={()=>navigate("/")}/>









{/* MOBILE MENU ICON */}

<div 
className="mobile-menu"
onClick={()=>{
setMenuOpen(!menuOpen)
}}
>


{

menuOpen

?

<FaTimes/>

:

<FaBars/>

}


</div>









<div 
className={
menuOpen
?
"navbar-links active"
:
"navbar-links"
}
>



{/*
    Everything except Company Register has been removed here.
    Student and Placement Admin accounts are created only in
    Django Admin now, so there is nothing left to self-serve
    for them - and "Home", "For Students", "Placement Admin"
    and a standalone "Login" button all used to point at the
    exact same "/" page (where every role's login tab already
    lives), which was confusing rather than useful. Company
    Register is the one distinct, real action left, so it's
    the only thing shown to a logged-out visitor.
*/}



{

!user &&

<Link

to="/company/register"

className="navbar-login-btn"

>

Register Company

</Link>


}









{

user && user.role==="student" &&

<>


<Link to="/student/dashboard">

Dashboard

</Link>



<Link to="/student/profile">

Profile

</Link>



<div className="user-box">


<FaUserCircle/>


<span>

{
user.username
}

</span>


</div>



<button
className="logout-btn"
onClick={handleLogout}
>

Logout

</button>



</>

}









{

user && user.role==="company" &&

<>


<Link to="/company/dashboard">

Dashboard

</Link>




<Link to="/company/profile">

Company Profile

</Link>



<div className="user-box">


<FaUserCircle/>


<span>

{
user.username
}

</span>


</div>



<button
className="logout-btn"
onClick={handleLogout}
>

Logout

</button>



</>

}






</div>



</nav>


);


};


export default Navbar;
